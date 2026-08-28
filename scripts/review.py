#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成された原稿を、調査メモと突き合わせて検証する。

    python3 scripts/review.py post/2026-08-25

validate.py が「形式」を見るのに対し、こちらは「中身」を見る。
別のモデル呼び出しに、書いた本人ではなく検査役として原稿を読ませ、
調査メモに根拠のない数字・主張が混ざっていないかを指摘させる。

無人で投稿する以上、事実誤認が最大のリスクなのでここを最後の関門にしている。
critical が1件でも出れば異常終了し、投稿は行われない。

必要な環境変数:
    ANTHROPIC_API_KEY   必須
    CLAUDE_MODEL        任意（既定 claude-sonnet-4-5）
    REVIEW_STRICT       任意。"1" にすると warning でも止める
"""
import hashlib
import json
import os
import sys
import urllib.request
import urllib.error
from pathlib import Path

API = "https://api.anthropic.com/v1/messages"

SYSTEM = """あなたは経済ニュース解説の校閲者です。書き手ではありません。
これから、調査メモと、それを元に書かれた投稿原稿を渡します。

あなたの仕事は、原稿に載っている数字と主張のひとつひとつについて、
**調査メモの中に根拠があるかを確認すること**です。

critical として報告すべきもの:
- 調査メモに存在しない数字が原稿に出ている
- 調査メモの数字と原稿の数字が食い違っている（桁、単位、日付を含む）
- 調査メモでは「推計」「見通し」「観測」とされているものが、原稿では確定事実として書かれている
- 出典のない断定的な予測（「〜になる」「〜する見込み」を根拠なく書いている）
- 投資助言・銘柄推奨と読めるもの
- 事実と意見の区別がついていない箇所

warning として報告すべきもの:
- 表現は正しいが誤解を招きやすい書き方
- 数字は合っているが文脈（いつ時点か、何と比べてか）が抜けている
- 反対意見の扱いが形式的で、実質的な反証になっていない

原稿を良くする提案は不要です。**問題の指摘だけ**してください。
問題がなければ issues を空にしてください。
甘く見ないでください。あなたが見逃したものは、そのまま公開されます。"""

SCHEMA = {
    "type": "object",
    "required": ["verdict", "issues"],
    "properties": {
        "verdict": {"type": "string", "enum": ["pass", "fail"],
                    "description": "critical が1件でもあれば fail"},
        "issues": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["severity", "where", "what"],
                "properties": {
                    "severity": {"type": "string", "enum": ["critical", "warning"]},
                    "where": {"type": "string", "description": "どこの記述か（例: 2枚目の1つ目の箇条書き）"},
                    "what": {"type": "string", "description": "何が問題か。調査メモのどの記述と食い違うかを具体的に"},
                },
            },
        },
        "note": {"type": "string", "description": "全体の所見を1〜2文で。任意"},
    },
}


def main():
    day = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key:
        raise SystemExit("ANTHROPIC_API_KEY が未設定です。")
    model = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-5")

    doc = json.loads((day / "content.json").read_text(encoding="utf-8"))
    research = (day / "research.md")
    if not research.exists():
        # 調査メモがなければ突き合わせる相手がいない＝検証できない。
        # 無人で投稿する以上、検証できないものを通してはいけないので中断する。
        if os.environ.get("REVIEW_ALLOW_NO_RESEARCH") == "1":
            print("注意: research.md がありません。"
                  "REVIEW_ALLOW_NO_RESEARCH=1 のため検証をスキップします。")
            return
        raise SystemExit(
            f"research.md がありません: {research}\n"
            "調査メモがないと原稿の数字を照合できないため、投稿を中止します。\n"
            "手書きの content.json を意図的に通す場合のみ REVIEW_ALLOW_NO_RESEARCH=1 を指定してください。")
    notes = research.read_text(encoding="utf-8")

    draft = {"slides": doc.get("slides"), "captions": doc.get("captions"),
             "sources": doc.get("sources")}

    payload = {
        "model": model, "max_tokens": 4000, "system": SYSTEM,
        "tools": [{"name": "report", "description": "校閲結果を報告する", "input_schema": SCHEMA}],
        "tool_choice": {"type": "tool", "name": "report"},
        "messages": [{"role": "user", "content":
                      f"# 調査メモ\n\n{notes}\n\n---\n\n# 投稿原稿\n\n"
                      f"```json\n{json.dumps(draft, ensure_ascii=False, indent=2)}\n```"}],
    }
    req = urllib.request.Request(
        API, data=json.dumps(payload).encode(),
        headers={"x-api-key": key, "anthropic-version": "2023-06-01",
                 "content-type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            res = json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        raise SystemExit(f"[Anthropic API エラー] HTTP {e.code}\n{e.read().decode(errors='replace')}")

    block = next((b for b in res["content"] if b.get("type") == "tool_use"), None)
    if not block:
        raise SystemExit("校閲結果を受け取れませんでした。安全側に倒して中断します。")
    out = block["input"]
    issues = out.get("issues", [])
    crit = [i for i in issues if i.get("severity") == "critical"]
    warns = [i for i in issues if i.get("severity") == "warning"]

    # どの原稿を校閲したのかを残す。check_review.py がこれで
    # 「校閲後に原稿だけ差し替える」を弾く。
    out["content_sha256"] = hashlib.sha256(
        (day / "content.json").read_bytes()).hexdigest()
    (day / "review.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    for i in warns:
        print(f"注意 [{i.get('where')}] {i.get('what')}")
    if out.get("note"):
        print(f"所見: {out['note']}")

    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write(f"### 校閲結果: {out.get('verdict')}\n\n")
            if out.get("note"):
                f.write(f"{out['note']}\n\n")
            for i in issues:
                f.write(f"- **{i.get('severity')}** [{i.get('where')}] {i.get('what')}\n")
            if not issues:
                f.write("指摘なし。\n")

    if crit:
        print("\n校閲で重大な指摘が出ました。投稿は行いません。")
        for i in crit:
            print(f"  critical [{i.get('where')}] {i.get('what')}")
        sys.exit(1)
    if warns and os.environ.get("REVIEW_STRICT") == "1":
        print("\nREVIEW_STRICT=1 のため、警告でも中断します。")
        sys.exit(1)
    print(f"校閲OK（重大 0件 / 注意 {len(warns)}件）")


if __name__ == "__main__":
    main()
