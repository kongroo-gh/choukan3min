# セットアップ手順（Bluesky 全自動）

> **【一部古い】** これは Anthropic API で毎朝生成していた頃の手順です。
> 現在は原稿づくりをローカルの Claude Code で行い、`ANTHROPIC_API_KEY` は不要です。
> 現行の構成は `README.md`、毎晩の手順は `MORNING.md`、
> 別アカウントへの引き継ぎは `MIGRATE.md` を見てください。
> Bluesky のアプリパスワードと Secrets の登録手順（3〜4章）は今も有効です。

所要 20〜30分。上から順に進めてください。
終わると、毎朝6:35に調査から投稿まで無人で走る状態になります。

---

## 0. 先に知っておいていただきたいこと

このリポジトリは Claude が組み立てましたが、**Claude 自身が GitHub に設置することはできませんでした。**
理由は2つあります。

**理由1: Claude のいるクラウド環境から SNS の API に到達できない**

実際に疎通を試した結果です。

```
https://pypi.org/simple/          200   ← パッケージ配布元は通る
https://api.github.com            200   ← GitHub API は通る（ただし権限は限定）
https://bsky.social/xrpc/...      000   ← 遮断
https://graph.threads.net/        000   ← 遮断
https://graph.facebook.com/       000   ← 遮断
```

**理由2: Claude のトークンに新規リポジトリを作る権限がない**

```
POST /user/repos → "sessions are bound to their configured repositories"
```

一度置いてしまえば、あとは GitHub Actions が毎朝ひとりで回ります。

---

## 1. リポジトリを作って中身を置く

GitHub で新しいリポジトリを作ります。**公開（Public）で構いません。**
公開にすると次の利点があります。

- **Actions の実行時間が無料・無制限**（非公開だと月2,000分の枠を使う）
- 将来 Threads / Instagram を足すとき、`raw.githubusercontent.com` が
  そのまま画像の公開URLとして使える（Meta系はこれが必須。別途の画像ホストが不要になる）

公開すると、その日の原稿・調査メモ・画像が投稿の数分前から誰でも見られる状態になります。
どのみち直後に公開する内容なので実害は小さいですが、承知の上で選んでください。

```bash
unzip choukan3min-autopost.zip
cd repo
git init && git add -A
git commit -m "初回"
git branch -M main
git remote add origin https://github.com/<あなたのID>/choukan3min.git
git push -u origin main
```

スマートフォンしかない場合は、GitHub の web 画面から
「Add file → Upload files」でフォルダごとドラッグしても構いません。

---

## 2. Anthropic の API キーを用意する

毎朝のニュース調査・原稿執筆・校閲に使います。

1. https://console.anthropic.com/ でアカウントを作る
2. **Billing** でクレジットを入れる（最初は $20 程度で十分）
3. **Limits** で月額の上限を設定する（暴走時の保険。$30 など）
4. **API keys** → Create Key。表示された `sk-ant-...` をコピー

**費用の目安: 1日 $0.35〜0.70、月 $11〜21。**
web検索つきの調査1回、構成1回、校閲1回の計3コールを毎日実行します。
必ず上限設定をしてください。

---

## 3. Bluesky のアプリパスワードを発行する

**通常のログインパスワードは使いません。**

1. Bluesky アプリ → 設定 → プライバシーとセキュリティ → アプリパスワード
2. 「アプリパスワードを追加」。名前は `github-actions` など
3. 表示された文字列をコピー（**画面を閉じると二度と表示されません**）

アプリパスワードはアカウントの削除やメールアドレスの変更ができない権限に限定されており、
いつでも失効させられます。公開リポジトリでも GitHub Secrets の中身は公開されません。

---

## 4. GitHub に登録する

リポジトリの **Settings → Secrets and variables → Actions** を開きます。

**Secrets タブ**（暗号化されて保存され、あとから中身を見ることはできません）

| Name | Value |
|---|---|
| `ANTHROPIC_API_KEY` | 手順2の `sk-ant-...` |
| `BLUESKY_HANDLE` | `economy-social.bsky.social`（先頭の `@` は付けても付けなくても動きます） |
| `BLUESKY_APP_PASSWORD` | 手順3のアプリパスワード |

**Variables タブ**（ただの設定値。秘密ではありません）

| Name | Value | 意味 |
|---|---|---|
| `ACCOUNT_HANDLE` | `@economy-social` | 画像のフッターに入る表記（設定済みの既定値と同じ） |
| `AUTO_PUBLISH` | *（未設定でよい）* | `false` にしたときだけ投稿を止める |
| `CLAUDE_MODEL` | *（任意）* | 既定は `claude-sonnet-4-5` |
| `REVIEW_STRICT` | *（任意）* | `1` にすると校閲の軽微な指摘でも投稿を止める |

`AUTO_PUBLISH` は**未設定なら投稿する**設定にしてあります。
止めたいときだけ `false` を入れてください。

---

## 5-A. 接続だけ先に確かめる（いちばん手軽・投稿されません）

パソコンが手元にあるなら、GitHub に置く前でもこれだけ試せます。
**ログインと画像アップロードまで実際に通し、投稿はしません。**

```bash
cd repo
export BLUESKY_HANDLE=economy-social.bsky.social
export BLUESKY_APP_PASSWORD='手順3でコピーしたもの'
python3 scripts/selftest.py post/2026-08-25
```

うまくいくとこう出ます。

```
── 1. ログイン ──
   ハンドル: economy-social.bsky.social
   成功。DID: did:plc:xxxxxxxxxxxxxxxxxxxxxxxx

── 2. 本文 ──
   240 文字 / 上限 300
   リンク化: #日銀  (tag)
   ...
── 3. 画像のアップロード ──
   01.png   134,660バイト  1080×1350  → アップロード成功
   ...
接続確認はすべて成功しました。投稿はしていません。
```

アップロードした画像は、投稿レコードから参照されない限り誰にも見えません。
実際に投稿してみたい場合は `--post` を付けて再実行してください。

```bash
python3 scripts/selftest.py post/2026-08-25 --post
```

投稿URLが出ます。テスト投稿は Bluesky アプリから削除できます。

`ログイン: HTTP 401` が出たら、ハンドルかアプリパスワードの誤りです。
アプリパスワードは4文字ずつハイフンで区切られた形式（`xxxx-xxxx-xxxx-xxxx`）です。

---

## 5-B. Actions で試運転する（投稿せずに中身を見る）

1. **Actions** タブ →「朝刊3分 毎朝の生成と投稿」→ **Run workflow**
2. `dry_run` に **✓ を入れて**実行
3. 5〜10分で完了（初回は Chromium の準備で時間がかかります）
4. 実行結果の画面を下にスクロール → **Artifacts** から `brief-2026-XX-XX` を
   ダウンロード。画像9枚とキャプション3種、調査メモ、校閲結果が入っています

うまくいかない場合、よくある原因は次のとおりです。

| 症状 | 原因 |
|---|---|
| `ANTHROPIC_API_KEY が未設定です` | Secrets の名前の綴り違い |
| `HTTP 400 credit balance is too low` | Anthropic のクレジット不足 |
| 形式の検査に失敗 | 文字数超過・禁止表現・出典不足など。ログに理由が出ます |
| 校閲で重大な指摘 | 数字が調査メモと食い違った。`review.json` に詳細 |
| 画像の日本語が豆腐（□） | フォント導入の失敗。ログの `fc-list` の行を確認 |

検査や校閲で止まった場合、**それは正常動作です。** 再実行すれば別の原稿が作られます。

---

## 6. 実際に投稿してみる

Artifacts の中身に納得できたら、`dry_run` の ✓ を外して Run workflow。
実行結果のサマリに投稿URLが出ます。

これ以降は**毎朝6:35に自動で投稿されます。** 何もする必要はありません。

---

## 7. 無人運転で何が守られているか

あなたが見ていない内容がそのまま公開されるので、2段の関門を置いてあります。

**1段目 `validate.py` — 形式の検査（API不要・確定的）**

スライドの構造、1枚あたりの文字数、使用可能なHTMLタグ、出典URLが2件以上あるか、
キャプションの文字数、ハッシュタグの個数、免責文の有無、5枚目の反対意見が15字以上あるか、
禁止表現17語、画像の枚数とファイルサイズ。1つでも引っかかれば投稿しません。

**2段目 `review.py` — 中身の校閲（別のモデル呼び出し）**

書き手ではなく校閲者として、原稿と調査メモを突き合わせます。

- 調査メモに存在しない数字が原稿に出ていないか
- 桁・単位・日付が食い違っていないか
- 「推計」「観測」が確定事実として書かれていないか
- 投資助言と読める記述がないか

`critical` が1件でも出れば投稿を中止します。調査メモ（`research.md`）自体が無い場合も中止します。

**それでも防げないこと**: 調査の段階で拾った情報がそもそも誤っていた場合。
出典URLは `research.md` に残るので、気になったときは辿って確認してください。

心配になったら `AUTO_PUBLISH` を `false` にすれば、生成だけして投稿しなくなります。

---

## 止め方

| したいこと | 方法 |
|---|---|
| 今日の分だけ止める | `post/<日付>/.posted-bluesky` を作って push |
| しばらく止める | Variables の `AUTO_PUBLISH` を `false` に |
| 完全に止める | Actions タブでワークフローを Disable |
| 投稿し直す | `.posted-bluesky` を消して Run workflow |
| 基準を厳しくする | Variables に `REVIEW_STRICT` = `1` |

失敗すると GitHub から通知メールが届き、リポジトリに Issue が立ちます。

---

## Threads と Instagram を足すとき

リポジトリを公開にしたので、画像の公開URLは
`https://raw.githubusercontent.com/<ID>/choukan3min/main/post/<日付>/instagram/01.png`
がそのまま使えます。別途の画像ホストは不要です。

残る作業は Meta 側です。

- Meta の開発者アカウントとアプリ作成
- Instagram の場合はさらに Facebook ページとの連携、ページ公開認可（PPA）
- アクセストークンの60日ごとの更新（これも Actions で自動化できます）

`scripts/post_threads.py` を足し、`daily.yml` にステップを追加する形になります。
