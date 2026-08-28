#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""校閲結果 review.json を検査する。API不要・確定的。

    python3 scripts/check_review.py post/2026-08-28

原稿をローカルで作る運用では、関門2（中身の校閲）もローカルで行う。
このスクリプトは、その結果が確かに存在し、原稿と対応していることを
GitHub Actions 側で機械的に確かめるためのもの。校閲そのものは行わない。

これが無いと「校閲を忘れたまま投稿する」「校閲後に原稿だけ差し替える」が
素通りしてしまう。関門2 をローカルへ移す代わりに、ここで存在を強制する。

止める条件:
    review.json が無い
    verdict が pass でない
    critical の指摘が1件でもある
    content_sha256 が今の content.json と一致しない（校閲後に原稿が変わった）
    REVIEW_STRICT=1 のとき、warning が1件でもある
"""
import hashlib
import json
import os
import sys
from pathlib import Path


def main():
    day = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    content = day / "content.json"
    review = day / "review.json"

    if not content.exists():
        raise SystemExit(f"content.json がありません: {content}")
    if not review.exists():
        raise SystemExit(
            f"review.json がありません: {review}\n"
            "関門2（中身の校閲）が行われていません。投稿しません。\n"
            "ローカルで校閲を行い、review.json を commit してください。")

    try:
        out = json.loads(review.read_text(encoding="utf-8"))
    except ValueError as e:
        raise SystemExit(f"review.json を読めません: {e}")

    verdict = out.get("verdict")
    issues = out.get("issues") or []
    crit = [i for i in issues if i.get("severity") == "critical"]
    warns = [i for i in issues if i.get("severity") == "warning"]

    # 校閲したあとに原稿を差し替えていないか
    want = out.get("content_sha256")
    have = hashlib.sha256(content.read_bytes()).hexdigest()
    if not want:
        raise SystemExit(
            "review.json に content_sha256 がありません。\n"
            "どの原稿を校閲したのか確かめられないため、投稿しません。")
    if want != have:
        raise SystemExit(
            "校閲したあとに content.json が変更されています。投稿しません。\n"
            f"  校閲時: {want}\n"
            f"  現在  : {have}\n"
            "原稿を直したなら、校閲もやり直してください。")

    for i in warns:
        print(f"注意 [{i.get('where')}] {i.get('what')}")
    if out.get("note"):
        print(f"所見: {out['note']}")

    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write(f"### 校閲結果（ローカルで実施）: {verdict}\n\n")
            if out.get("note"):
                f.write(f"{out['note']}\n\n")
            for i in issues:
                f.write(f"- **{i.get('severity')}** [{i.get('where')}] {i.get('what')}\n")
            if not issues:
                f.write("指摘なし。\n")

    if crit:
        print("\n校閲で重大な指摘が出ています。投稿は行いません。")
        for i in crit:
            print(f"  critical [{i.get('where')}] {i.get('what')}")
        sys.exit(1)
    if verdict != "pass":
        raise SystemExit(f"verdict が '{verdict}' です（pass でなければ投稿しません）。")
    if warns and os.environ.get("REVIEW_STRICT") == "1":
        print("\nREVIEW_STRICT=1 のため、警告でも中断します。")
        sys.exit(1)

    print(f"校閲の確認OK（重大 0件 / 注意 {len(warns)}件 / 原稿と一致）")


if __name__ == "__main__":
    main()
