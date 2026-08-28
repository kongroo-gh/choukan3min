#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Claude Code が集めた記事を Gemini に整理させ、調査メモ research.md を作る。

    python3 scripts/gemini_research.py post/2026-08-29
    python3 scripts/gemini_research.py --check              使えるか診断する
    python3 scripts/gemini_research.py post/... --grounding  Gemini自身に検索させる（有料枠のみ）

必要な環境変数:
    GEMINI_API_KEY   必須。https://aistudio.google.com で無料発行できる
    GEMINI_MODEL     任意（既定 gemini-3.7-flash）
    RECENT_TOPICS    任意。直近テーマを渡すとネタの重複を避ける

役割分担:
    収集  Claude Code が web検索して post/<日付>/sources.md を書く（URL＋本文）
    整理  Gemini がそれを読んで6項目のメモにする  ← このスクリプト
    構成  Claude Code が research.md から原稿を組む
    校閲  Claude Code が research.md と原稿を突き合わせる

なぜ整理だけ Gemini にやらせるか:
    原稿を書くのは Claude なので、その根拠になるメモを別ベンダーの別モデルに
    作らせる。校閲のとき Claude は「自分が整理していない資料」と原稿を突き合わせる
    ことになり、数字の捏造や取り違えが捕まりやすくなる。

なぜ Gemini に検索させないか:
    Google検索グラウンディングは無料枠の対象外（実測で HTTP 429）。
    検索は Claude Code 側で行い、Gemini には本文を渡すだけにすれば無料枠で足りる。
    渡した URL をそのまま使わせるので、リダイレクトURLの失効問題も起きない。
    --grounding を付けると旧方式で動くが、有料枠が要る。

捏造対策:
    整理結果に sources.md へ渡していない URL が現れたら中断する。
    検証できない出典が原稿に流れ込むのを防ぐため。

標準ライブラリのみ。依存を増やさないこと。
"""
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

JST = timezone(timedelta(hours=9))
ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0 Safari/537.36"

ASK_SOURCES = """今日は{date}（日本時間）です。
あなたは日本語の経済ニュース解説アカウント「朝刊3分」の調査担当です。

このあとに、収集済みの記事本文をそのまま貼ります。
**その本文だけを根拠に**、扱う『今日の1本』を1つ選び、次の6項目に整理してください。
自分の知識で補ってはいけません。書かれていないことは書かないでください。

1. 何が起きたか（日付・金額・水準などの具体的な数字を必ず含める）
2. なぜそうなるのか（因果を3段階で）
3. 押さえるべき数字4つ（項目名・数値・単位・補足）
4. 数値の推移があればその系列（2〜5点、日付と値）
5. 生活への影響3つ
6. この見方への反論・反証を1つ

厳守すること:
- 各項目の末尾に、根拠にした記事の URL を https:// から始まる形でそのまま書く。
  渡した本文の「URL:」行にある文字列をそのまま使うこと。作ってはいけない。
- 出典URLは全体で最低2件。
- 本文に無い数字を書かない。裏が取れないものは「裏が取れず」と明記する。
- 記事どうしで数字が食い違う場合は、両方の値と出典を併記する。どちらかに寄せない。
- 推計・観測にすぎないものを、確定した事実として書かない。
- 投資助言・銘柄推奨はしない。煽らない。

ネタ選びの優先順位:
  生活に直結し数字で語れるもの ＞ 世界の動きで日本に波及するもの ＞ 構造的な話題
避けるもの: 個別銘柄の値動き、憶測ベースの人事、政局の細部
"""

ASK_GROUNDING = """今日は{date}（日本時間）です。
あなたは日本語の経済ニュース解説アカウント「朝刊3分」の調査担当です。

今日の日本と世界の経済ニュースを Google 検索で調べ、扱う『今日の1本』を1つ選んでください。
日本国内の話題と世界の話題のバランスを意識してください。

選んだら、次の6項目を箇条書きで書き出してください。

1. 何が起きたか（日付・金額・水準などの具体的な数字を必ず含める）
2. なぜそうなるのか（因果を3段階で）
3. 押さえるべき数字4つ（項目名・数値・単位・補足）
4. 数値の推移があればその系列（2〜5点、日付と値）
5. 生活への影響3つ
6. この見方への反論・反証を1つ

厳守すること:
- 各項目の末尾に、根拠にした情報源のURLを https:// から始まる形でそのまま書く。
- 検索で確認できなかった数字は書かない。裏が取れないものは「裏が取れず」と明記する。
- 情報源どうしで数字が食い違う場合は、両方の値と出典を併記する。どちらかに寄せない。
- 推計・観測にすぎないものを、確定した事実として書かない。
- 投資助言・銘柄推奨はしない。煽らない。

ネタ選びの優先順位:
  生活に直結し数字で語れるもの ＞ 世界の動きで日本に波及するもの ＞ 構造的な話題
避けるもの: 個別銘柄の値動き、憶測ベースの人事、政局の細部
"""


def call(model, key, prompt, search=False):
    body = {"contents": [{"parts": [{"text": prompt}]}]}
    if search:
        # グラウンディングは無料枠の対象外（実測: HTTP 429）。有料化した場合のみ使える。
        body["tools"] = [{"google_search": {}}]
    req = urllib.request.Request(
        ENDPOINT.format(model=model), data=json.dumps(body).encode(),
        headers={"x-goog-api-key": key, "content-type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")
        hint = ""
        if e.code in (400, 404):
            hint = ("\nモデル名が使えない可能性があります。"
                    "GEMINI_MODEL で変更してください（無料枠は Flash / Flash-Lite 系）。")
        elif e.code == 429:
            hint = "\n無料枠のレート制限に達しています。時間をおいて再実行してください。"
        raise SystemExit(f"[Gemini API エラー] HTTP {e.code}\n{detail}{hint}")


def resolve(url):
    """リダイレクトURLを実際の記事URLまで辿る。失敗したら元のURLを返す。"""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.url or url
    except Exception:
        return url


def http(url, key, body=None):
    """成功なら (True, JSON)、失敗なら (False, "HTTP xxx: …") を返す。例外を投げない。"""
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url, data=data,
        headers={"x-goog-api-key": key, "content-type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return True, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        raw = e.read().decode(errors="replace")
        try:
            msg = json.loads(raw)["error"]["message"]
        except Exception:
            msg = raw[:200]
        return False, f"HTTP {e.code}: {msg}"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def check(key, model):
    """429 の原因を切り分ける。モデルが使えないのか、検索が使えないのか。"""
    print("=" * 60)
    print("1. このキーで見えるモデルを列挙します")
    ok, res = http("https://generativelanguage.googleapis.com/v1beta/models", key)
    if not ok:
        print(f"   取得できませんでした: {res}")
    else:
        names = []
        for m in res.get("models", []):
            n = m.get("name", "").replace("models/", "")
            if "generateContent" in (m.get("supportedGenerationMethods") or []):
                names.append(n)
        flash = [n for n in names if "flash" in n or "lite" in n]
        print(f"   generateContent 対応 {len(names)} 件")
        print("   Flash / Lite 系:")
        for n in sorted(flash):
            print(f"     {n}")
        if model.replace("models/", "") not in names:
            print(f"   ※ 指定中の {model} は一覧にありません")

    url = ENDPOINT.format(model=model)
    tiny = {"contents": [{"parts": [{"text": "1+1は？"}]}],
            "generationConfig": {"maxOutputTokens": 16}}

    print()
    print(f"2. {model} に検索なしで1回投げます（最小のリクエスト）")
    ok1, res1 = http(url, key, tiny)
    print("   成功" if ok1 else f"   失敗 {res1}")

    print()
    print(f"3. {model} に google_search つきで1回投げます")
    ok2, res2 = http(url, key, dict(tiny, tools=[{"google_search": {}}]))
    print("   成功" if ok2 else f"   失敗 {res2}")

    print()
    print("=" * 60)
    if ok1 and ok2:
        print("結論: どちらも通ります。先ほどの 429 は一時的なものです。")
        print("      そのまま再実行してください。")
    elif ok1 and not ok2:
        print("結論: モデルは使えますが、Google検索グラウンディングが使えません。")
        print("      無料枠では検索ツールが対象外の可能性が高いです。")
        print("      → 検索なしで調査させることはできません（出典が取れないため）。")
        print("      → NotebookLM で手作業（NOTEBOOKLM.md）か、")
        print("        Claude Code に調べさせる方式に戻すのが現実的です。")
    elif not ok1:
        print("結論: このモデル自体が今のキーで使えません。")
        print("      上の一覧から別のモデルを選び、GEMINI_MODEL で指定してください。")
        print("      例: GEMINI_MODEL=<一覧の名前> python3 scripts/gemini_research.py ...")
    print("実際の残量は https://ai.dev/rate-limit で確認できます。")
    return 0


def from_sources(day_dir, date_s, model, key, recent):
    """Claude Code が集めた記事本文 sources.md を、Gemini に6項目へ整理させる。

    検索は Claude Code 側が済ませてある。Gemini は要約と取捨選択だけを行う。
    原稿を書くのは Claude なので、その根拠になるメモを別のモデルに作らせることで、
    校閲のとき「自分が整理していない資料」と突き合わせる形になる。
    """
    src = day_dir / "sources.md"
    if not src.exists():
        raise SystemExit(
            f"{src} がありません。\n"
            "先に Claude Code に記事を集めさせてください（MORNING.md の①）。\n"
            "書式は『## 見出し / URL: https://… / 本文』の繰り返し。")
    material = src.read_text(encoding="utf-8").strip()
    src_urls = sorted(set(re.findall(r"https?://[^\s<>\"'）」】、。]+", material)))
    if len(src_urls) < 2:
        raise SystemExit(
            f"{src} の URL が {len(src_urls)} 件しかありません（2件以上必要）。")
    print(f"[調査] {src} を Gemini（{model}）で整理中… "
          f"（{len(material)}字 / URL {len(src_urls)}件）")

    prompt = ASK_SOURCES.format(date=date_s)
    if recent:
        prompt += ("\n直近で扱ったテーマです。同じ角度の繰り返しは避けてください。\n"
                   "新しい進展がある続報なら扱ってかまいません。\n" + recent + "\n")
    prompt += "\n\n--- ここから収集済みの記事本文 ---\n\n" + material

    res = call(model, key, prompt, search=False)
    cands = res.get("candidates") or []
    if not cands:
        raise SystemExit("Gemini から候補が返りませんでした。\n"
                         + json.dumps(res, ensure_ascii=False)[:2000])
    notes = "".join(p.get("text", "") for p in
                    (cands[0].get("content", {}).get("parts") or [])).strip()
    if len(notes) < 200:
        raise SystemExit(f"整理結果が短すぎます（{len(notes)}字）。中断します。\n{notes}")

    urls = sorted(set(re.findall(r"https?://[^\s<>\"'）」】、。]+", notes)))
    made_up = [u for u in urls if u not in src_urls]
    if len(urls) < 2:
        raise SystemExit(
            f"整理結果の出典URLが {len(urls)} 件しかありません（2件以上必要）。\n"
            "このまま進めても validate.py で必ず止まるため、ここで中断します。")
    if made_up:
        # 渡していないURLが出てきたら、作られた疑いがある。検証できないので止める。
        raise SystemExit(
            "渡していないURLが整理結果に含まれています。捏造の疑いがあるため中断します。\n"
            + "\n".join(f"  {u}" for u in made_up))

    text = "\n".join([
        f"# {date_s} 調査メモ", "",
        f"作成: Gemini（{model}）が sources.md を整理したもの。web検索はしていない。",
        "記事の収集は Claude Code、整理は Gemini、原稿と校閲は Claude。",
        "根拠となるこのメモを別のモデルが作ることで、校閲の独立性を確保している。",
        "", notes, ""])
    (day_dir / "research.md").write_text(text + "\n", encoding="utf-8")
    u = res.get("usageMetadata", {})
    print(f"  完了（{len(notes)}字 / 出典URL {len(urls)}件 / すべて sources.md 由来 / "
          f"in {u.get('promptTokenCount')} out {u.get('candidatesTokenCount')}）")
    print(f"→ {day_dir}/research.md")
    return 0


def main():
    day_dir = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    day_dir.mkdir(parents=True, exist_ok=True)
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        raise SystemExit(
            "GEMINI_API_KEY が未設定です。\n"
            "https://aistudio.google.com でキーを発行してください（無料枠あり）。\n"
            "  export GEMINI_API_KEY='...'")
    model = os.environ.get("GEMINI_MODEL", "gemini-3.7-flash").strip()
    if "--check" in sys.argv:
        return check(key, model)
    date_s = (day_dir.name if re.match(r"^\d{4}-\d{2}-\d{2}$", day_dir.name)
              else datetime.now(JST).strftime("%Y-%m-%d"))

    recent = os.environ.get("RECENT_TOPICS", "").strip()
    if "--grounding" not in sys.argv:
        return from_sources(day_dir, date_s, model, key, recent)

    # 以下は Google検索グラウンディングを使う旧方式。無料枠では 429 になる。
    prompt = ASK_GROUNDING.format(date=date_s)
    if recent:
        prompt += ("\n直近で扱ったテーマです。同じ角度の繰り返しは避けてください。\n"
                   "新しい進展がある続報なら扱ってかまいません。\n" + recent + "\n")

    print(f"[調査] {date_s} のニュースを Gemini（{model}）で調査中…")
    res = call(model, key, prompt, search=True)

    cands = res.get("candidates") or []
    if not cands:
        raise SystemExit("Gemini から候補が返りませんでした。\n" + json.dumps(res, ensure_ascii=False)[:2000])
    cand = cands[0]
    notes = "".join(p.get("text", "") for p in
                    (cand.get("content", {}).get("parts") or [])).strip()
    if len(notes) < 200:
        raise SystemExit(f"調査結果が短すぎます（{len(notes)}字）。中断します。\n{notes}")

    # グラウンディングが示した情報源を、実URLへ解決して集める
    chunks = (cand.get("groundingMetadata") or {}).get("groundingChunks") or []
    seen, sources = set(), []
    for c in chunks:
        w = c.get("web") or {}
        uri, title = w.get("uri"), (w.get("title") or "").strip()
        if not uri:
            continue
        real = resolve(uri)
        if real in seen:
            continue
        seen.add(real)
        sources.append((real, title, real != uri))
    print(f"  情報源 {len(sources)} 件（うち実URLへ解決できたもの "
          f"{sum(1 for _, _, ok in sources if ok)} 件）")

    body = [f"# {date_s} 調査メモ", "",
            f"作成: Gemini（{model}）の Google検索グラウンディング。",
            "原稿を書くのは Claude なので、根拠となるこのメモは別ベンダーのモデルが作っている。",
            "", notes, ""]
    if sources:
        body += ["", "## グラウンディングが参照した情報源", ""]
        for url, title, resolved in sources:
            mark = "" if resolved else "（リダイレクトURLのまま。失効する可能性あり）"
            body.append(f"- {title or '(題名なし)'}{mark}")
            body.append(f"  {url}")

    text = "\n".join(body)
    urls = sorted(set(re.findall(r"https?://[^\s<>\"'）」】、。]+", text)))
    if len(urls) < 2:
        raise SystemExit(
            f"調査メモの出典URLが {len(urls)} 件しかありません（2件以上必要）。\n"
            "このまま進めても validate.py で必ず止まるため、ここで中断します。")

    (day_dir / "research.md").write_text(text + "\n", encoding="utf-8")
    u = res.get("usageMetadata", {})
    print(f"  完了（{len(notes)}字 / 出典URL {len(urls)}件 / "
          f"in {u.get('promptTokenCount')} out {u.get('candidatesTokenCount')}）")
    print(f"→ {day_dir}/research.md")


if __name__ == "__main__":
    sys.exit(main() or 0)
