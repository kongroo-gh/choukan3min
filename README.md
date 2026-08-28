# 朝刊3分

経済ニュース解説アカウント「朝刊3分」を、毎朝ひとりで回すためのリポジトリです。

**はじめて置く方は [SETUP.md](SETUP.md) を先に読んでください。**

---

## 毎朝なにが起きるか

原稿づくりは**手元の Claude Code**が行い、GitHub Actions は**検査して投稿するだけ**です。
Anthropic API は使いません。**費用は $0** です。

```
前夜（Mac / Claude Code）
   │
   ├─ ① 収集      Claude Code が web検索 → sources.md（URL＋本文）
   ├─ ② 整理      Gemini（無料枠）が6項目へ → research.md
   │              書き手（Claude）と整理役を分けて、校閲の独立性を上げる
   ├─ ③ 構成      research.md だけを根拠に content.json
   ├─ ④ 画像      render.py → instagram 5枚 / bluesky 4枚
   ├─ ⑤ 関門1     validate.py（形式。API不要・確定的）
   ├─ ⑥ 関門2     原稿と research.md を突き合わせ → review.json
   └─ ⑦ commit & push
                          │
翌朝 6:35 JST（GitHub Actions）
   │
   ├─ ⑧ 原稿があるか確認   無ければ Issue を立てて休刊（ジョブは成功扱い）
   ├─ ⑨ 関門1 を再実行     validate.py
   ├─ ⑩ 関門2 の結果を確認 check_review.py
   │                       review.json が無い・fail・critical あり・
   │                       原稿と不一致 なら投稿しない
   └─ ⑪ post_bluesky.py    Bluesky へ投稿
```

Instagram と Threads は今のところ手投稿です（画像の公開URLが必要なため。SETUP.md 末尾に説明）。
Artifacts から画像とキャプションを取り出して貼ってください。

毎朝の手順は **[MORNING.md](MORNING.md)**、NotebookLM の使い方は
**[NOTEBOOKLM.md](NOTEBOOKLM.md)** にあります。

---

## 関門2 はローカルに移してある

無人で回す仕組みから人の手が入る運用に変えたため、中身の校閲もローカルで行います。
ただし**飛ばせないようにしてあります**。

`check_review.py` が Actions 側で次を確かめ、1つでも該当すれば投稿しません。

- `review.json` が無い（＝校閲を忘れた）
- `verdict` が `pass` でない、または `critical` の指摘がある
- `content_sha256` が今の `content.json` と一致しない（＝**校閲後に原稿を差し替えた**）
- `REVIEW_STRICT=1` のとき、`warning` が1件でもある

**弱点**: 本来の `review.py` は別のAPIコールで、書き手と校閲役が完全に別でした。
ローカルでは同じ機械の中で行うため、独立性はその分下がります。
`review.json` の `note` に、どういう条件で校閲したかを必ず書き残してください。

---

## 必要な Secrets

GitHub Actions 側（投稿するだけ）:

| 名前 | 用途 |
|---|---|
| `BLUESKY_HANDLE` | `economy-social.bsky.social` |
| `BLUESKY_APP_PASSWORD` | 設定 → プライバシーとセキュリティ → アプリパスワード |

手元（原稿づくり）:

| 変数 | 用途 |
|---|---|
| `GEMINI_API_KEY` | 整理。https://aistudio.google.com で**無料発行**。検索は使わないので無料枠で足りる |

`ANTHROPIC_API_KEY` は**不要**です。構成と校閲は Claude Code（契約）で行います。

---

## ディレクトリ

```
scripts/
  render.py             content.json → PNG（デザイン案C・新聞風）
                        playwright が無ければ手元の Chrome を使う
  validate.py           関門1: 形式（API不要・確定的）
  check_review.py       関門2の結果を確認（API不要・確定的）
  post_bluesky.py       Bluesky へ投稿
  selftest.py           接続確認（既定では投稿しない）
  recent_topics.py      直近のテーマ一覧
  notebooklm_prompt.py  NotebookLM に貼るプロンプトを組み立てる
  ── ここから下は API を使う旧方式。毎朝の運用では使わない ──
  generate.py           Claude API で原稿を作る
  review.py             Claude API で校閲する
  digest.py             投稿後の記録づくり
MORNING.md              毎朝の手順
NOTEBOOKLM.md           NotebookLM の使い方
.github/workflows/
  daily.yml             毎朝6:35の投稿。API不要
  bluesky-test.yml      接続テスト。単体で完結
post/YYYY-MM-DD/
  research.md      調査メモ（出典つき）。検証のよりどころ
  content.json     原稿の元データ
  review.json      関門2の結果。content.json のハッシュを含む
  instagram/01-05.png   bluesky/01-04.png
  instagram.txt  threads.txt  bluesky.txt  bluesky.alt.txt
  .posted-bluesky  投稿後に作られる。二重投稿の防止用
```

---

## 5枚の型

| 枚 | 役割 | 中身 |
|---|---|---|
| 1 | 表紙 | 結論を断定形の見出しで。サブに数字を1つ。天秤の図版 |
| 2 | 何が起きた？ | 事実を3つ。日付・金額・水準を必ず入れる |
| 3 | なぜそうなる？ | 番号つき3ステップで因果。最後に結論を一行 |
| 4 | 数字で見る | 2×2のスタット4つ＋推移チャート |
| 5 | 私たちへの影響 | 生活への影響を3枚のカード＋**反対意見**＋CTA |

X と Bluesky は画像4枚が上限のため、3枚目を落とした4枚版を別に書き出しています。

---

## 2段の関門

無人で回す以上、ここが唯一の歯止めです。緩めないでください。

### 1段目 validate.py — 形式（API不要・確定的）

- スライドの構造（5枚・順番・必須項目・要素数）
- 1枚あたりの文字数（220字を超えると注意）
- 使用可能なHTMLタグは `<b>` と `<em>` のみ
- 出典URLが2件以上あるか
- キャプションの文字数（IG 2,200／Threads 500／Bluesky 300）
- ハッシュタグの個数（IG 5／Threads 1／Bluesky 3）
- 各キャプションに免責文があるか
- 5枚目の反対意見が15字以上あるか
- 禁止表現（「必ず儲か」「今すぐ買」「知らないと損」など17語）
- 画像の枚数とファイルサイズ

### 2段目 review.json — 中身（ローカルで校閲し、CIが存在を強制）

書き手ではなく校閲者として、原稿と `research.md` を突き合わせます。

- 調査メモに存在しない数字が原稿に出ていないか
- 桁・単位・日付が食い違っていないか
- 「推計」「観測」が確定事実として書かれていないか
- 出典のない断定的な予測、投資助言と読める記述がないか

結果を `review.json` に書き、`check_review.py` が Actions 側で確認します。
`critical` が1件でもあれば投稿を中止。`review.json` が無い場合も、
校閲後に `content.json` を差し替えた場合も中止します。
`REVIEW_STRICT=1` にすると `warning` でも止まります。

**それでも防げないこと**: 調査の段階で拾った情報がそもそも誤っていた場合。
出典URLは `research.md` に残るので、気になったときは辿って確認してください。
また、書き手と校閲役が同じ機械の中にいるため、独立性は API 方式より下がります。

---

## 運用の方針

- 投資助言・銘柄推奨をしない。煽らない
- 数字は出典のある実数のみ。裏が取れないものは使わない
- 5枚目に必ず反対意見を入れる。断定だけの投稿にしない
- ネタ選定は「生活に直結し数字で語れるもの」＞「世界の動きで日本に波及するもの」＞「構造的な話題」
- 避けるもの: 個別銘柄の値動き、憶測ベースの人事、政局の細部

これらは `scripts/generate.py` の `RULES` に書かれており、毎回モデルに渡されます。
方針を変えるときはそこを直してください。

---

## 費用

| | 目安 |
|---|---|
| Anthropic API | **$0**（毎朝の運用では呼ばない） |
| GitHub Actions | 公開リポジトリなら無料・無制限 |
| Bluesky | 無料 |

原稿づくりは手元の Claude Code が行うため、Claude の契約の使用量は消費します。

API を使う旧方式（`generate.py` / `review.py`）に戻す場合は、
1日 $0.35〜0.70・月 $11〜21 が目安です。その際は Anthropic のコンソールで
月額上限を設定してください。
