#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""直近の投稿テーマを列挙する。generate.py に渡してネタの重複を避けるため。

    python3 scripts/recent_topics.py [件数]
    python3 scripts/recent_topics.py [件数] --digest   記録の全文を読む

--digest は digest.py が残した digest.md をまとめて表示する。
翌朝 NotebookLM に入れるソースを選ぶとき、積み残した論点と
追うべき続報をここで確認できる。
"""
import json
import sys
from pathlib import Path

args = [a for a in sys.argv[1:] if not a.startswith("-")]
n = int(args[0]) if args else 7
want_digest = "--digest" in sys.argv

if want_digest:
    days = sorted((p for p in Path("post").glob("*/") if (p / "digest.md").exists()),
                  reverse=True)[:n] if Path("post").is_dir() else []
    if not days:
        print("記録がまだありません。digest.py は投稿の後に走ります。")
    for d in days:
        print((d / "digest.md").read_text(encoding="utf-8").rstrip())
        print()
    sys.exit(0)

days = sorted((p for p in Path("post").glob("*/") if (p / "content.json").exists()),
              reverse=True)[:n] if Path("post").is_dir() else []
for d in days:
    try:
        doc = json.loads((d / "content.json").read_text(encoding="utf-8"))
    except Exception:
        continue
    topic = (doc.get("topic") or "").strip()
    if topic:
        print(f"- {d.name}: {topic}")
