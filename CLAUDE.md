# 朝刊3分 — プロジェクト context

経済ニュース解説アカウント「朝刊3分」を毎朝ひとりで回すリポジトリ。
Claude Code で作業するときは、まずこのファイルを読んでから動くこと。

初回のセットアップが未完了なら **`HANDOFF.md` を読んで、そこに書かれた手順を実行する。**

---

## これは何か

**原稿づくりは手元の Claude Code が行い、GitHub Actions は検査して投稿するだけ。**
Anthropic API は毎朝の運用では呼ばない。費用は $0。

```
前夜（このリポジトリで Claude Code を動かす）
  ① 収集   Claude Code が web検索 → sources.md（URL＋本文。要約しない）
  ② 整理   gemini_research.py → research.md
           Gemini（無料枠）が6項目へ整理。書き手と整理役を分けるため。
           Gemini に検索はさせない（グラウンディングは無料枠外。実測 429）。
           手作業で NotebookLM を使う道もある（NOTEBOOKLM.md）
  ③ 構成   research.md だけを根拠に content.json
  ④ 画像   render.py → PNG 9枚（IG 5 / Bluesky 4）
  ⑤ 関門1  validate.py    形式。API不要・確定的
  ⑥ 関門2  原稿と research.md を突き合わせ → review.json
  ⑦ commit & push

翌朝 6:35 JST（daily.yml）
  ⑧ 原稿があるか確認   無ければ Issue を立てて休刊。ジョブは成功扱い
  ⑨ validate.py         関門1を CI でも再実行
  ⑩ check_review.py     関門2の結果を確認。API不要・確定的
  ⑪ post_bluesky.py     Bluesky へ投稿
```

手順は `MORNING.md`、NotebookLM は `NOTEBOOKLM.md`。

`generate.py` / `review.py` / `digest.py` は **API を使う旧方式**で、
毎朝の運用では使わない。API に戻すときのために残してある。

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

**翌朝そのまま公開される。ここを緩めると誤情報がそのまま世に出る。**
原稿づくりには人が関わるが、投稿は無人で行われる。前夜に commit したものが
そのまま出ると考えること。

1. **2段の関門を弱めない。** `validate.py` と `check_review.py`（および旧方式の
   `review.py`）のしきい値・禁止語・必須項目を緩めてはいけない。テストを通すために
   検査を甘くするのは本末転倒。検査で止まるのは正常動作。
   **`check_review.py` の条件を外さない。** 特に `content_sha256` の照合は
   「校閲後に原稿だけ差し替える」を防ぐ唯一の歯止め。ここを緩めると関門2が
   形だけになる。`review.json` を手で書いて通すのも同じこと。
2. **`AUTO_PUBLISH` を勝手に変えない。** ユーザーが明示的に指示したときだけ触る。
3. **テスト投稿を無断でしない。** `--post` や `dry_run` なしの実行は、
   ユーザーの明示的な指示があるときだけ。
4. **数字を創作しない。** `research.md` に根拠がないものは原稿に入れない。
   **NotebookLM が書いた `research.md` の原文を書き換えない。** 検証のよりどころ。
   自分で調べ足したときは末尾に追記し、出典URLも必ず付ける。
   追記し忘れると、関門2で「メモに無い数字」として弾かれる（弾かれるのが正しい）。
   **出典どうしで数字が食い違ったら、どちらかに寄せない。** 両方の値と出典を
   `research.md` に残し、原稿でどちらを採ったかと理由を `review.json` に書く。
5. **`review.json` の `note` に、どういう条件で校閲したかを書く。**
   原稿を書いたのと同じセッションで校閲したなら、そう書く。
   独立性がどこまであったかは、あとから記事を検証するときの手がかりになる。
6. **免責文を消さない。** 各キャプション末尾の「※投資判断はご自身の責任で〜」は必須。
7. **5枚目の反対意見を消さない。** 断定だけの投稿にしない方針。

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
# 画像を書き出す（playwright が無ければ手元の Chrome を使う）
python3 scripts/render.py post/2026-08-29

# 関門1（APIキー不要）
python3 scripts/validate.py post/2026-08-29

# 関門2の結果を確認（APIキー不要）
python3 scripts/check_review.py post/2026-08-29

# 整理（Gemini・無料枠）。先に sources.md を用意しておく
export GEMINI_API_KEY='...'
python3 scripts/gemini_research.py post/2026-08-29
python3 scripts/gemini_research.py --check     # 使えるか診断

# NotebookLM に貼るプロンプト（手作業でやる場合。引数なしで翌朝が既定）
python3 scripts/notebooklm_prompt.py | pbcopy

# 直近のテーマ
python3 scripts/recent_topics.py 7

# Bluesky の接続確認（投稿しない）
export BLUESKY_HANDLE=economy-social.bsky.social
export BLUESKY_APP_PASSWORD='...'
python3 scripts/selftest.py post/2026-08-25
```

macOS には Hiragino Mincho ProN があるので明朝は出る。
画像化は playwright があればそれを、無ければ Google Chrome をヘッドレスで使う
（`CHROME_PATH` で場所を指定できる）。どちらも Chromium 系なので出来上がりは同じ。

スクリプトは**すべて標準ライブラリのみ**（render.py の playwright を除く）。
依存を増やさないこと。

## 変更するときの注意

- **`render.py` を触ったら必ず画像を目視する。** 文字のはみ出し・重なりは
  自動検査では拾えない。`post/<日付>/instagram/*.png` を開いて確認する。
  5枚目は要素が多く、溢れるとフッターに重なる（実際に踏んだ）。
- **原稿の文字数には上限がある。** 目安は `MORNING.md` の表。特に2〜5枚目の
  title は12字を超えると折り返して1文字だけ次行に落ちる。
- **`validate.py` / `check_review.py` を触ったら壊れたデータで試す。**
  正常系だけ通しても意味がない。`check_review.py` は
  無い / pass / warning / STRICT / critical / fail / ハッシュ不一致 /
  ハッシュ欠落 / JSON破損 の9系統。
- **`review.py`（旧方式）を触ったら API をモックして試す。** pass / warning /
  critical / 応答不正 / `REVIEW_STRICT` の5系統。実APIを叩く必要はない。
- **`review.json` を手で書いて関門2を通さない。** 校閲した事実がないのに
  通すのは、検査を消すのと同じ。
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
- **原稿が無い日は休刊。** `content.json` が無ければ Actions は投稿せず、
  Issue を立てて正常終了する。ジョブは失敗扱いにしない。
- **原稿を直したら校閲もやり直す。** `content.json` が変われば
  `review.json` の `content_sha256` と合わなくなり、CI が弾く。
- **`render.py` の縦軸目盛りは値の幅が狭いと壊れる。** 例: 1.7〜1.8 の2点で
  「1.8 / 1.8 / 1.7」と重複表示になる。幅の狭い系列はチャートを省くこと。
- **Gemini の Google検索グラウンディングは無料枠で使えない（実測）。**
  モデル自体は無料で叩けるが、`tools: [{"google_search": {}}]` を付けると
  初回から HTTP 429（RESOURCE_EXHAUSTED）になる。だから検索は Claude Code 側で
  行い、Gemini には `sources.md` の本文を渡して整理だけさせる。
  `gemini_research.py --check` で切り分けられる（モデル / 検索を別々に試す）。
- **Gemini に渡していないURLが整理結果に出たら中断する。** 学習データから
  思い出したURLを出典にされると、「出典があるのに検証できない」状態になる。
  `gemini_research.py` がこれを弾く。この検査を外さないこと。
- **日付は JST 基準。** `TZ=Asia/Tokyo date +%F`。cron は `35 21 * * *`（UTC）。
- **`.DS_Store`** … macOS が撒くので `.gitignore` 済み。

---

## ファイル構成

```
scripts/
  render.py             content.json → PNG。デザインはここで固定
  validate.py           関門1: 形式
  check_review.py       関門2の結果を確認（存在・pass・原稿との一致）
  post_bluesky.py       Bluesky 投稿
  selftest.py           接続確認（既定では投稿しない）
  recent_topics.py      直近テーマ一覧
  gemini_research.py    sources.md を Gemini に整理させ research.md を作る（無料枠）
  notebooklm_prompt.py  NotebookLM に貼るプロンプトを組み立てる（手作業の道）
  ── 以下は API を使う旧方式。毎朝の運用では使わない ──
  generate.py           Claude API で原稿を作る
  review.py             Claude API で校閲する
  digest.py             投稿後の記録づくり
MORNING.md              毎朝の手順（文字数の目安を含む）
NOTEBOOKLM.md           NotebookLM の使い方
.github/workflows/
  daily.yml             毎朝6:35の投稿。API不要
  bluesky-test.yml      接続テスト。単体で完結し他ファイルに依存しない
post/YYYY-MM-DD/
  sources.md   集めた記事（URL＋本文）。Gemini への入力
  research.md  Gemini が整理した調査メモ。検証のよりどころ
  content.json review.json
  instagram/01-05.png   bluesky/01-04.png
  instagram.txt  threads.txt  bluesky.txt  bluesky.alt.txt
  .posted-bluesky
```

## 費用

毎朝の運用では Anthropic API を呼ばないので **$0**。Actions は公開リポジトリなので
無料、Bluesky も無料。原稿づくりは手元の Claude Code が行うため、Claude の契約の
使用量は消費する。

API を使う旧方式に戻す場合は 1日 $0.35〜0.70。コンソールで月額上限を設定すること。
