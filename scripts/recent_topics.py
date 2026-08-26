#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""直近の投稿テーマを列挙する。generate.py に渡してネタの重複を避けるため。

    python3 scripts/recent_topics.py [件数]
"""
import json
import sys
from pathlib import Path

n = int(sys.argv[1]) if len(sys.argv) > 1 else 7
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
