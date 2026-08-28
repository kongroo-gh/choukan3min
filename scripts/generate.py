#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""その日の経済ニュースを調べ、カルーセル5枚分の原稿 content.json を作る。

    python3 scripts/generate.py post/2026-08-25

必要な環境変数:
    ANTHROPIC_API_KEY   必須
    CLAUDE_MODEL        任意（既定 claude-sonnet-4-5）
    ACCOUNT_HANDLE      任意（既定 @economy-social）
    RECENT_TOPICS       任意。直近の投稿テーマを改行区切りで渡すと重複を避ける
    FORCE_WEB_RESEARCH  任意。1 にすると research.md があっても無視して web検索する
    DIGEST_DAYS         任意（既定 7）。何日ぶんの digest.md を選定に使うか
    NO_WEB_SUPPLEMENT   任意。1 にすると素材が薄くても web検索で補わない

調査メモの出所は2通り。content.json の research_source に記録される。

    supplied    … post/<日付>/research.md が既にある場合（NotebookLM などで人が用意）
    web_search  … 無い場合。従来どおり web検索で自動調査し、メモ自体も作る

supplied のときは、さらに過去との突き合わせが入る。

    [調査] research.md を読む（web検索もAPIコールもしない）
    [選定] 直近の digest.md と突き合わせ、今日使う素材を選ぶ
           判定は sufficient / thin / none の3段階。基準は5枚の型を埋められるか。
           結果は selection.json に残る。
    [補足] thin か none のときだけ、足りない要素を web検索で補う
           → research_source は supplied+web になる
    [構成] 調査メモだけを根拠に、決められたJSON構造へ落とし込む

補った分は research.md の末尾に追記する。review.py は原稿を research.md と
突き合わせるので、補足をメモに入れないと正しい数字まで根拠なしと判定されるため。
人が書いた原文（目印より前）は一字も書き換えない。

digest.md は digest.py が前日の投稿後に作る。手順は NOTEBOOKLM.md を参照。
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


SELECT_SCHEMA = {
    "type": "object",
    "required": ["verdict", "reason", "focus", "use", "avoid", "gaps"],
    "properties": {
        "verdict": {
            "type": "string", "enum": ["sufficient", "thin", "none"],
            "description": "sufficient=調査メモだけで5枚を埋められる / "
                           "thin=一部足りない / none=過去の焼き直しばかりで使える素材が実質ない",
        },
        "reason": {"type": "string", "description": "その判定の理由を80字程度で"},
        "focus": {"type": "string", "description": "今日の切り口を40字程度で。過去と同じ角度にしない"},
        "use": {"type": "array", "maxItems": 8, "items": {"type": "string"},
                "description": "調査メモの中で今日使う論点。各40字程度"},
        "avoid": {"type": "array", "maxItems": 8, "items": {"type": "string"},
                  "description": "過去に同じ角度で扱い済みのため今日は避ける論点。日付を添える。"
                                 "新しい進展がある続報なら避けなくてよい"},
        "gaps": {"type": "array", "maxItems": 6, "items": {"type": "string"},
                 "description": "5枚を埋めるのに足りていない要素。web検索で補う手がかりになるよう具体的に書く。"
                                "verdict が none のときは、代わりに調べるべきテーマの手がかりを書く。"
                                "sufficient なら空"},
    },
}

# research.md に web検索の補足を追記するときの目印。
# これより前は人が用意した原文で、一字も書き換えない。
SUPPLEMENT_MARK = "<!-- 補足調査（web検索）ここから -->"


def load_digests(day_dir, n):
    """直近 n 日ぶんの digest.md を新しい順に集める。当日ぶんは除く。"""
    root = day_dir.parent
    if not root.is_dir():
        return []
    days = sorted((p for p in root.iterdir()
                   if p.is_dir() and p.name != day_dir.name and (p / "digest.md").exists()),
                  reverse=True)[:n]
    return [(d.name, (d / "digest.md").read_text(encoding="utf-8").strip()) for d in days]


def append_supplement(path, text):
    """補った調査を research.md の末尾に足す。

    原文（目印より前）はそのまま。何度走らせても
    「原文 ＋ 最新の補足1つ」に落ち着くようにしてある。
    """
    head = path.read_text(encoding="utf-8").split(SUPPLEMENT_MARK)[0].rstrip()
    path.write_text(f"{head}\n\n{SUPPLEMENT_MARK}\n## 補足調査（web検索で補った分）\n\n{text}\n",
                    encoding="utf-8")


def annotate(notes, sel):
    """構成の工程に渡す調査メモへ、選定の結果を添える。事実は足さない。"""
    out = [notes, "", "---", "## 選定（過去の記録と突き合わせた結果）",
           f"- 今日の切り口: {sel.get('focus', '')}"]
    if sel.get("use"):
        out += ["- 使う論点:"] + [f"  - {x}" for x in sel["use"]]
    if sel.get("avoid"):
        out += ["- 避ける論点（過去と同じ角度になるため）:"] + [f"  - {x}" for x in sel["avoid"]]
    return "\n".join(out)


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
    # research.md が既に置いてあれば（NotebookLM などで人が用意した調査メモ）、それを使い
    # web 検索はしない。無ければ従来どおり Anthropic の web_search で調べる。
    # どちらでも以降は変わらない。「この調査メモだけを根拠に構成する」ことは同じで、
    # review.py が原稿と突き合わせる相手も同じ research.md のまま。
    research_path = day_dir / "research.md"
    verdict = ""
    supplied = ""
    if research_path.exists() and os.environ.get("FORCE_WEB_RESEARCH", "").strip() != "1":
        supplied = research_path.read_text(encoding="utf-8").strip()

    if supplied:
        research_source = "supplied"
        notes = supplied
        if len(notes) < 200:
            raise SystemExit(
                f"{research_path} が短すぎます（{len(notes)}字）。中断します。\n"
                "NotebookLM の要約を貼り忘れていないか確認してください。")
        urls = sorted(set(re.findall(r"https?://[^\s<>\"'）」】、。]+", notes)))
        if len(urls) < 2:
            raise SystemExit(
                f"{research_path} の出典URLが {len(urls)} 件です（2件以上必要）。\n"
                "このまま進めても validate.py で必ず止まるため、ここで中断します。\n"
                "NotebookLM の出力に出典URLを含めてください（NOTEBOOKLM.md を参照）。")
        print(f"[調査] {research_path} を使います"
              f"（{len(notes)}字 / 出典URL {len(urls)}件 / web検索はしません）")

        # ---- 過去の記録と突き合わせ、今日使う素材を選ぶ ----
        digests = load_digests(day_dir, int(os.environ.get("DIGEST_DAYS", "7") or 7))
        past = ("\n\n".join(f"### {d}\n{t}" for d, t in digests)
                if digests else "（過去の記録はまだありません）")
        print(f"[選定] 過去 {len(digests)} 日ぶんの記録と突き合わせ中…")
        res_s = call({
            "model": model, "max_tokens": 2000,
            "system": RULES,
            "tools": [{"name": "emit_selection",
                       "description": "過去の記録と突き合わせ、今日使う素材を選定する",
                       "input_schema": SELECT_SCHEMA}],
            "tool_choice": {"type": "tool", "name": "emit_selection"},
            "messages": [{"role": "user", "content": (
                f"今日は{date_s}です。今日の調査メモと、過去に投稿した日の記録があります。\n\n"
                "過去の記録と突き合わせ、今日の朝刊3分で使う素材を選定してください。\n\n"
                "判定の基準は、この調査メモだけで5枚の型を埋められるかどうかです。\n"
                "  1枚目 結論の見出しと、数字を1つ\n"
                "  2枚目 日付・金額・水準を含む事実3つ\n"
                "  3枚目 因果を3段階で説明できるだけの材料\n"
                "  4枚目 項目名・数値・単位がそろった数字4つ\n"
                "  5枚目 生活への影響3つと、反対意見1つ\n"
                "すべて埋まるなら sufficient、一部足りないなら thin、"
                "過去と同じ角度の焼き直しばかりで使える素材が実質ないなら none です。\n\n"
                "既に扱ったテーマでも、新しい進展があるなら続報として扱ってかまいません。"
                "同じ角度の繰り返しになるものだけを avoid に入れてください。\n\n"
                f"--- 過去の記録 ---\n{past}\n\n"
                f"--- 今日の調査メモ ---\n{notes[:30000]}")}],
        }, key)
        blk = next((b for b in res_s["content"] if b.get("type") == "tool_use"), None)
        if not blk:
            raise SystemExit("選定に失敗しました。\n" + json.dumps(res_s)[:2000])
        sel = blk["input"]
        verdict = sel.get("verdict", "thin")
        print(f"  判定: {verdict} — {sel.get('reason', '')}")
        if sel.get("avoid"):
            print(f"  過去と同じ角度のため避ける論点: {len(sel['avoid'])}件")
        (day_dir / "selection.json").write_text(
            json.dumps(sel, ensure_ascii=False, indent=2), encoding="utf-8")

        # ---- 素材が足りなければ web検索で補う ----
        if verdict != "sufficient" and os.environ.get("NO_WEB_SUPPLEMENT", "").strip() != "1":
            want = ("\n".join(f"- {g}" for g in (sel.get("gaps") or []))
                    or "- 5枚を埋めるための事実と数字")
            print(f"[補足] 素材が {verdict} のため web検索で補います…")
            ask2 = (f"今日は{date_s}（日本時間）です。\n\n"
                    "手元の調査メモだけでは朝刊3分の5枚を埋められません。\n"
                    "次の不足を web 検索で補い、出典URLつきの箇条書きで書き出してください。\n\n"
                    f"{want}\n\n"
                    "裏が取れなかった数字は使わず、その旨を書いてください。\n"
                    "推計や観測を、確定した事実として書かないでください。")
            if recent:
                ask2 += f"\n\n直近で扱ったテーマです。重複を避けてください:\n{recent}"
            res_w = call({
                "model": model, "max_tokens": 8000,
                "tools": [{"type": "web_search_20250305", "name": "web_search", "max_uses": 10}],
                "messages": [{"role": "user", "content": ask2}],
                "system": RULES,
            }, key)
            extra = "".join(b.get("text", "") for b in res_w["content"]
                            if b.get("type") == "text").strip()
            if len(extra) < 100:
                raise SystemExit("補足の調査結果が短すぎます。中断します。\n" + extra)
            # review.py は原稿を research.md と突き合わせる。補った分もメモに
            # 入れておかないと、正しい数字まで根拠なしと判定されてしまう。
            append_supplement(research_path, extra)
            notes = research_path.read_text(encoding="utf-8").strip()
            research_source = "supplied+web"
            print(f"  補足 {len(extra)}字を research.md に追記しました")

        notes = annotate(notes, sel)
    else:
        research_source = "web_search"
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

        print(f"[調査] {date_s} のニュースを web検索中…")
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
    print("[構成] 5枚分の原稿に組み立て中…")
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
    doc["research_source"] = research_source
    if verdict:
        doc["research_verdict"] = verdict
    doc["generated_at"] = datetime.now(timezone.utc).isoformat()

    (day_dir / "content.json").write_text(
        json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    if research_source == "web_search":
        (day_dir / "research.md").write_text(
            f"# {date_s} 調査メモ\n\n{notes}\n", encoding="utf-8")
    else:
        # 人が用意したメモ。検証のよりどころなので、加工も上書きもしない。
        print(f"  {research_path} は原文のまま残します（上書きしません）")

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
