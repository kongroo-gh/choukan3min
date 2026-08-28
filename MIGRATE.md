# 別の Claude アカウントへ引き継ぐ

原稿づくりは Claude Code（契約内）で動いているため、**アカウントを変えると
夜の工程が止まる。**朝の投稿は GitHub Actions なので影響を受けない。

移すのは3つだけ。他はそのまま使える。

---

## 引き継ぎ不要なもの

| | 理由 |
|---|---|
| リポジトリとコード | GitHub にある |
| GitHub Secrets（Bluesky） | GitHub アカウント側。Claude とは無関係 |
| Bluesky アカウントと過去の投稿 | 同上 |
| Gemini の APIキー | Google アカウント側。**値は使い回せる** |
| Obsidian の記録 | ローカルにある |

## 引き継ぎが要るもの（3つ）

| | いまの場所 | どうするか |
|---|---|---|
| 定期タスクの登録 | `~/.claude/scheduled-tasks/choukan3min-nightly/` | 新アカウントで登録し直す。内容は `NIGHTLY_TASK.md` |
| 権限の許可リスト | `.claude/settings.local.json`（gitignore） | `.claude/settings.local.json.example` をコピー |
| Gemini キーのファイル | `~/.config/choukan3min.env` | **同じ Mac なら残る。**別の機械なら作り直す |

---

## 手順

### 0. 旧アカウントで止める

Issue が毎日増えるのを避けるため、移行の間だけ止めておくのが安全。

- 定期タスクをサイドバーの「Scheduled」から無効化する
- 移行が長引くなら、`daily.yml` の `schedule:` をコメントアウトして push
  （原稿が無い日は毎朝 Issue が1件立つため）

### 1. 新アカウントで Claude Code を開く

作業ディレクトリは `~/Downloads/repo`（クローン先が違えばそこ）。
リポジトリが手元に無ければ:

```bash
git clone https://github.com/kongroo-gh/choukan3min.git && cd choukan3min
```

### 2. 権限の許可リストを置く

```bash
sed '/^\/\//d' .claude/settings.local.json.example > .claude/settings.local.json
python3 -c "import json;print(len(json.load(open('.claude/settings.local.json'))['permissions']['allow']),'件 読み込めました')"
```

**これを飛ばすと、初回の自動実行が承認待ちで止まる。**

### 3. Gemini のキーを置く（同じ Mac なら確認だけ）

```bash
ls -l ~/.config/choukan3min.env
```

無ければ作る。値は https://aistudio.google.com のもの（無料枠）。

```bash
mkdir -p ~/.config && read -rs "?Gemini APIキーを貼って Enter: " K \
  && printf 'export GEMINI_API_KEY=%s\n' "$K" > ~/.config/choukan3min.env \
  && chmod 600 ~/.config/choukan3min.env && unset K && echo "保存しました"
```

### 4. 定期タスクを登録する

`NIGHTLY_TASK.md` の「---」より下をそのまま指示文にして、Claude Code に登録を頼む。

```
NIGHTLY_TASK.md の指示文で、毎晩22時に動く定期タスクを登録して。
taskId は choukan3min-nightly、cron は 0 22 * * *。
```

### 5. 手動で1回通す

サイドバーの「Scheduled」から **Run now**。理由は2つ。

- 承認が保存され、以降の自動実行に引き継がれる
- Gemini と各サイトへの接続が実際に通るか確認できる

**完走したら `.claude/settings.local.json` を必ず見る。**日付が焼き込まれた
エントリが増えていたら、ワイルドカードに直す。

```bash
grep -c '2026-' .claude/settings.local.json   # 0 であること
```

### 6. 動作確認

```bash
D=$(TZ=Asia/Tokyo date -v+1d +%F)
python3 scripts/validate.py post/$D
python3 scripts/check_review.py post/$D
```

両方通れば、翌朝6:35に自動投稿される。

### 7. 旧アカウント側の後始末

- 定期タスクを削除
- `daily.yml` の cron を止めていたら戻す
- 旧アカウントに紐づく認証情報は無い（GitHub と Bluesky は別アカウント）

---

## 引き継がれない前提条件

- **Mac が起動していること**
- **Claude Code アプリが開いていること**（定期タスクはアプリが開いている間に動く。
  閉じていた場合は次回起動時に実行される）

## うまくいかないとき

| 症状 | 見るところ |
|---|---|
| 夜のタスクが動かない | アプリが開いているか。「Scheduled」で有効か |
| 途中で止まる | `.claude/settings.local.json` に日付が焼き込まれていないか |
| Gemini で 429 | `python3 scripts/gemini_research.py --check` で切り分け |
| 朝に休刊 Issue | 前夜のタスクが失敗している。タスクの実行ログを見る |
| 投稿されない | `check_review.py` が止めている。`review.json` を確認 |

設計の背景は `CLAUDE.md`、毎晩の手順は `MORNING.md`。
