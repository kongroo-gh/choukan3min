# 毎朝の手順（ローカルで作り、GitHub が投稿する）

Anthropic API を使わない運用です。原稿づくりは手元の Claude Code が行い、
GitHub Actions は検査して投稿するだけを担います。**費用は $0** です。

```
ローカル（Mac / Claude Code）                    GitHub Actions（6:35 JST）
  ① 調査      → research.md
  ② 構成      → content.json
  ③ 画像      → render.py で PNG 9枚
  ④ 関門1     → validate.py                       ⑦ 原稿があるか確認
  ⑤ 関門2     → review.json                       ⑧ 関門1を再実行 validate.py
  ⑥ commit & push  ────────────────────────→     ⑨ 関門2の結果を確認 check_review.py
                                                  ⑩ post_bluesky.py で投稿
```

原稿が無い日は投稿せず、Issue で知らせて正常終了します（休刊）。

---

## ローカルでやること

**前夜に作ります。**対象日は投稿する朝の日付（JST）なので、ディレクトリ名は翌日です。
朝の直前に作るより確実で、投稿前に目を通す余裕もできます。

### ① 調査 → sources.md → research.md

**収集は Claude Code、整理は Gemini**に分けます。

```
Claude Code   web検索して記事を集める → sources.md（URL＋本文。要約はしない）
Gemini        それを6項目に整理       → research.md
```

原稿を書くのは Claude なので、**その根拠になるメモは別のモデルに作らせます。**
校閲のとき Claude は「自分が整理していない資料」と原稿を突き合わせることになり、
数字の捏造や取り違えが捕まりやすくなります。ここが精度の要です。

Claude Code に記事を集めさせ、`post/<日付>/sources.md` にこの書式で保存します。

```markdown
## 記事の見出し
URL: https://www.example.co.jp/article
（記事本文をそのまま。要約しない）

## 次の記事の見出し
URL: https://...
```

そのうえで Gemini に整理させます。

```bash
export GEMINI_API_KEY='...'          # aistudio.google.com で無料発行
python3 scripts/gemini_research.py post/2026-08-29
```

**Gemini に検索はさせません。**Google検索グラウンディングは無料枠の対象外で、
使うと HTTP 429 になります（実測済み）。検索を Claude Code 側に置くことで
無料枠に収まり、しかも出典URLは実物のまま残ります。

整理結果に**渡していないURLが混ざっていたら中断**します。学習データから思い出した
URLを出典として書かれると、「出典があるのに検証できない」状態になるためです。

手作業で NotebookLM に整理させたい日は [NOTEBOOKLM.md](NOTEBOOKLM.md) の手順で。
どちらも使わない日は Claude が自分で調べて書きますが、**その場合は書き手と
整理役が同じになる**ので、`review.json` の `note` にそう記録してください。

### ② 構成 → content.json

`research.md` **だけ**を根拠に、5枚分の原稿と媒体別キャプションを組み立てます。
構造は `scripts/validate.py` の `REQUIRED_KEYS` が定めるとおりです。

**文字数の目安**（これを超えると画像からはみ出します。自動検査では拾えません）

| 場所 | 目安 |
|---|---|
| 1枚目 title | 各行 8〜9字 |
| 1枚目 sub | 各行 26字まで（2行） |
| 2〜5枚目 title | **12字まで**（14字で折り返して1文字だけ落ちる） |
| 2枚目 note / 3枚目 tail | 24字まで |
| 5枚目 cards の説明 | 各 30字まで |
| 5枚目 caution | 50字前後（15字未満は validate が弾く） |
| 5枚目 cta | 各行 20字まで（2行） |

キャプションの上限は Instagram 2,200字・Threads 500字・Bluesky 300字。
ハッシュタグは 5個・1個・3個まで。末尾の免責文は必須です。

**見出しで因果を断定しないでください。**本文で「とみられる」と留保しているのに
見出しだけ言い切る、という形で起きやすい失敗です（2026-08-29 の回で実際に踏みました）。
`research.md` が推計・観測として書いている因果は、見出しでも推計として扱います。

| | |
|---|---|
| 悪い例 | 「タダにしたら、入れなくなった」「無償化が需要を呼んだ」「無償化が、行き場を奪った。」 |
| 良い例 | 「無償化のあとで、待機児童が増えた」「なぜ東京だけ増えたか」「増加分は、ほぼ東京都に集中している。」 |

原則は**起きた順番や事実の並びを述べ、原因の断定を避ける**こと。問いかけの形も使えます。
`research.md` が明確な因果として書いている場合に限り、見出しでも因果として書けます。

煽り表現も使いません。`validate.py` の禁止語リストは最低限の歯止めであって、
そこに載っていなければ何を書いてもよい、という意味ではありません。

**4枚目にグラフを入れるときの注意**

- `chart` の3番目は**注記**の欄です。単位を入れると点の横に浮いて出ます
  （2026-08-29 の回で踏みました）。不要なら空文字にし、単位は `chart_caption` に書きます
- 値の幅が狭いと縦軸の目盛りが壊れます。その場合はチャートを省いてください

### ③ 画像 → PNG 9枚

```bash
python3 scripts/render.py post/2026-08-29
```

playwright が無ければ手元の Google Chrome をヘッドレスで使います（出来上がりは同じ）。

**書き出したら必ず目を通してください。**文字のはみ出しと重なりは自動検査では
拾えません。特に5枚目は要素が多く、溢れるとフッターに重なります。

### ④ 関門1 → validate.py

```bash
python3 scripts/validate.py post/2026-08-29
```

形式の検査です。API不要・確定的。ここで止まるのは正常動作です。

### ⑤ 関門2 → review.json

原稿と `research.md` を突き合わせ、結果を `post/<日付>/review.json` に書きます。

```json
{
  "verdict": "pass",
  "issues": [{"severity": "warning", "where": "2枚目", "what": "…"}],
  "note": "…",
  "content_sha256": "（content.json の sha256）"
}
```

見るところ:

- 調査メモに存在しない数字が原稿に出ていないか
- 桁・単位・日付が食い違っていないか
- 「推計」「観測」が確定事実として書かれていないか
- 出典のない断定的な予測、投資助言と読める記述がないか

`critical` が1件でもあれば `verdict` は `fail` です。ハッシュは次で作れます。

```bash
python3 -c "import hashlib;print(hashlib.sha256(open('post/2026-08-29/content.json','rb').read()).hexdigest())"
```

機械的な下調べとして、原稿の数値がすべてメモにあるかは次で確認できます。

```bash
python3 - <<'EOF'
import json, re
from pathlib import Path
d = Path("post/2026-08-29")
doc = json.loads((d/"content.json").read_text(encoding="utf-8"))
notes = (d/"research.md").read_text(encoding="utf-8")
t = re.sub(r"</?(?:b|em)>", "", json.dumps(
    {"s": doc["slides"], "c": doc["captions"]}, ensure_ascii=False))
ng = [n for n in sorted(set(re.findall(r"\d+(?:\.\d+)?", t))) if n not in notes]
print("根拠が見つからない数値:", ng or "なし")
EOF
```

ただし**これは下調べであって校閲ではありません。**桁の取り違えや、
数字は合っているが文脈が違う、といった誤りは拾えません。

### ⑥ commit & push

```bash
git add post/2026-08-29 && git commit -m "brief: 2026-08-29" && git push
```

6:35 JST までに push されていれば、その朝に投稿されます。

---

## GitHub 側がやること

`daily.yml` は Anthropic API を一切呼びません。必要な Secrets は
`BLUESKY_HANDLE` と `BLUESKY_APP_PASSWORD` の2つだけです。

| ステップ | 内容 |
|---|---|
| 原稿があるか確認 | 無ければ Issue を立てて**休刊**（ジョブは成功扱い） |
| 関門1 | `validate.py` を CI でも再実行 |
| 関門2 の確認 | `check_review.py` |
| 投稿 | `post_bluesky.py` |

### check_review.py が止める条件

- `review.json` が無い（＝校閲を忘れた）
- `verdict` が `pass` でない
- `critical` の指摘がある
- `content_sha256` が今の `content.json` と一致しない（＝**校閲後に原稿を差し替えた**）
- `REVIEW_STRICT=1` のとき、`warning` が1件でもある

関門2 をローカルへ移す代わりに、**その存在と原稿との対応を CI が強制します。**
校閲を飛ばして投稿することはできません。

---

## この運用の弱点

**校閲の独立性が下がります。**

本来の `review.py` は、書き手とは別のAPIコールで、原稿と調査メモだけを見て
校閲していました。ローカルでは同じ機械の中で行うため、書き手と校閲役が
近くなります。同一セッションで書いて自分で検算するのは、独立した校閲では
ありません。

`review.json` の `note` には、**どういう条件で校閲したのかを正直に書いてください。**
あとから記事を検証するときの手がかりになります。

これを避けたい場合は、校閲だけ別セッション（別コンテキスト）で行うか、
`ANTHROPIC_API_KEY` を設定して `review.py` に戻す選択があります。
`review.py` も同じ形式で `content_sha256` を書くので、どちらでも `check_review.py`
はそのまま機能します。

---

## 落とし穴

- **日付は投稿する朝の日付（JST）。** `TZ=Asia/Tokyo date +%F`
- **原稿を直したら校閲もやり直す。** ハッシュが変わり CI が弾きます
- **`render.py` の縦軸目盛り。** 値の幅が小さいと重複表示になります
  （例: 1.7〜1.8 で「1.8 / 1.8 / 1.7」）。幅の狭い系列はチャートを省くこと
- **`.posted-bluesky`** … これがあると二重投稿を防ぐためスキップされます
