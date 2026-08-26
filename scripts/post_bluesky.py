#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bluesky へ画像つき投稿を行う。

使い方:
    python3 scripts/post_bluesky.py post/2026-08-25

必要な環境変数（GitHub Secrets から渡す）:
    BLUESKY_HANDLE        例: choukan3min.bsky.social
    BLUESKY_APP_PASSWORD  設定 → プライバシーとセキュリティ → アプリパスワード で発行したもの
                          （通常のログインパスワードは使わないこと）

投稿ディレクトリの構成:
    post/YYYY-MM-DD/
        bluesky.txt        本文（300グラフェム以内）
        bluesky/01.png     画像（最大4枚。ファイル名順に並ぶ）
        bluesky/02.png
        ...
        bluesky.alt.txt    任意。1行1枚の代替テキスト
"""
import json
import os
import re
import sys
import struct
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

PDS = os.environ.get("BLUESKY_PDS", "https://bsky.social")
MAX_IMAGES = 4
MAX_BLOB_BYTES = 976_560   # Bluesky の実際の上限（約 976KB）
MAX_GRAPHEMES = 300


def api(path, payload=None, token=None, blob=None, content_type=None):
    url = f"{PDS}/xrpc/{path}"
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if blob is not None:
        data, headers["Content-Type"] = blob, content_type
    elif payload is not None:
        data = json.dumps(payload).encode()
        headers["Content-Type"] = "application/json"
    else:
        data = None
    req = urllib.request.Request(url, data=data, headers=headers,
                                 method="POST" if data is not None else "GET")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        raise SystemExit(f"[Bluesky API エラー] {path} → HTTP {e.code}\n{body}")


def png_size(path: Path):
    """PNG のヘッダから幅・高さを読む（外部ライブラリなし）。"""
    with open(path, "rb") as f:
        head = f.read(24)
    if head[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    w, h = struct.unpack(">II", head[16:24])
    return w, h


def build_facets(text: str):
    """ハッシュタグとURLをリンク化する。オフセットは UTF-8 のバイト位置。"""
    facets = []
    b = text.encode("utf-8")

    for m in re.finditer(r"#([^\s#、。！？「」（）]+)", text):
        tag = m.group(1)
        if not tag or len(tag) > 64:
            continue
        start = len(text[:m.start()].encode("utf-8"))
        end = start + len(m.group(0).encode("utf-8"))
        facets.append({
            "index": {"byteStart": start, "byteEnd": end},
            "features": [{"$type": "app.bsky.richtext.facet#tag", "tag": tag}],
        })

    for m in re.finditer(r"https?://[^\s、。「」（）]+", text):
        uri = m.group(0).rstrip(".,)")
        start = len(text[:m.start()].encode("utf-8"))
        end = start + len(uri.encode("utf-8"))
        facets.append({
            "index": {"byteStart": start, "byteEnd": end},
            "features": [{"$type": "app.bsky.richtext.facet#link", "uri": uri}],
        })

    assert len(b) >= 0
    return facets


def main():
    if len(sys.argv) < 2:
        raise SystemExit("使い方: post_bluesky.py <投稿ディレクトリ>")
    day = Path(sys.argv[1])
    # 先頭の @ は API の identifier では受け付けられないので落とす。
    # Secrets に "@economy-social.bsky.social" と入れてしまっても動くようにするため。
    handle = os.environ.get("BLUESKY_HANDLE", "").strip().lstrip("@")
    password = os.environ.get("BLUESKY_APP_PASSWORD", "").strip()
    if not handle or not password:
        raise SystemExit("BLUESKY_HANDLE と BLUESKY_APP_PASSWORD が未設定です。"
                         "リポジトリの Settings → Secrets and variables → Actions で登録してください。")

    text_path = day / "bluesky.txt"
    if not text_path.exists():
        raise SystemExit(f"本文が見つかりません: {text_path}")
    text = text_path.read_text(encoding="utf-8").strip()
    if len(text) > MAX_GRAPHEMES:
        raise SystemExit(f"本文が {len(text)} 文字です。Bluesky の上限は {MAX_GRAPHEMES} 文字。短くしてください。")

    img_dir = day / "bluesky"
    images = sorted(img_dir.glob("*.png")) if img_dir.is_dir() else []
    if len(images) > MAX_IMAGES:
        raise SystemExit(f"画像が {len(images)} 枚あります。Bluesky の上限は {MAX_IMAGES} 枚。")

    alts = []
    alt_path = day / "bluesky.alt.txt"
    if alt_path.exists():
        alts = [ln.strip() for ln in alt_path.read_text(encoding="utf-8").splitlines() if ln.strip()]

    print(f"ログイン: {handle}")
    sess = api("com.atproto.server.createSession",
               {"identifier": handle, "password": password})
    token, did = sess["accessJwt"], sess["did"]
    print(f"  → DID {did}")

    embed_images = []
    for i, p in enumerate(images):
        raw = p.read_bytes()
        if len(raw) > MAX_BLOB_BYTES:
            raise SystemExit(f"{p.name} は {len(raw):,} バイトで上限 {MAX_BLOB_BYTES:,} を超えています。")
        print(f"アップロード: {p.name} ({len(raw):,} バイト)")
        res = api("com.atproto.repo.uploadBlob", token=token,
                  blob=raw, content_type="image/png")
        item = {
            "alt": alts[i] if i < len(alts) else f"経済ニュース解説スライド {i + 1}枚目",
            "image": res["blob"],
        }
        wh = png_size(p)
        if wh:
            item["aspectRatio"] = {"width": wh[0], "height": wh[1]}
        embed_images.append(item)

    record = {
        "$type": "app.bsky.feed.post",
        "text": text,
        "createdAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "langs": ["ja"],
        "facets": build_facets(text),
    }
    if embed_images:
        record["embed"] = {"$type": "app.bsky.embed.images", "images": embed_images}

    out = api("com.atproto.repo.createRecord", token=token, payload={
        "repo": did, "collection": "app.bsky.feed.post", "record": record,
    })
    rkey = out["uri"].rsplit("/", 1)[-1]
    url = f"https://bsky.app/profile/{handle}/post/{rkey}"
    print(f"投稿しました: {url}")

    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write(f"### Bluesky\n投稿しました → [{url}]({url})\n\n"
                    f"- 画像 {len(embed_images)} 枚\n- 本文 {len(text)} 文字\n")


if __name__ == "__main__":
    main()
