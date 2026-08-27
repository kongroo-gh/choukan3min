# 朝刊3分 — プロジェクト context

経済ニュース解説アカウント「朝刊3分」を毎朝ひとりで回すリポジトリ。
Claude Code で作業するときは、まずこのファイルを読んでから動くこと。

初回のセットアップが未完了なら **`HANDOFF.md` を読んで、そこに書かれた手順を実行する。**

---

## これは何か

毎朝6:35（JST）に GitHub Actions が起動し、次を無人で行う。

```
generate.py   Anthropic API（web_search 付き）で当日の経済ニュースを調査 → 5枚分の原稿
render.py     原稿 → PNG 9枚（Instagram 5枚 / Bluesky 4枚）
validate.py   【関門1】形式の検査。API不要・確定的
review.py     【関門2】中身の校閲。原稿を調査メモと突き合わせる別のAPIコール
post_bluesky.py   Bluesky へ投稿
```

Bluesky のみ自動投稿。Instagram / Threads は未開設で、Actions の Artifacts から
取り出して手投稿する運用。

## アカウント情報

| 項目 | 値 |
|---|---|
| Bluesky ハンドル | `economy-social.bsky.social` |
| 画像フッター表記 | `@economy-social` |
| 表示名 | 朝刊3分 |
| デザイン | 案C「GAZETTE（新聞風）」生成り `#EFE9DB` ／ 赤 `#A8241F` ／ 明朝 |

第1号は手動投稿済み:
https://bsky.app/profile/economy-social.bsky.social/post/3mtx5oa6hnd25

---

## 絶対に守ること

**無人で公開される。ここを緩めると誤情報がそのまま世に出る。**

1. **2段の関門を弱めない。** `validate.py` と `review.py` のしきい値・禁止語・
   必須項目を緩めてはいけない。テストを通すために検査を甘くするのは本末転倒。
   検査で止まるのは正常動作。
2. **`AUTO_PUBLISH` を勝手に変えない。** ユーザーが明示的に指示したときだけ触る。
3. **テスト投稿を無断でしない。** `--post` や `dry_run` なしの実行は、
   ユーザーの明示的な指示があるときだけ。
4. **数字を創作しない。** `research.md` に根拠がないものは原稿に入れない。
   これはモデルへの指示（`generate.py` の `RULES`）としても書かれている。
5. **免責文を消さない。** 各キャプション末尾の「※投資判断はご自身の責任で〜」は必須。
6. **5枚目の反対意見を消さない。** 断定だけの投稿にしない方針。

## 仕様上の制約（守らないと投稿が壊れる）

| 項目 | 値 | 理由 |
|---|---|---|
| 画像 | 1080×1350（4:5） | Instagram が許容する縦長の上限 |
| Bluesky の画像 | 最大4枚・1枚 976,560 バイト以内 | AT Protocol の上限 |
| Bluesky の本文 | 300グラフェム | 同上 |
| Instagram のハッシュタグ | 最大5個 | 2025年12月から制限。増やすと有害 |
| Threads のトピックタグ | 1個のみ | 仕様 |
| カルーセル1枚目 | 必ず4:5 | IG は1枚目の比率で全カードを強制クロップ |
| Bluesky のハンドル | 先頭の `@` を除去して渡す | `identifier` は `@` を受け付けない |

4枚版は5枚から**3枚目（なぜ＝因果説明）を落とす**（`render.py` の `SHORT_IDX`）。

---

## ローカルでの動かし方

```bash
# 依存（初回のみ）
pip3 install playwright
python3 -m playwright install chromium

# 画像を書き出す
python3 scripts/render.py post/2026-08-25

# 形式を検査する（APIキー不要）
python3 scripts/validate.py post/2026-08-25

# Bluesky の接続確認（投稿しない）
export BLUESKY_HANDLE=economy-social.bsky.social
export BLUESKY_APP_PASSWORD='...'
python3 scripts/selftest.py post/2026-08-25
```

macOS には Hiragino Mincho ProN があるので明朝は出る。
Actions（Ubuntu）では `fonts-noto-cjk` を入れており、無ければ豆腐（□）になるので
ワークフローが `fc-list` で確認して落とすようになっている。

スクリプトは**すべて標準ライブラリのみ**（render.py の playwright を除く）。
依存を増やさないこと。Actions の起動が遅くなる。

---

## 変更するときの注意

- **`render.py` を触ったら必ず画像を目視する。** 文字のはみ出し・重なりは
  自動検査では拾えない。`post/<日付>/instagram/*.png` を開いて確認する。
- **`validate.py` を触ったら壊れたデータで試す。** 正常系だけ通しても意味がない。
  `content.json` をわざと壊して、期待どおり exit 1 になるか確かめる。
- **`review.py` を触ったら API をモックして試す。** pass / warning / critical /
  応答不正 / `REVIEW_STRICT` の5系統。実APIを叩く必要はない。
- **ワークフローのシェルは `bash -e`。** `[ cond ] && VAR=x` は条件不成立で
  ステップごと失敗する。`if ... fi` を使うこと（過去に踏んだ）。
- **`run: |` の中に、字下げから外れた行を書かない（過去に踏んだ）。**
  `gh issue create --body "..."` の本文を列0から続けたせいで YAML のブロックが
  そこで終わり、本文の1行がトップレベルのキーになった。GitHub は未知の
  トップレベルキーを持つワークフローを**起動前に**弾くので、ジョブ0個で失敗し、
  スケジュールも一度も発火しなかった。複数行の文字列は `printf '%s\n'` で組む。
  直したら必ずトップレベルのキーを確認すること。
  `name` / `on` / `concurrency` / `permissions` / `jobs` 以外があってはいけない。

## よくある落とし穴

- **`.posted-bluesky`** … これがあると二重投稿を防ぐためスキップされる。
  手動で投稿した日は、この印を作っておかないと Actions が再投稿する。
- **日付は JST 基準。** `TZ=Asia/Tokyo date +%F`。cron は `35 21 * * *`（UTC）。
- **`.DS_Store`** … macOS が撒くので `.gitignore` 済み。

---

## ファイル構成

```
scripts/
  generate.py        Claude API で原稿を作る（RULES に編集方針が書いてある）
  render.py          content.json → PNG。デザインはここで固定
  validate.py        関門1: 形式
  review.py          関門2: 中身
  post_bluesky.py    Bluesky 投稿
  selftest.py        接続確認（既定では投稿しない）
  recent_topics.py   直近テーマ一覧（ネタ重複の回避に使う）
.github/workflows/
  daily.yml          毎朝の本番
  bluesky-test.yml   接続テスト。単体で完結し他ファイルに依存しない
post/YYYY-MM-DD/
  content.json  research.md  review.json
  instagram/01-05.png   bluesky/01-04.png
  instagram.txt  threads.txt  bluesky.txt  bluesky.alt.txt
  .posted-bluesky
```

## 費用

Anthropic API が 1日 $0.35〜0.70（調査・構成・校閲の3コール）。
Actions は公開リポジトリなので無料。Bluesky も無料。
コンソールで月額上限を設定してある前提。
