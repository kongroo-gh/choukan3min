#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""投稿前の検査。1つでも引っかかれば異常終了し、ワークフローが投稿まで進まない。

    python3 scripts/validate.py post/2026-08-25

無人で回す以上、ここが唯一の歯止めになる。緩めないこと。
"""
import json
import re
import sys
from pathlib import Path

DISCLAIMER = "投資判断"
BANNED = [
    "必ず儲か", "絶対に儲か", "今すぐ買", "今すぐ売", "爆益", "億り人",
    "知らないと損", "情弱", "ヤバい", "衝撃の", "驚愕", "誰も教えてくれない",
    "元本保証", "確実に上がり", "確実に下が", "断言します",
]
ALLOWED_TAGS = re.compile(r"</?(?:b|em)>")
ANY_TAG = re.compile(r"<[^>]+>")

LIMITS = {"instagram": 2200, "threads": 500, "bluesky": 300}
TAG_LIMITS = {"instagram": 5, "threads": 1, "bluesky": 3}

REQUIRED_KEYS = {
    "cover": ["kicker", "title", "sub"],
    "what": ["kicker", "title", "bullets", "note"],
    "why": ["kicker", "title", "steps"],
    "numbers": ["kicker", "title", "stats"],
    "life": ["kicker", "title", "cards", "caution", "cta"],
}
ORDER = ["cover", "what", "why", "numbers", "life"]

errors, warnings = [], []


def err(m): errors.append(m)
def warn(m): warnings.append(m)


def walk_strings(o, path="$"):
    if isinstance(o, str):
        yield path, o
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from walk_strings(v, f"{path}[{i}]")
    elif isinstance(o, dict):
        for k, v in o.items():
            yield from walk_strings(v, f"{path}.{k}")


def main():
    day = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    cj = day / "content.json"
    if not cj.exists():
        raise SystemExit(f"content.json がありません: {cj}")
    doc = json.loads(cj.read_text(encoding="utf-8"))

    # --- スライド構造 ---
    slides = doc.get("slides", [])
    if len(slides) != 5:
        err(f"スライドが {len(slides)} 枚です（5枚必要）")
    for i, s in enumerate(slides[:5]):
        kind = s.get("kind")
        if kind != ORDER[i]:
            err(f"{i+1}枚目の kind が '{kind}' です（'{ORDER[i]}' であるべき）")
            continue
        for k in REQUIRED_KEYS[kind]:
            if not s.get(k):
                err(f"{i+1}枚目に '{k}' がありません")
        if kind == "what" and len(s.get("bullets", [])) != 3:
            err(f"2枚目の bullets が {len(s.get('bullets', []))} 個です（3個必要）")
        if kind == "why" and len(s.get("steps", [])) != 3:
            err(f"3枚目の steps が {len(s.get('steps', []))} 個です（3個必要）")
        if kind == "numbers":
            st = s.get("stats", [])
            if len(st) != 4:
                err(f"4枚目の stats が {len(st)} 個です（4個必要）")
            for j, row in enumerate(st):
                if not isinstance(row, list) or len(row) != 4:
                    err(f"4枚目 stats[{j}] は [項目,数値,単位,補足] の4要素である必要があります")
            ch = s.get("chart")
            if ch is not None:
                if not (2 <= len(ch) <= 5):
                    err(f"4枚目の chart は2〜5点にしてください（{len(ch)}点）")
                for j, p in enumerate(ch):
                    if not isinstance(p, list) or len(p) != 3 or not isinstance(p[1], (int, float)):
                        err(f"4枚目 chart[{j}] は [ラベル, 数値, 注記] である必要があります")
        if kind == "life":
            if len(s.get("cards", [])) != 3:
                err(f"5枚目の cards が {len(s.get('cards', []))} 個です（3個必要）")
            if len((s.get("caution") or "").strip()) < 15:
                err("5枚目の caution（反対意見・反証）が短すぎます。断定だけの投稿にしないこと")

    # --- 文字数と禁止表現とタグ ---
    for path, text in walk_strings({"slides": slides}):
        plain = ANY_TAG.sub("", text)
        if len(plain) > 220:
            warn(f"{path} が {len(plain)}字と長めです（目安180字）")
        for tag in ANY_TAG.findall(text):
            if not ALLOWED_TAGS.fullmatch(tag):
                err(f"{path} に使用禁止のタグ {tag} が含まれています")

    # --- 出典 ---
    src = doc.get("sources", [])
    if len(src) < 2:
        err(f"出典が {len(src)} 件です（2件以上必要）")
    for u in src:
        if not re.match(r"^https?://", str(u)):
            err(f"出典がURLではありません: {u!r}")

    # --- キャプション ---
    caps = doc.get("captions", {})
    for name, limit in LIMITS.items():
        txt = (caps.get(name) or "").strip()
        if not txt:
            err(f"{name} のキャプションがありません")
            continue
        if len(txt) > limit:
            err(f"{name} のキャプションが {len(txt)}字です（上限 {limit}字）")
        if DISCLAIMER not in txt:
            err(f"{name} のキャプションに免責文（投資判断〜）がありません")
        tags = re.findall(r"#[^\s#、。！？]+", txt)
        if len(tags) > TAG_LIMITS[name]:
            err(f"{name} のハッシュタグが {len(tags)}個です（上限 {TAG_LIMITS[name]}個）: {' '.join(tags)}")

    # --- 禁止表現（本文全体） ---
    whole = json.dumps(doc, ensure_ascii=False)
    for w in BANNED:
        if w in whole:
            err(f"禁止表現『{w}』が含まれています")

    # --- 画像 ---
    for folder, want in (("instagram", 5), ("bluesky", 4)):
        d = day / folder
        pngs = sorted(d.glob("*.png")) if d.is_dir() else []
        if not pngs:
            warn(f"{folder} の画像がまだありません（render.py 実行前なら正常）")
            continue
        if len(pngs) != want:
            err(f"{folder} の画像が {len(pngs)}枚です（{want}枚必要）")
        for p in pngs:
            size = p.stat().st_size
            if folder == "bluesky" and size > 976_560:
                err(f"{p.name} が {size:,}バイトで Bluesky の上限を超えています")
            if size < 8_000:
                err(f"{p.name} が {size:,}バイトしかありません。描画に失敗した可能性があります")

    # --- 結果 ---
    for w in warnings:
        print(f"注意: {w}")
    if errors:
        print("\n検査に失敗しました。投稿は行いません。")
        for e in errors:
            print(f"  エラー: {e}")
        sys.exit(1)
    print(f"検査OK（テーマ: {doc.get('topic')} / 出典 {len(src)}件 / 注意 {len(warnings)}件）")


if __name__ == "__main__":
    main()
