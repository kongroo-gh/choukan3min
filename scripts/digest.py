#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""その日の投稿が終わったあとに、翌日以降のための記録を残す。

    python3 scripts/digest.py post/2026-08-27

出力は post/<日付>/digest.md。翌朝 generate.py がこれを読み、
NotebookLM から来た調査メモと突き合わせてネタを選定する。

記録は2階建てになっている。
    骨格 … content.json から機械的に作る。テーマ・使った数字・出典・反対意見。
           APIキーが無くても必ず書き出される。
    所見 … 積み残した論点と追うべき続報。1回だけAPIを呼んで書かせる。
           失敗しても骨格だけ残して正常終了する。

投稿が済んだあとに走るので、ここで落ちても手遅れである。
したがって、この工程は決してワークフローを失敗させない。

必要な環境変数:
    ANTHROPIC_API_KEY   任意。無ければ骨格だけ書く
    CLAUDE_MODEL        任意（既定 claude-sonnet-4-5）
"""
import json
import os
import re
import sys
import urllib.request
import urllib.error
from pathlib import Path

API = "https://api.anthropic.com/v1/messages"


def plain(s):
    """原稿の <b> / <em> を落とす。記録は人も読むしモデルにも渡すため。"""
    return re.sub(r"</?(?:b|em)>", "", str(s or "")).strip()

SCHEMA = {
    "type": "object",
    "required": ["angle", "leftovers", "followups"],
    "properties": {
        "angle": {"type": "string",
                  "description": "今日どういう切り口で書いたかを40字程度で。翌日ぶつからないように"},
        "leftovers": {
            "type": "array", "minItems": 0, "maxItems": 5, "items": {"type": "string"},
            "description": "調査メモにはあったが今日は使わなかった論点。翌日以降の候補になる。各40字程度",
        },
        "followups": {
            "type": "array", "minItems": 0, "maxItems": 5, "items": {"type": "string"},
            "description": "続報を追うべき点。『いつ何が出るか』が分かるものは日付も。各40字程度",
        },
    },
}


def skeleton(day, doc):
    """content.json から機械的に作れる部分。APIに依存しない。"""
    out = [f"# {day} の記録", ""]
    out += [f"- テーマ: {plain(doc.get('topic')) or '(不明)'}"]
    out += [f"- 調査メモの出所: {doc.get('research_source', '不明')}"]

    slides = doc.get("slides") or []

    def slide(kind):
        return next((s for s in slides if isinstance(s, dict) and s.get("kind") == kind), {})

    stats = slide("numbers").get("stats") or []
    if stats:
        out += ["", "## 使った数字"]
        for s in stats:
            if isinstance(s, list) and len(s) >= 3:
                out.append(f"- {plain(s[0])}: {plain(s[1])}{plain(s[2])}"
                           + (f"（{plain(s[3])}）" if len(s) > 3 and s[3] else ""))

    caution = plain(slide("life").get("caution"))
    if caution:
        out += ["", "## 提示した反対意見", f"- {caution}"]

    src = doc.get("sources") or []
    if src:
        out += ["", "## 使った出典"]
        out += [f"- {u}" for u in src]
    return out


def call(payload, key):
    req = urllib.request.Request(
        API, data=json.dumps(payload).encode(),
        headers={"x-api-key": key, "anthropic-version": "2023-06-01",
                 "content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.loads(r.read().decode())


def main():
    day_dir = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    day = day_dir.name
    content = day_dir / "content.json"
    if not content.exists():
        print(f"{content} がありません。記録は作りません。")
        return 0

    doc = json.loads(content.read_text(encoding="utf-8"))
    lines = skeleton(day, doc)

    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    notes = ""
    research = day_dir / "research.md"
    if research.exists():
        notes = research.read_text(encoding="utf-8").strip()

    if key and notes and "--no-api" not in sys.argv:
        model = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-5")
        try:
            res = call({
                "model": model, "max_tokens": 1500,
                "tools": [{"name": "emit_digest",
                           "description": "翌日以降のための記録を出力する",
                           "input_schema": SCHEMA}],
                "tool_choice": {"type": "tool", "name": "emit_digest"},
                "messages": [{"role": "user", "content":
                              f"{day} の朝刊3分は「{doc.get('topic')}」を扱いました。\n\n"
                              "以下はその日の調査メモです。この中で今日の原稿に"
                              "使われなかった論点と、続報を追うべき点を emit_digest で"
                              "書き出してください。メモに書かれていないことは足さないでください。\n\n"
                              f"--- 調査メモ ---\n{notes[:20000]}\n\n"
                              f"--- 今日の原稿 ---\n"
                              f"{json.dumps(doc.get('slides'), ensure_ascii=False)[:8000]}"}],
            }, key)
            block = next((b for b in res["content"] if b.get("type") == "tool_use"), None)
            if block:
                d = block["input"]
                if d.get("angle"):
                    lines += ["", "## 今日の切り口", f"- {d['angle']}"]
                if d.get("leftovers"):
                    lines += ["", "## 積み残した論点（翌日以降の候補）"]
                    lines += [f"- {x}" for x in d["leftovers"]]
                if d.get("followups"):
                    lines += ["", "## 追うべき続報"]
                    lines += [f"- {x}" for x in d["followups"]]
                print("所見を書き出しました。")
        except (urllib.error.HTTPError, urllib.error.URLError, KeyError, ValueError) as e:
            # 投稿は既に済んでいる。ここで失敗しても骨格だけ残して正常終了する。
            print(f"所見の作成に失敗しました（骨格のみ残します）: {type(e).__name__}: {e}")
    else:
        print("APIを呼ばずに骨格だけ書き出します。")

    (day_dir / "digest.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"→ {day_dir}/digest.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
