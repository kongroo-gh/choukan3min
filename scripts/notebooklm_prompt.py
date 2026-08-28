#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""NotebookLM に貼り付けるプロンプトを組み立てて表示する。

    python3 scripts/notebooklm_prompt.py 2026-08-29
    python3 scripts/notebooklm_prompt.py 2026-08-29 | pbcopy   # そのままコピー

対象日と直近の投稿テーマを埋め込んだ状態で出力するので、
毎回書き換える必要がない。直近テーマを渡すのはネタの重複を避けるため。

NotebookLM には API が無く、ソースの追加とプロンプトの実行は人が行う。
このスクリプトはその手間を減らすためだけのもので、通信は一切しない。
"""
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

JST = timezone(timedelta(hours=9))

BODY = """あなたは日本語の経済ニュース解説アカウント「朝刊3分」の調査担当です。
{date} 朝に配信する回の元ネタを作ります。

このノートブックに追加したソースだけを根拠に、扱う『今日の1本』を1つ選び、
次の6項目を箇条書きで書き出してください。

1. 何が起きたか（日付・金額・水準などの具体的な数字を必ず含める）
2. なぜそうなるのか（因果を3段階で）
3. 押さえるべき数字4つ（項目名・数値・単位・補足）
4. 数値の推移があればその系列（2〜5点、日付と値）
5. 生活への影響3つ
6. この見方への反論・反証を1つ

厳守すること:
- 各項目の末尾に、根拠にしたソースのURLを https:// から始まる形でそのまま書く。
  [1] のような番号だけの引用にせず、URL文字列を必ず本文中に出す。
- 出典URLは全体で最低2件、できれば3件以上。
- ソースに書かれていない数字を書かない。裏が取れないものは「裏が取れず」と明記する。
- ソースどうしで数字が食い違う場合は、両方の値と出典を併記する。どちらかに寄せない。
- 推計・観測にすぎないものを確定した事実として書かない。
- 投資助言・銘柄推奨はしない。煽らない。

ネタ選びの優先順位:
  生活に直結し数字で語れるもの ＞ 世界の動きで日本に波及するもの ＞ 構造的な話題
避けるもの: 個別銘柄の値動き、憶測ベースの人事、政局の細部
"""

DEDUP = """
直近で扱ったテーマです。同じ角度の繰り返しは避けてください。
新しい進展がある続報なら扱ってかまいません。
{topics}
"""


def recent(root, n=7, skip=None):
    if not root.is_dir():
        return []
    days = sorted((p for p in root.iterdir()
                   if p.is_dir() and p.name != skip and (p / "content.json").exists()),
                  reverse=True)[:n]
    out = []
    for d in days:
        try:
            doc = json.loads((d / "content.json").read_text(encoding="utf-8"))
        except ValueError:
            continue
        t = (doc.get("topic") or "").strip()
        if t:
            out.append(f"- {d.name}: {t}")
    return out


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    if args and re.match(r"^\d{4}-\d{2}-\d{2}$", args[0]):
        date_s = args[0]
    else:
        # 引数が無ければ「翌朝」を既定にする。前夜に用意する運用のため。
        date_s = (datetime.now(JST) + timedelta(days=1)).strftime("%Y-%m-%d")

    text = BODY.format(date=date_s)
    topics = recent(Path("post"), 7, skip=date_s)
    if topics:
        text += DEDUP.format(topics="\n".join(topics))

    sys.stdout.write(text)
    if sys.stdout.isatty():
        print()
        print("─" * 60)
        print(f"対象日: {date_s}")
        print("1. NotebookLM にソース（ニュースのURL）を『ウェブサイト』として追加")
        print("2. 上のプロンプトを貼って実行")
        print("3. 出力を保存:")
        print(f"     mkdir -p post/{date_s} && pbpaste > post/{date_s}/research.md")
        print(f"     grep -c 'https\\?://' post/{date_s}/research.md   # 2以上であること")


if __name__ == "__main__":
    main()
