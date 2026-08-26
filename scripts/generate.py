#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""その日の経済ニュースを調べ、カルーセル5枚分の原稿 content.json を作る。

    python3 scripts/generate.py post/2026-08-25

必要な環境変数:
    ANTHROPIC_API_KEY   必須
    CLAUDE_MODEL        任意（既定 claude-sonnet-4-5）
    ACCOUNT_HANDLE      任意（既定 @economy-social）
    RECENT_TOPICS       任意。直近の投稿テーマを改行区切りで渡すと重複を避ける

APIを2回呼ぶ。
    1回目 … web検索つきで当日のニュースを調べ、事実と数字を出典つきで書き出させる
    2回目 … その調査メモだけを渡し、決められたJSON構造に落とし込ませる

分けている理由は、検索と構造化を同時にやらせると構造が崩れやすいため。
"""
import json
import os
import re
import sys
import urllib.request
import urllib.error
from datetime import datetime, timedelta, timezone
from pathlib import Path

API = "https://api.anthropic.com/v1/messages"
JST = timezone(timedelta(hours=9))

RULES = """あなたは日本語の経済ニュース解説アカウント「朝刊3分」の編集者です。
毎朝、その日いちばん知るべき経済ニュースを1本だけ選び、5枚のスライドで解説します。

## 読者
経済の専門家ではない社会人。投資をしている人もいれば、まだの人もいる。
専門用語を使ったら、その場で言い換える。

## ネタ選定の優先順位
1. 生活に直結し、かつ数字で語れるもの（金利・物価・為替・賃金・税）
2. 世界の動きで日本に波及するもの（FOMC、原油、地政学、関税）
3. 構造的な話題（人口、産業、エネルギー、AIと雇用）
避けるもの: 個別銘柄の値動き、憶測ベースの人事、政局の細部。

## 絶対に守ること
- 数字は出典のある実数のみ。推計値は「推計」「約」と明記する。
  裏が取れない数字は、使わずに構成し直す。誤情報を出さないことが最優先。
- 投資助言・銘柄推奨をしない。「買い」「売り」「儲かる」等の表現を使わない。
- 煽らない。「衝撃」「ヤバい」「知らないと損」等を使わない。
- 5枚目には必ず反対意見・反証を1つ入れる。断定だけの投稿にしない。
- 見出しは体言止めか断定形。「〜か？」で逃げない。
- 1枚あたりの日本語は最大180字程度。読めない密度にしない。
"""

SCHEMA = {
    "type": "object",
    "required": ["topic", "slides", "captions", "sources"],
    "properties": {
        "topic": {"type": "string", "description": "その日のテーマを15字程度で。投稿ログ用"},
        "sources": {
            "type": "array", "minItems": 2, "maxItems": 8,
            "items": {"type": "string"},
            "description": "使った一次情報に近い出典のURL",
        },
        "slides": {
            "type": "array", "minItems": 5, "maxItems": 5,
            "items": {"type": "object"},
            "description": (
                "5枚。順番と構造は固定。強調したい語は <b>…</b> で囲める（他のHTMLタグは使用禁止）。\n"
                "1枚目 {kind:'cover', kicker:'日銀 × 為替 のような2語', "
                "title:['見出し1行目','見出し2行目'], sub:'数字を1つ含む2行の要約', "
                "balance_left:'下がるものの名前2〜3字', balance_right:'上がるものの名前2〜3字'}\n"
                "2枚目 {kind:'what', kicker:'① 何が起きた？', title:'見出し', "
                "bullets:['事実1','事実2','事実3'], note:'＝ で始まる一言のまとめ', "
                "sides:['左の主体2字','右の主体2字','図の下のラベル']}  sides は省略可\n"
                "3枚目 {kind:'why', kicker:'② なぜそうなる？', title:'見出し', "
                "steps:[['小見出し','説明'],['小見出し','説明'],['小見出し','説明']], "
                "tail:'＝ で始まる結論一行'}\n"
                "4枚目 {kind:'numbers', kicker:'③ 数字で見る', title:'見出し', "
                "stats:[['項目名','数値','単位','補足'] を4組], "
                "chart:[['横軸ラベル',数値,'注記'] を2〜5点], chart_caption:'グラフの説明'}  "
                "chart は数値の推移がある時だけ。無ければ chart と chart_caption を省略\n"
                "5枚目 {kind:'life', kicker:'④ 私たちへの影響', title:'見出し', "
                "cards:[['見出し','説明','アイコン名'] を3組], caution:'反対意見・反証', "
                "cta:'保存とフォローを促す2行'}  "
                "アイコン名は home / bank / cart / chart / globe / factory から選ぶ"
            ),
        },
        "captions": {
            "type": "object",
            "required": ["instagram", "threads", "bluesky"],
            "properties": {
                "instagram": {"type": "string", "description":
                              "600〜900字。末尾に『※投資判断はご自身の責任でお願いします』"
                              "と、ハッシュタグをちょうど5個（#経済ニュース #ニュース解説 #お金の勉強 ＋その日のもの2個）"},
                "threads": {"type": "string", "description":
                            "500字以内。末尾に免責文と、ハッシュタグはちょうど1個"},
                "bluesky": {"type": "string", "description":
                            "300字以内。末尾に免責文と、ハッシュタグは3個以内"},
            },
        },
    },
}


def call(payload, key):
    req = urllib.request.Request(
        API, data=json.dumps(payload).encode(),
        headers={"x-api-key": key, "anthropic-version": "2023-06-01",
                 "content-type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        raise SystemExit(f"[Anthropic API エラー] HTTP {e.code}\n{e.read().decode(errors='replace')}")


def main():
    day_dir = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    day_dir.mkdir(parents=True, exist_ok=True)
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key:
        raise SystemExit("ANTHROPIC_API_KEY が未設定です。"
                         "リポジトリの Settings → Secrets and variables → Actions で登録してください。")
    model = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-5")
    today = datetime.now(JST)
    date_s = day_dir.name if re.match(r"^\d{4}-\d{2}-\d{2}$", day_dir.name) else today.strftime("%Y-%m-%d")
    recent = os.environ.get("RECENT_TOPICS", "").strip()

    # ---- 1回目: 調べる ----
    ask = (f"今日は{date_s}（日本時間）です。\n\n"
           "今日の日本と世界の経済ニュースを web 検索で調べ、朝刊3分で扱う『今日の1本』を選んでください。\n"
           "日本国内の話題と世界の話題のバランスを意識してください。\n\n"
           "選んだら、次を出典URLつきの箇条書きで書き出してください。\n"
           "1. 何が起きたか（日付・金額・水準などの具体的な数字を必ず含める）\n"
           "2. なぜそうなるのか（因果を3段階で）\n"
           "3. 押さえるべき数字4つ（項目名・数値・単位・補足）\n"
           "4. 数値の推移があればその系列（2〜5点、日付と値）\n"
           "5. 生活への影響3つ\n"
           "6. この見方への反論・反証を1つ\n\n"
           "裏が取れなかった数字は使わず、その旨を書いてください。")
    if recent:
        ask += f"\n\n直近で扱ったテーマです。重複を避けてください:\n{recent}"

    print(f"[1/2] {date_s} のニュースを調査中…")
    res1 = call({
        "model": model, "max_tokens": 8000,
        "tools": [{"type": "web_search_20250305", "name": "web_search", "max_uses": 10}],
        "messages": [{"role": "user", "content": ask}],
        "system": RULES,
    }, key)
    notes = "".join(b.get("text", "") for b in res1["content"] if b.get("type") == "text").strip()
    if len(notes) < 200:
        raise SystemExit("調査結果が短すぎます。中断します。\n" + notes)
    u1 = res1.get("usage", {})
    print(f"  調査完了（{len(notes)}字 / in {u1.get('input_tokens')} out {u1.get('output_tokens')}）")

    # ---- 2回目: 構造化する ----
    print("[2/2] 5枚分の原稿に構成中…")
    res2 = call({
        "model": model, "max_tokens": 8000,
        "system": RULES,
        "tools": [{"name": "emit_content",
                   "description": "カルーセル5枚分の原稿と、媒体別のキャプションを出力する",
                   "input_schema": SCHEMA}],
        "tool_choice": {"type": "tool", "name": "emit_content"},
        "messages": [{"role": "user", "content":
                      f"今日は{date_s}です。以下の調査メモだけを根拠に、"
                      f"emit_content を呼んで原稿を出力してください。"
                      f"メモにない数字を足さないでください。\n\n---\n{notes}"}],
    }, key)
    block = next((b for b in res2["content"] if b.get("type") == "tool_use"), None)
    if not block:
        raise SystemExit("構造化に失敗しました。\n" + json.dumps(res2)[:2000])
    doc = block["input"]
    u2 = res2.get("usage", {})
    print(f"  構成完了（in {u2.get('input_tokens')} out {u2.get('output_tokens')}）")

    doc["date"] = date_s
    doc["eyebrow"] = "ECONOMY BRIEF"
    doc["handle"] = os.environ.get("ACCOUNT_HANDLE", "@economy-social")
    doc["model"] = model
    doc["generated_at"] = datetime.now(timezone.utc).isoformat()

    (day_dir / "content.json").write_text(
        json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    (day_dir / "research.md").write_text(
        f"# {date_s} 調査メモ\n\n{notes}\n", encoding="utf-8")

    for name in ("instagram", "threads", "bluesky"):
        (day_dir / f"{name}.txt").write_text(doc["captions"][name].strip() + "\n", encoding="utf-8")

    alts = ["表紙。" + "".join(doc["slides"][0].get("title", [])),
            "何が起きたか。事実を3点で説明。",
            "数字で見る。押さえるべき4つの数字。",
            "私たちへの影響。生活への影響を3点で。"]
    (day_dir / "bluesky.alt.txt").write_text("\n".join(alts) + "\n", encoding="utf-8")

    print(f"テーマ: {doc.get('topic')}")
    print(f"出典 {len(doc.get('sources', []))} 件")
    print(f"→ {day_dir}/content.json")


if __name__ == "__main__":
    main()
