# 移行タスク（Claude Code 向け）

> **【完了済み】2026-08-28 にこの手順は完了しました。以下は記録です。**
> リポジトリは作成・push 済み、Bluesky の Secrets も設定・接続確認済みで、
> 2026-08-28 と 08-29 の号を配信しています。
> **別の Claude アカウントへ引き継ぐ場合は `MIGRATE.md` を見てください。**
> なお当時と構成が変わっています（毎朝の運用で Anthropic API を使わなくなった）。

**このファイルは一度きりの初期セットアップ手順です。完了したら不要になります。**

先に `CLAUDE.md` を読んでください。特に「絶対に守ること」の6項目。

---

## いまの状態

- コードは完成していて、ローカルでの動作確認は済んでいる
- Bluesky への投稿も1度成功している（手動、`selftest.py --post` 経由）
  https://bsky.app/profile/economy-social.bsky.social/post/3mtx5oa6hnd25
- **GitHub にはまだ何も置かれていない。** リポジトリすら作られていない
- したがって毎朝の自動運転はまだ動いていない

## ゴール

GitHub Actions が毎朝6:35（JST）に、調査から Bluesky 投稿までを無人で行う状態。

---

## タスク

### 0. 前提を確認する

```bash
gh auth status        # 未認証なら gh auth login
python3 --version     # 3.9 以上
git status
```

`gh` が無ければ `brew install gh`。

### 1. `.posted-bluesky` を作る（重要・忘れると二重投稿）

`post/2026-08-25/` は既に手動で Bluesky へ投稿済みです。
印がないと Actions が同じ内容をもう一度投稿します。

```bash
date -u +"%Y-%m-%dT%H:%M:%SZ" > post/2026-08-25/.posted-bluesky
```

### 2. リポジトリを作って push

**公開（Public）で作ります。** 理由は2つ。

- Actions の実行時間が無料・無制限（非公開だと月2,000分の枠を消費）
- 将来 Threads / Instagram を足すとき、`raw.githubusercontent.com` が
  そのまま画像の公開URLとして使える（Meta系はこれが必須）

その日の原稿が投稿の数分前から公開状態になりますが、
どのみち直後に公開する内容なのでユーザーは了承済みです。

```bash
git init
git add -A
git commit -m "初回: 朝刊3分 自動投稿"
git branch -M main
gh repo create choukan3min --public --source=. --remote=origin --push
```

### 3. Secrets と Variables を登録

**値をチャットに表示させないこと。** `gh secret set` は引数なしで実行すると
非表示のプロンプトで入力を受け取ります。ユーザー自身に打ってもらってください。

```bash
gh secret set ANTHROPIC_API_KEY        # console.anthropic.com で発行した sk-ant-...
gh secret set BLUESKY_HANDLE           # economy-social.bsky.social
gh secret set BLUESKY_APP_PASSWORD     # Bluesky のアプリパスワード（ログインPWではない）

gh variable set ACCOUNT_HANDLE --body "@economy-social"
```

`AUTO_PUBLISH` は**作らないでください。** 未設定＝投稿する、が既定の挙動です。
止めたいときだけ `false` を入れる設計になっています。

登録できたか確認:

```bash
gh secret list
gh variable list
```

**`ANTHROPIC_API_KEY` がまだ無い場合はここで止めてユーザーに確認してください。**
勝手に先へ進まないこと。console.anthropic.com で
Billing にクレジットを入れ、Limits で月額上限を設定してもらう必要があります。
費用は1日 $0.35〜0.70 の見込みです。

### 4. 試運転（投稿しない）

```bash
gh workflow run daily.yml -f dry_run=true
sleep 10
gh run watch
```

5〜10分かかります（初回は Chromium の準備で時間がかかる）。

完了したら生成物を取り出して**必ず目視してください**:

```bash
gh run download --name "brief-$(TZ=Asia/Tokyo date +%F)" --dir /tmp/brief
open /tmp/brief/instagram/01.png
cat /tmp/brief/bluesky.txt
cat /tmp/brief/research.md
```

見るべき点:

- 日本語が豆腐（□）になっていないか
- 文字がはみ出したり重なったりしていないか
- 本文の数字が `research.md` の内容と合っているか
- 5枚目に反対意見が入っているか

失敗した場合、よくある原因は次のとおりです。

| ログの症状 | 原因 |
|---|---|
| `ANTHROPIC_API_KEY が未設定です` | Secret 名の綴り違い |
| `HTTP 400 credit balance is too low` | Anthropic のクレジット不足 |
| `検査に失敗しました` | validate.py が止めた。**これは正常動作。** ログに理由が出る |
| `校閲で重大な指摘` | review.py が止めた。**これも正常動作。** `review.json` に詳細 |
| `Noto Serif CJK JP が見つかりません` | apt の失敗。再実行で直ることが多い |

**検査で止まったときに、検査を緩めて通そうとしないこと。** 再実行すれば
別の原稿が作られます。何度も同じ理由で止まる場合はユーザーに報告してください。

### 5. 本番投稿（ユーザーの確認を取ってから）

手順4の生成物をユーザーに見せて、**了承を得てから**実行します。

```bash
gh workflow run daily.yml
gh run watch
```

サマリに投稿URLが出ます。

### 6. 完了報告

以下をユーザーに伝えてください。

- リポジトリのURL
- 初回投稿のURL
- 次回の自動実行は翌朝6:35（JST）であること
- **Claude（Cowork側）の毎朝の定期タスクを止めてもらう必要があること。**
  両方動くと1日に2本ぶん別々の原稿ができます

---

## 完了後

このファイル（`HANDOFF.md`）は削除して構いません。
`CLAUDE.md` は運用の context として残してください。

## やらないこと

- `AUTO_PUBLISH` を勝手に設定しない
- 検査（validate.py / review.py）を通すために基準を緩めない
- ユーザーの確認なしに本番投稿しない
- 依存ライブラリを増やさない（標準ライブラリ＋playwright のみ）
- `post/` の過去ディレクトリを消さない（ネタ重複の回避に使っている）
