#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bluesky の接続確認。既定では投稿しない。

    # 認証と画像アップロードだけ確認する（投稿されません）
    python3 scripts/selftest.py post/2026-08-25

    # 実際にテスト投稿する
    python3 scripts/selftest.py post/2026-08-25 --post

何を確かめるか:
    1. ハンドルとアプリパスワードでログインできるか
    2. 画像4枚をアップロードできるか（サイズ上限・認証）
    3. 投稿レコードが仕様どおり組み立てられるか

1〜3 はすべて公開されません。アップロードした画像も、
投稿レコードから参照されない限り誰にも見えません。
--post を付けたときだけ createRecord を呼び、実際に投稿されます。

必要な環境変数:
    BLUESKY_HANDLE          例: economy-social.bsky.social
    BLUESKY_APP_PASSWORD    アプリパスワード（ログインパスワードではない）
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from post_bluesky import api, png_size, build_facets, MAX_BLOB_BYTES, MAX_GRAPHEMES  # noqa: E402


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    do_post = "--post" in sys.argv
    day = Path(args[0] if args else ".")

    handle = os.environ.get("BLUESKY_HANDLE", "").strip().lstrip("@")
    password = os.environ.get("BLUESKY_APP_PASSWORD", "").strip()
    if not handle or not password:
        raise SystemExit(
            "BLUESKY_HANDLE と BLUESKY_APP_PASSWORD を環境変数で渡してください。\n\n"
            "  export BLUESKY_HANDLE=economy-social.bsky.social\n"
            "  export BLUESKY_APP_PASSWORD='xxxx-xxxx-xxxx-xxxx'\n"
            "  python3 scripts/selftest.py post/2026-08-25\n")

    print("── 1. ログイン ──")
    print(f"   ハンドル: {handle}")
    sess = api("com.atproto.server.createSession",
               {"identifier": handle, "password": password})
    token, did = sess["accessJwt"], sess["did"]
    print(f"   成功。DID: {did}")
    if sess.get("handle") and sess["handle"] != handle:
        print(f"   注意: サーバー上のハンドルは {sess['handle']} です")

    print("\n── 2. 本文 ──")
    text = (day / "bluesky.txt").read_text(encoding="utf-8").strip()
    print(f"   {len(text)} 文字 / 上限 {MAX_GRAPHEMES}")
    if len(text) > MAX_GRAPHEMES:
        raise SystemExit("   本文が長すぎます。")
    facets = build_facets(text)
    b = text.encode("utf-8")
    for f in facets:
        i = f["index"]
        seg = b[i["byteStart"]:i["byteEnd"]].decode("utf-8")
        kind = f["features"][0]["$type"].rsplit("#", 1)[-1]
        print(f"   リンク化: {seg}  ({kind})")

    print("\n── 3. 画像のアップロード ──")
    images = sorted((day / "bluesky").glob("*.png"))
    if not images:
        raise SystemExit(f"   画像が見つかりません: {day}/bluesky/*.png")
    alts = []
    ap = day / "bluesky.alt.txt"
    if ap.exists():
        alts = [x.strip() for x in ap.read_text(encoding="utf-8").splitlines() if x.strip()]

    embeds = []
    for i, p in enumerate(images):
        raw = p.read_bytes()
        wh = png_size(p)
        if len(raw) > MAX_BLOB_BYTES:
            raise SystemExit(f"   {p.name} が大きすぎます（{len(raw):,} / {MAX_BLOB_BYTES:,}）")
        res = api("com.atproto.repo.uploadBlob", token=token, blob=raw, content_type="image/png")
        embeds.append({"alt": alts[i] if i < len(alts) else f"スライド{i+1}枚目",
                       "image": res["blob"],
                       "aspectRatio": {"width": wh[0], "height": wh[1]} if wh else None})
        print(f"   {p.name}  {len(raw):>7,}バイト  {wh[0]}×{wh[1]}  → アップロード成功")

    print("\n── 4. 投稿レコードの組み立て ──")
    record = {"$type": "app.bsky.feed.post", "text": text,
              "createdAt": "(投稿時に生成)", "langs": ["ja"], "facets": facets,
              "embed": {"$type": "app.bsky.embed.images", "images": embeds}}
    print(f"   画像 {len(embeds)} 枚 / facets {len(facets)} 件 / langs ja")
    print(f"   レコードのサイズ: {len(json.dumps(record, ensure_ascii=False)):,} バイト")

    if not do_post:
        print("\n────────────────────────────────")
        print("接続確認はすべて成功しました。投稿はしていません。")
        print("実際に投稿するには --post を付けて再実行してください:")
        print(f"  python3 scripts/selftest.py {day} --post")
        return

    print("\n── 5. 投稿 ──")
    from datetime import datetime, timezone
    record["createdAt"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    out = api("com.atproto.repo.createRecord", token=token, payload={
        "repo": did, "collection": "app.bsky.feed.post", "record": record})
    rkey = out["uri"].rsplit("/", 1)[-1]
    print(f"   投稿しました: https://bsky.app/profile/{handle}/post/{rkey}")
    print(f"\n   消したいときは Bluesky アプリから削除してください。")
    print(f"   （このリポジトリで運用を始める前に消しておくと履歴がきれいです）")


if __name__ == "__main__":
    main()
