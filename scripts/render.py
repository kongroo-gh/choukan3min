#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""content.json から カルーセル画像を書き出す。

    python3 scripts/render.py post/2026-08-25

出力:
    post/<日付>/instagram/01.png 〜 05.png   （5枚。Threads も同じものを使う）
    post/<日付>/bluesky/01.png 〜 04.png     （4枚。3枚目を落とした版）

デザインは案C「GAZETTE（新聞風）」。配色と書体はここで固定している。
"""
import asyncio
import json
import sys
from pathlib import Path

W, H = 1080, 1350
SHORT_IDX = [0, 1, 3, 4]          # X / Bluesky は画像4枚が上限。3枚目を落とす。

T = dict(
    bg="#EFE9DB", panel="#F8F4E9", panelbd="#D6CBB2",
    ink="#1B1815", muted="#6E6153", acc="#A8241F", acc2="#1B1815", rule="#CBBFA6",
    chip="#EAE0C9", chipink="#A8241F",
    font="'Noto Serif CJK JP','Noto Serif JP','Hiragino Mincho ProN','Yu Mincho',serif",
    radius="4px", hw="700",
)


# ---------------- illustrations ----------------
def ill_balance(t):
    a, b, m, ink = t["acc"], t["acc2"], t["muted"], t["ink"]
    return f'''
<svg class="ill" viewBox="0 0 900 366" fill="none" xmlns="http://www.w3.org/2000/svg">
  <path d="M450 148 L512 300 L388 300 Z" fill="{a}" opacity=".18"/>
  <path d="M450 148 L512 300 L388 300 Z" stroke="{a}" stroke-width="3"/>
  <g transform="rotate(-11 450 148)">
    <rect x="150" y="136" width="600" height="22" rx="11" fill="{ink}" opacity=".92"/>
    <circle cx="450" cy="147" r="13" fill="{t['bg']}" stroke="{ink}" stroke-width="6"/>
  </g>
  <g>
    <circle cx="168" cy="258" r="66" fill="{a}" opacity=".14"/>
    <circle cx="168" cy="258" r="66" stroke="{a}" stroke-width="4"/>
    <text x="168" y="284" text-anchor="middle" font-size="70" font-weight="800" fill="{a}" font-family="Helvetica,Arial,sans-serif">¥</text>
    <path d="M168 106 L168 168 M146 146 L168 170 L190 146" stroke="{a}" stroke-width="7" stroke-linecap="round" stroke-linejoin="round"/>
  </g>
  <g>
    <circle cx="734" cy="150" r="66" fill="{b}" opacity=".14"/>
    <circle cx="734" cy="150" r="66" stroke="{b}" stroke-width="4"/>
    <text x="734" y="176" text-anchor="middle" font-size="62" font-weight="800" fill="{b}" font-family="Helvetica,Arial,sans-serif">%</text>
    <path d="M734 78 L734 22 M712 44 L734 20 L756 44" stroke="{b}" stroke-width="7" stroke-linecap="round" stroke-linejoin="round"/>
  </g>
  <text x="168" y="358" text-anchor="middle" font-size="27" font-weight="700" fill="{m}">{t.get('lbl_l','円安')}</text>
  <text x="734" y="252" text-anchor="middle" font-size="27" font-weight="700" fill="{m}">{t.get('lbl_r','金利')}</text>
</svg>'''


def ill_two_sides(t, left, right, center):
    a, b, m, ink = t["acc"], t["acc2"], t["muted"], t["ink"]
    return f'''
<svg class="ill" viewBox="0 0 900 200" fill="none" xmlns="http://www.w3.org/2000/svg">
  <rect x="12" y="52" width="196" height="96" rx="14" fill="{a}" opacity=".13"/>
  <rect x="12" y="52" width="196" height="96" rx="14" stroke="{a}" stroke-width="3"/>
  <text x="110" y="112" text-anchor="middle" font-size="40" font-weight="800" fill="{a}">{left}</text>
  <rect x="692" y="52" width="196" height="96" rx="14" fill="{b}" opacity=".13"/>
  <rect x="692" y="52" width="196" height="96" rx="14" stroke="{b}" stroke-width="3"/>
  <text x="790" y="112" text-anchor="middle" font-size="40" font-weight="800" fill="{b}">{right}</text>
  <path d="M222 100 L392 100" stroke="{a}" stroke-width="5" stroke-linecap="round" stroke-dasharray="14 12"/>
  <path d="M372 84 L398 100 L372 116" stroke="{a}" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/>
  <path d="M678 100 L508 100" stroke="{b}" stroke-width="5" stroke-linecap="round" stroke-dasharray="14 12"/>
  <path d="M528 84 L502 100 L528 116" stroke="{b}" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/>
  <circle cx="450" cy="100" r="62" fill="{ink}" opacity=".08"/>
  <circle cx="450" cy="100" r="62" stroke="{ink}" stroke-width="4"/>
  <text x="450" y="126" text-anchor="middle" font-size="66" font-weight="800" fill="{ink}" font-family="Helvetica,Arial,sans-serif">¥</text>
  <text x="450" y="192" text-anchor="middle" font-size="24" font-weight="700" fill="{m}">{center}</text>
</svg>'''


def ill_chart(t, pts, caption):
    """pts = [[ラベル, 値, 注記], ...] 2〜6点。"""
    a, m, ink, rule = t["acc"], t["muted"], t["ink"], t["rule"]
    cw, ch = 900, 268
    L, R, TP, B = 66, 46, 26, 74
    vals = [p[1] for p in pts]
    span = max(vals) - min(vals) or 1
    lo, hi = min(vals) - span * 0.45, max(vals) + span * 0.45
    n = len(pts)

    def X(i): return L + (cw - L - R) * (i / max(n - 1, 1))
    def Y(v): return TP + (ch - TP - B) * (1 - (v - lo) / (hi - lo))

    step = (hi - lo) / 4
    grid = ""
    for k in range(1, 4):
        gv = lo + step * k
        y = Y(gv)
        lab = f"{gv:.0f}" if span >= 4 else f"{gv:.1f}"
        grid += f'<line x1="{L}" y1="{y:.1f}" x2="{cw-R}" y2="{y:.1f}" stroke="{rule}" stroke-width="1.5"/>'
        grid += f'<text x="{L-14}" y="{y+8:.1f}" text-anchor="end" font-size="20" fill="{m}">{lab}</text>'

    d = " ".join(("M" if i == 0 else "L") + f"{X(i):.1f} {Y(p[1]):.1f}" for i, p in enumerate(pts))
    area = d + f" L{X(n-1):.1f} {ch-B} L{X(0):.1f} {ch-B} Z"
    dots = ""
    for i, p in enumerate(pts):
        x, y = X(i), Y(p[1])
        anc = "start" if i == 0 else ("end" if i == n - 1 else "middle")
        ax = x - 12 if i == 0 else (x + 12 if i == n - 1 else x)
        dots += f'<circle cx="{x:.1f}" cy="{y:.1f}" r="9" fill="{t["bg"]}" stroke="{a}" stroke-width="5"/>'
        dots += f'<text x="{ax:.1f}" y="{y-26:.1f}" text-anchor="{anc}" font-size="23" font-weight="800" fill="{ink}">{p[2]}</text>'
        for k, line in enumerate(str(p[0]).split("\n")):
            dots += f'<text x="{x:.1f}" y="{ch-B+34+k*26:.1f}" text-anchor="middle" font-size="21" fill="{m}">{line}</text>'
    return (f'<svg class="chart" viewBox="0 0 {cw} {ch}" fill="none" xmlns="http://www.w3.org/2000/svg">'
            f'{grid}<path d="{area}" fill="{a}" opacity=".10"/>'
            f'<path d="{d}" stroke="{a}" stroke-width="5" stroke-linejoin="round" stroke-linecap="round"/>'
            f'{dots}</svg><div class="ccap">{caption}</div>')


ICONS = {
    "home": '<path d="M6 26 L32 6 L58 26 V56 H38 V38 H26 V56 H6 Z" stroke="CC" stroke-width="4" stroke-linejoin="round" fill="none"/>',
    "bank": '<path d="M6 24 L32 8 L58 24 M10 24 V50 M22 24 V50 M42 24 V50 M54 24 V50 M4 56 H60" stroke="CC" stroke-width="4" stroke-linecap="round" fill="none"/>',
    "cart": '<path d="M6 10 H16 L24 40 H50 L58 18 H20" stroke="CC" stroke-width="4" stroke-linejoin="round" stroke-linecap="round" fill="none"/><circle cx="27" cy="52" r="5" stroke="CC" stroke-width="4" fill="none"/><circle cx="47" cy="52" r="5" stroke="CC" stroke-width="4" fill="none"/>',
    "chart": '<path d="M8 56 V22 M24 56 V10 M40 56 V30 M56 56 V18 M4 60 H60" stroke="CC" stroke-width="4" stroke-linecap="round" fill="none"/>',
    "globe": '<circle cx="32" cy="32" r="26" stroke="CC" stroke-width="4" fill="none"/><path d="M6 32 H58 M32 6 C44 18 44 46 32 58 C20 46 20 18 32 6" stroke="CC" stroke-width="4" fill="none"/>',
    "factory": '<path d="M6 56 V26 L24 38 V26 L42 38 V14 H58 V56 Z" stroke="CC" stroke-width="4" stroke-linejoin="round" fill="none"/>',
}
ICON_ORDER = ["home", "bank", "cart"]


def icon(name, color):
    p = ICONS.get(name, ICONS["chart"]).replace("CC", color)
    return f'<svg class="ic" viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg">{p}</svg>'


def css(t):
    return f'''
*{{margin:0;padding:0;box-sizing:border-box}}
.board{{width:{W}px;height:{H}px;background:{t["bg"]};color:{t["ink"]};
  font-family:{t["font"]};position:relative;overflow:hidden;
  display:flex;flex-direction:column;padding:74px 76px 62px;}}
.hd{{display:flex;justify-content:space-between;align-items:center;font-size:23px;
  letter-spacing:.16em;color:{t["muted"]};font-weight:700;flex:0 0 auto}}
.hd .bar{{flex:1;height:2px;background:{t["rule"]};margin:0 22px}}
.ft{{display:flex;justify-content:space-between;align-items:center;font-size:23px;
  color:{t["muted"]};font-weight:700;flex:0 0 auto;padding-top:22px;border-top:2px solid {t["rule"]}}}
.body{{flex:1 1 auto;display:flex;flex-direction:column;padding:44px 0 26px;min-height:0}}
.chip{{display:inline-block;background:{t["chip"]};color:{t["chipink"]};font-size:26px;font-weight:800;
  padding:12px 24px;border-radius:3px;letter-spacing:.04em;align-self:flex-start}}
h1{{font-weight:{t["hw"]};line-height:1.16;letter-spacing:-.02em}}
h1.cover{{font-size:88px;margin-top:30px}}
h1.sec{{font-size:66px;margin-top:26px}}
em{{font-style:normal;color:{t["acc"]}}}
b{{color:{t["acc"]};font-weight:700}}
.sub{{font-size:35px;line-height:1.62;color:{t["muted"]};margin-top:28px;white-space:pre-line;font-weight:500}}
.sub b{{color:{t["ink"]}}}
.spacer{{flex:1 1 auto}}
.swipe{{font-size:27px;font-weight:800;color:{t["acc"]};letter-spacing:.02em}}
.ill{{width:100%;height:auto;display:block}}
ul.bl{{list-style:none;margin-top:36px;display:flex;flex-direction:column;gap:34px}}
ul.bl li{{position:relative;padding-left:50px;font-size:33px;line-height:1.6;font-weight:500}}
ul.bl li:before{{content:"";position:absolute;left:6px;top:16px;width:16px;height:16px;
  border-radius:2px;background:{t["acc"]}}}
.note{{margin-top:34px;background:{t["panel"]};border:2px solid {t["panelbd"]};border-left:8px solid {t["acc"]};
  border-radius:{t["radius"]};padding:30px 34px;font-size:32px;font-weight:800;line-height:1.5}}
.steps{{margin-top:38px;display:flex;flex-direction:column;gap:54px}}
.step{{display:flex;gap:26px;align-items:flex-start}}
.step .n{{flex:0 0 64px;height:64px;border-radius:4px;background:{t["acc"]};
  color:{t["panel"]};font-size:33px;font-weight:900;display:flex;align-items:center;
  justify-content:center;font-family:Helvetica,Arial,sans-serif}}
.step .tt{{font-size:37px;font-weight:700;line-height:1.35}}
.step .dd{{font-size:29px;line-height:1.58;color:{t["muted"]};margin-top:12px;font-weight:500}}
.step .dd b{{color:{t["ink"]}}}
.stats{{margin-top:34px;display:grid;grid-template-columns:1fr 1fr;gap:20px}}
.stat{{background:{t["panel"]};border:2px solid {t["panelbd"]};border-radius:{t["radius"]};padding:28px 30px}}
.stat .k{{font-size:25px;font-weight:800;color:{t["muted"]};letter-spacing:.03em}}
.stat .v{{font-size:66px;font-weight:900;line-height:1.05;margin-top:6px;color:{t["acc"]};
  font-family:Helvetica,Arial,sans-serif;letter-spacing:-.02em}}
.stat .v span{{font-size:29px;font-weight:800;margin-left:6px;color:{t["ink"]};font-family:{t["font"]}}}
.stat .s{{font-size:24px;color:{t["muted"]};margin-top:8px;font-weight:600}}
.chart{{width:100%;height:auto;display:block;margin-top:20px}}
.ccap{{font-size:22px;color:{t["muted"]};font-weight:700;margin-top:6px;text-align:right}}
.cards{{margin-top:34px;display:flex;flex-direction:column;gap:22px}}
.card{{display:flex;gap:24px;align-items:center;background:{t["panel"]};border:2px solid {t["panelbd"]};
  border-radius:{t["radius"]};padding:28px 30px}}
.ic{{flex:0 0 58px;width:58px;height:58px}}
.card .ct{{font-size:33px;font-weight:700;line-height:1.3}}
.card .cd{{font-size:27px;line-height:1.5;color:{t["muted"]};margin-top:10px;font-weight:500}}
.caution{{margin-top:32px;font-size:27px;line-height:1.58;color:{t["muted"]};font-weight:600;
  border-left:6px solid {t["rule"]};padding-left:22px}}
.caution b{{color:{t["ink"]}}}
.cta{{margin-top:30px;font-size:31px;font-weight:800;line-height:1.5;white-space:pre-line;color:{t["acc"]}}}
'''


def body(s, t):
    k = s["kind"]
    if k == "cover":
        t = dict(t, lbl_l=s.get("balance_left", "円安"), lbl_r=s.get("balance_right", "金利"))
        title = "<br>".join(s["title"])
        return (f'<div class="chip">{s["kicker"]}</div><h1 class="cover">{title}</h1>'
                f'<div class="sub">{s["sub"]}</div><div class="spacer"></div>'
                f'{ill_balance(t)}<div style="height:26px"></div>'
                f'<div class="swipe">{s.get("swipe", "スワイプして3分で理解 →")}</div>')
    if k == "what":
        lis = "".join(f"<li>{x}</li>" for x in s["bullets"])
        ill = ill_two_sides(t, *s["sides"]) if s.get("sides") else ""
        return (f'<div class="chip">{s["kicker"]}</div><h1 class="sec">{s["title"]}</h1>'
                f'{ill}<ul class="bl">{lis}</ul><div class="spacer"></div>'
                f'<div class="note">{s["note"]}</div>')
    if k == "why":
        st = "".join(f'<div class="step"><div class="n">{i+1}</div><div>'
                     f'<div class="tt">{a}</div><div class="dd">{b}</div></div></div>'
                     for i, (a, b) in enumerate(s["steps"]))
        tail = f'<div class="note">{s["tail"]}</div>' if s.get("tail") else ""
        return (f'<div class="chip">{s["kicker"]}</div><h1 class="sec">{s["title"]}</h1>'
                f'<div class="steps">{st}</div><div class="spacer"></div>{tail}')
    if k == "numbers":
        cells = "".join(f'<div class="stat"><div class="k">{a}</div>'
                        f'<div class="v">{b}<span>{c}</span></div><div class="s">{d}</div></div>'
                        for a, b, c, d in s["stats"])
        chart = ill_chart(t, s["chart"], s.get("chart_caption", "")) if s.get("chart") else ""
        return (f'<div class="chip">{s["kicker"]}</div><h1 class="sec">{s["title"]}</h1>'
                f'<div class="stats">{cells}</div><div class="spacer"></div>{chart}')
    if k == "life":
        cs = ""
        for i, c in enumerate(s["cards"]):
            name = c[2] if len(c) > 2 else ICON_ORDER[i % len(ICON_ORDER)]
            cs += (f'<div class="card">{icon(name, t["acc"])}<div>'
                   f'<div class="ct">{c[0]}</div><div class="cd">{c[1]}</div></div></div>')
        return (f'<div class="chip">{s["kicker"]}</div><h1 class="sec">{s["title"]}</h1>'
                f'<div class="cards">{cs}</div><div class="caution">{s["caution"]}</div>'
                f'<div class="spacer"></div><div class="cta">{s["cta"]}</div>')
    raise ValueError(f"未知のスライド種別: {k}")


def page(doc, s, i, total):
    board = (f'<div class="board"><div class="hd"><span>{doc.get("eyebrow","ECONOMY BRIEF")}</span>'
             f'<span class="bar"></span><span>{doc["date"].replace("-", ".")}</span></div>'
             f'<div class="body">{body(s, T)}</div>'
             f'<div class="ft"><span>{doc.get("handle","@economy-social")}</span>'
             f'<span>{i+1} / {total}</span></div></div>')
    return (f'<!doctype html><html><head><meta charset="utf-8"><style>{css(T)}'
            f'body{{background:{T["bg"]}}}</style></head><body>{board}</body></html>')


async def shoot(pairs):
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={"width": W, "height": H}, device_scale_factor=1)
        for html_path, png_path in pairs:
            await pg.goto("file://" + str(html_path.resolve()))
            await pg.wait_for_timeout(180)
            await pg.screenshot(path=str(png_path),
                                clip={"x": 0, "y": 0, "width": W, "height": H})
            print(f"  {png_path}")
        await b.close()


def main():
    day = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    doc = json.loads((day / "content.json").read_text(encoding="utf-8"))
    slides = doc["slides"]
    if len(slides) != 5:
        raise SystemExit(f"スライドは5枚必要です（{len(slides)}枚でした）")

    tmp = day / ".html"
    tmp.mkdir(parents=True, exist_ok=True)
    pairs = []

    ig = day / "instagram"
    ig.mkdir(exist_ok=True)
    for i, s in enumerate(slides):
        h = tmp / f"ig_{i+1}.html"
        h.write_text(page(doc, s, i, 5), encoding="utf-8")
        pairs.append((h, ig / f"{i+1:02d}.png"))

    bs = day / "bluesky"
    bs.mkdir(exist_ok=True)
    for n, idx in enumerate(SHORT_IDX):
        h = tmp / f"bs_{n+1}.html"
        h.write_text(page(doc, slides[idx], n, len(SHORT_IDX)), encoding="utf-8")
        pairs.append((h, bs / f"{n+1:02d}.png"))

    print(f"書き出し: {len(pairs)} 枚")
    asyncio.run(shoot(pairs))
    for f in tmp.glob("*.html"):
        f.unlink()
    tmp.rmdir()
    print("完了")


if __name__ == "__main__":
    main()
