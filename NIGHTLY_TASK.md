# 毎晩の定期タスク（Claude Code に登録する指示文）

このファイルの内容を、Claude Code の定期タスクとして登録する。
登録先は `~/.claude/scheduled-tasks/choukan3min-nightly/SKILL.md`。
アカウントや機械を移したら登録し直す必要がある（リポジトリには残るが、
定期タスクの登録そのものは Claude Code 側にあるため）。

    cron: 0 22 * * *   （ローカル時刻。負荷分散で数分ずれる）

手順の実体は `MORNING.md` にある。この指示文はそれを読ませたうえで、
無人実行に固有の注意（止まらないこと、失敗したら push しないこと）を足したもの。

---

---
name: choukan3min-nightly
description: 朝刊3分：翌朝分の原稿を毎晩22時に作って push する（投稿は翌朝 GitHub Actions が行う）
---

経済ニュース解説アカウント「朝刊3分」の、翌朝配信分の原稿を作る作業です。
リポジトリは /Users/kongroo.ai/Downloads/repo です。まずそこへ移動してください。

**投稿はしません。**あなたの仕事は原稿を作って push するところまでです。
翌朝6:35に GitHub Actions が検査して投稿します。post_bluesky.py は絶対に実行しないでください。

## 最初に読むもの

作業を始める前に、必ずこの3つを読んでください。手順と制約が書いてあります。

- MORNING.md … 毎晩の手順。**文字数の目安の表は必ず守ること**
- CLAUDE.md … 絶対に守ること、仕様上の制約、落とし穴
- README.md … 5枚の型、運用の方針

## 対象日

`TZ=Asia/Tokyo date -v+1d +%F` で翌日の日付を出します。これが対象日です。
`post/<対象日>/content.json` が既にあれば、**何もせず終了**してください（二重作成の防止）。

## 手順

### 1. 記事を集める → post/<対象日>/sources.md

WebSearch と WebFetch で、その日の日本と世界の経済ニュースを調べます。
`python3 scripts/recent_topics.py 7` で直近のテーマを確認し、同じ角度の繰り返しを避けます。

**WebFetch できるのは下の一覧にあるドメインだけです。**
一覧に無い先を取りに行くと承認待ちで止まり、無人実行が朝まで進みません。
検索結果に一覧外のサイトが出てきたら、**取りに行かず、別の情報源を探してください。**
同じ話題は必ず複数社が報じています。WebSearch 自体に制限はありません。

一次情報に近いものを優先します。5〜8本を目安に、この書式で `sources.md` に保存します。

### 取得してよいドメイン（これ以外は取りに行かない）

    www.nikkei.com              business.nikkei.com         xtech.nikkei.com
    www.asahi.com               mainichi.jp                 www.yomiuri.co.jp
    www.sankei.com              www.tokyo-np.co.jp          www.chunichi.co.jp
    www.nishinippon.co.jp       www.hokkaido-np.co.jp       kahoku.news
    www.kobe-np.co.jp           www.toonippo.co.jp          www.jiji.com
    sp.m.jiji.com               www.kyodo.co.jp             nordot.app
    news.yahoo.co.jp            www3.nhk.or.jp              www.nhk.or.jp
    www.nhk.jp                  news.tv-asahi.co.jp         news.ntv.co.jp
    newsdig.tbs.co.jp           www.fnn.jp                  www.tv-tokyo.co.jp
    txbiz.tv-tokyo.co.jp        toyokeizai.net              diamond.jp
    president.jp                www.bloomberg.co.jp         www.bloomberg.com
    jp.reuters.com              www.reuters.com             jp.wsj.com
    www.wsj.com                 www.ft.com                  www.bbc.com
    apnews.com                  www.cnbc.com                www.economist.com
    www.boj.or.jp               www.stat.go.jp              www.e-stat.go.jp
    www.soumu.go.jp             www.mof.go.jp               www.meti.go.jp
    www.mhlw.go.jp              www.maff.go.jp              www.mlit.go.jp
    www.cao.go.jp               www.esri.cao.go.jp          www.cfa.go.jp
    www.jetro.go.jp             www.jpx.co.jp               www.imf.org
    www.oecd.org                www.worldbank.org           www.federalreserve.gov
    www.ecb.europa.eu           www.bls.gov

内訳は、全国紙・地方紙・通信社・放送局・経済メディア・官公庁・国際機関です。
足りないと感じたら、その日は諦めて別の社を当たってください。
一覧の追加は人の判断で行います。**勝手に一覧外へ取りに行かないこと。**


```markdown
## 記事の見出し
URL: https://www.example.co.jp/article
（記事本文をそのまま貼る。要約しない）
```

**ここでは要約も取捨選択もしません。**整理は次の工程で Gemini が行います。
URL は必ず2件以上必要です。

### 2. Gemini に整理させる → research.md

```bash
source ~/.config/choukan3min.env && python3 scripts/gemini_research.py post/<対象日>
```

APIキーは `~/.config/choukan3min.env` にあります。
これが失敗したら、**そこで中止**してください。原稿の根拠が無いまま進めてはいけません。
HTTP 429 が出たら無料枠の制限です。時間をおいても直らなければ中止して記録を残します。

### 3. 原稿を組む → content.json

`research.md` **だけ**を根拠に、5枚分の原稿と媒体別キャプションを作ります。
構造は scripts/validate.py の REQUIRED_KEYS が定めるとおりです。

**メモに無い数字を書いてはいけません。**これが最も重要な規則です。
MORNING.md の文字数の目安を必ず守ってください。超えると画像から文字が溢れます。
特に2〜5枚目の title は12字までです。

**見出しで因果を断定しないこと。**（2026-08-29 の回で実際にやってしまった失敗です）
本文で「とみられる」と留保しているのに、見出しだけ言い切る、というのが起きやすい形です。
research.md が推計・観測として書いている因果は、見出しでも推計として扱ってください。

    悪い例: 「タダにしたら、入れなくなった」「無償化が需要を呼んだ」「無償化が、行き場を奪った。」
    良い例: 「無償化のあとで、待機児童が増えた」「なぜ東京だけ増えたか」
            「増加分は、ほぼ東京都に集中している。」

原則は、**起きた順番や事実の並びを述べ、原因の断定は避ける**ことです。
問いかけの形（「なぜ〜か」）も使えます。
research.md が明確な因果として書いている場合に限り、見出しでも因果として書けます。

煽り表現も使わないでください。読者を不安にさせて注意を引く書き方はしません。
validate.py の禁止語リストは最低限の歯止めであって、そこに載っていなければ
何を書いてもよい、という意味ではありません。

グラフ（4枚目の chart）を入れるときは注意点が2つあります。

- 3番目の要素は**注記**の欄です。単位を入れないでください（点の横に浮いて表示されます）。
  注記が不要なら空文字にし、`chart_caption` に単位を含めた説明を書きます。
- 値の幅が狭いと縦軸の目盛りが壊れます（例: 1.7〜1.8 で「1.8 / 1.8 / 1.7」と重複表示）。
  その場合はチャートを省いてください。

### 4. 画像 → 5. 形式の検査

```bash
python3 scripts/render.py post/<対象日>
python3 scripts/validate.py post/<対象日>
```

validate.py が落ちたら原稿を直して、通るまで繰り返します。
**検査を緩めることは絶対にしないでください。**止まるのは正常動作です。

書き出した画像は必ず目で見てください。**文字のはみ出し・重なり・グラフの表示崩れは
validate.py では拾えません。**特に5枚目は要素が多く、溢れるとフッターに重なります。

### 6. 校閲 → review.json

ここは意識して独立した工程にしてください。書き手としてではなく校閲者として、
`content.json` と `research.md` を**改めて読み直して**から突き合わせます。

- 調査メモに存在しない数字が原稿に出ていないか
- 桁・単位・日付が食い違っていないか
- 「推計」「観測」が確定事実として書かれていないか。**見出しも本文と同じ基準で見ること**
- 出典のない断定的な予測、投資助言と読める記述がないか
- 煽り表現、読者の不安を煽って注意を引く書き方になっていないか

機械的な下調べとして、原稿の全数値がメモにあるかを確認するコードは MORNING.md にあります。
ただしそれは下調べであって校閲ではありません。桁の取り違えや文脈の誤りは拾えません。

結果を `post/<対象日>/review.json` に書きます。

```json
{
  "verdict": "pass",
  "issues": [{"severity": "warning", "where": "…", "what": "…"}],
  "note": "…",
  "content_sha256": "…"
}
```

`note` には必ず「無人の定期実行で、原稿を書いたのと同じセッションが校閲した」旨を書いてください。
あとから記事を検証するときの手がかりになります。
ハッシュは次で作ります。

```bash
python3 -c "import hashlib;print(hashlib.sha256(open('post/<対象日>/content.json','rb').read()).hexdigest())"
```

critical が1件でもあれば verdict は fail です。**その場合は push せず中止**してください。
中止した日は休刊になります。誤情報を出すより休刊のほうが良い、というのがこの運用の方針です。

確認:

```bash
python3 scripts/check_review.py post/<対象日>
```

### 7. commit & push

すべての検査を通ったときだけ行います。

```bash
git add post/<対象日> && git commit -m "brief: <対象日>（テーマ）" && git push
```

## 途中で失敗したとき

**部分的な成果物を push しないでください。**中途半端な原稿があると、翌朝の Actions が
それを検査して失敗します。何も push しなければ「原稿が無い日」として休刊になり、
Actions が Issue を立てて知らせます。そちらのほうが安全です。

どこで何が起きたかを最後に報告してください。

## 止まらないために

無人で動くので、**承認待ちで止まった時点でその日の朝刊は落ちます。**
次の3つを守れば止まりません。

- **WebFetch は上の一覧のドメインだけ。**一覧外は取りに行かない
- **コマンドはこの手順書に書かれた形のまま使う。**思いつきで別のコマンドを組まない
  （`scripts/` 配下の実行、`git`、`python3 -c`、`mkdir -p post/...` は許可済み）
- **`post/` の外にファイルを書かない**

どうしても許可されていない操作が要る場面に来たら、そこで**中止**してください。
承認を待って止まり続けるより、休刊にして Issue で知らせるほうが良い設計にしてあります。

## 絶対に守ること

- 数字を創作しない。research.md に根拠がないものは原稿に入れない
- **見出しで因果を断定しない。**本文が留保しているなら見出しも留保する
- **煽らない。**不安を煽って注意を引く書き方をしない。禁止語リストは最低限の歯止めにすぎない
- validate.py と check_review.py を緩めない。review.json を検査に通すためだけに手で書かない
- 画像は必ず目で見る。はみ出しと重なりは自動検査では拾えない
- 各キャプション末尾の免責文「※投資判断はご自身の責任でお願いします」を消さない
- 5枚目の反対意見を消さない
- 投資助言・銘柄推奨をしない
- post_bluesky.py を実行しない（投稿は翌朝の Actions の仕事）