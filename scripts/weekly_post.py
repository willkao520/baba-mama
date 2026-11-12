#!/usr/bin/env python3
"""每週四社群圖卡：從網站的「最近活動」挑出這個週末（週六、日）的活動，依地區產生 IG 輪播圖（1080x1350）。

用法：
  python3 scripts/weekly_post.py               # 以今天（臺北時間）算出接下來的週末
  python3 scripts/weekly_post.py --date 2026-11-12
  python3 scripts/weekly_post.py --skip "活動名稱關鍵字" --skip "另一個"   # 排除不想放的活動

輸出到 social/<週六日期>/：01.png、02.png…、captions.txt、picks.json、index.html（手機可直接下載的頁面）。
"""
import argparse, datetime as dt, html, json, re, subprocess, sys, time
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
SITE = "https://baba-mama.pages.dev"
PER_SLIDE = 6
MAX_SLIDES_PER_REGION = 2

REGIONS = [
    ("taipei", "台北", ["臺北市"], "#f1b33b", "#fff3d6"),
    ("newtaipei", "新北・基隆", ["新北市", "基隆市"], "#ee8fa6", "#fde4ea"),
    ("taoyuan", "桃園・新竹", ["桃園市", "新竹市", "新竹縣"], "#7cc59a", "#e2f4e8"),
    ("central", "中部", ["苗栗縣", "臺中市", "彰化縣", "南投縣", "雲林縣"], "#9b8ce0", "#ece8fb"),
    ("south", "南部", ["嘉義市", "嘉義縣", "臺南市", "高雄市", "屏東縣"], "#e4664a", "#fde3dc"),
    ("east", "東部・離島", ["宜蘭縣", "花蓮縣", "臺東縣", "澎湖縣", "金門縣", "連江縣"], "#8bb9e3", "#e3f0fb"),
]
TYPE_RANK = ["煙火・燈光秀", "市集・夜市", "嘉年華・節慶", "消防・警察體驗", "兒童劇・音樂會",
             "體驗營・營隊", "科學體驗", "戶外・自然", "展覽", "樂園優惠"]
FEE = {"free": "免費", "paid": "付費", "deal": "門票優惠", "check": "費用看官網"}
WD = "一二三四五六日"
e = html.escape


def taipei_today():
    return (dt.datetime.utcnow() + dt.timedelta(hours=8)).date()


def load_events():
    srv = subprocess.Popen([sys.executable, "-m", "http.server", "8798"], cwd=ROOT,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1.5)
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(); pg = b.new_page()
            pg.goto("http://localhost:8798/index.html"); pg.wait_for_timeout(1500)
            data = pg.evaluate("""()=>{const f=d=>d?`${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`:null;
              return liveEvents.map(x=>({n:x.n,c:x.c,d:x.d||'',t:x.t||'兒童劇・音樂會',f:x.f||(x.p?'paid':''),v:x.v||'',
                s:f(x.S),e:f(x.E),icon:(EV_ICON[x.t||'兒童劇・音樂會']||'')}));}""")
            b.close(); return data
    finally:
        srv.kill()


def short_name(n, limit=40):
    n = n.strip()
    if len(n) > limit:
        n2 = re.sub(r"[（(][^（）()]*[）)]\s*$", "", n).strip()
        if n2: n = n2
    return n if len(n) <= limit else n[:limit - 1] + "…"


def pick(events, sat, sun, skips):
    s_sat, s_sun = sat.isoformat(), sun.isoformat()
    seen, out = set(), {r[0]: [] for r in REGIONS}
    region_of = {c: r[0] for r in REGIONS for c in r[2]}
    cands = []
    for x in events:
        if not x["s"] or x["c"] not in region_of: continue
        end = x["e"] or "9999-12-31"
        if x["s"] > s_sun or end < s_sat: continue
        if any(k in x["n"] for k in skips): continue
        key = re.sub(r"[（(].*?[）)]|\s", "", x["n"])
        if (key, x["c"]) in seen: continue
        seen.add((key, x["c"]))
        days = (dt.date.fromisoformat(min(end, "2100-01-01")) - dt.date.fromisoformat(x["s"])).days
        rank = TYPE_RANK.index(x["t"]) if x["t"] in TYPE_RANK else len(TYPE_RANK)
        score = (12 if days > 30 else 6 if days > 7 else 0) + rank + (0 if x["f"] == "free" else 3)
        on_sat = x["s"] <= s_sat <= end; on_sun = x["s"] <= s_sun <= end
        when = "六日" if on_sat and on_sun else ("週六" if on_sat else "週日")
        cands.append((score, x["n"], dict(x, when=when, days=days)))
    for _, _, x in sorted(cands, key=lambda t: (t[0], t[1])):
        lst = out[region_of[x["c"]]]
        if len(lst) < PER_SLIDE * MAX_SLIDES_PER_REGION: lst.append(x)
    return out


def md(d):
    return f"{d.month}/{d.day}"


def date_line(x, sat, sun):
    if x["days"] > 7: return f"展期到 {md(dt.date.fromisoformat(x['e']))}" if x["e"] else "每週都有"
    if x["when"] == "六日": return f"{md(sat)}–{sun.day}（六日）"
    d = sat if x["when"] == "週六" else sun
    return f"{md(d)}（{x['when'][1]}）"


FONT = (ROOT / "scripts/fonts/Huninn-Regular.ttf").as_uri()
LOGO = (ROOT / "icons/logo-mark.png").as_uri()
LOGO_FULL = (ROOT / "icons/logo-full.png").as_uri()

BASE_CSS = f"""
@font-face{{font-family:Huninn;src:url('{FONT}')}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{width:1080px;height:1350px;font-family:Huninn,'Noto Sans CJK TC',sans-serif;color:#3a2e28;
  background:#fbf5e9 radial-gradient(#e6d8c2 2.4px,transparent 2.6px) 0 0/34px 34px;overflow:hidden;position:relative}}
.card{{position:absolute;left:60px;right:60px;top:150px;bottom:100px;background:#fff;border:6px solid #3a2e28;
  border-radius:48px;box-shadow:14px 16px 0 #3a2e28;padding:34px 44px}}
.tape{{position:absolute;width:170px;height:50px;opacity:.85;border-radius:6px}}
.brand{{position:absolute;top:44px;left:64px;display:flex;align-items:center;gap:14px;font-size:34px}}
.brand img{{width:76px;height:76px}}
.brand small{{font-size:24px;color:#8a6a4f;display:block;margin-top:2px}}
.foot{{position:absolute;bottom:34px;left:0;right:0;text-align:center;font-size:30px;color:#6b5546}}
.foot b{{color:#3a2e28;font-weight:normal;background:#fff3d6;border:3px solid #3a2e28;border-radius:999px;padding:4px 20px}}
.spark{{position:absolute}}
"""
SPARK = '<svg class="spark" style="{}" width="{}" height="{}" viewBox="0 0 40 40"><path d="M20 2l4.5 13.5L38 20l-13.5 4.5L20 38l-4.5-13.5L2 20l13.5-4.5z" fill="{}" stroke="#3a2e28" stroke-width="2.5" stroke-linejoin="round"/></svg>'


def spark(css, size, color):
    return SPARK.format(css, size, size, color)


def page(body, extra_css=""):
    return f"<!doctype html><html><head><meta charset='utf-8'><style>{BASE_CSS}{extra_css}</style></head><body>{body}</body></html>"


def cover_html(sat, sun, counts):
    pills = "".join(
        f'<div class="pill" style="background:{bg};border-color:#3a2e28"><span class="dot" style="background:{c}"></span>{e(name)}<em>{counts[k]} 個</em></div>'
        for k, name, _, c, bg in REGIONS if counts[k])
    css = """
.big{position:absolute;top:120px;left:0;right:0;text-align:center}
.big img{width:300px;height:300px}
.ribbon{display:inline-block;margin-top:10px;background:#e4664a;color:#fff;font-size:40px;padding:10px 40px;border:5px solid #3a2e28;border-radius:999px;box-shadow:6px 7px 0 #3a2e28;transform:rotate(-2deg)}
h1{font-size:96px;font-weight:normal;line-height:1.2;margin-top:34px;letter-spacing:2px}
h1 span{background:linear-gradient(transparent 62%,#ffd96a 62%)}
.sub{font-size:36px;color:#6b5546;margin-top:16px}
.pills{position:absolute;left:80px;right:80px;bottom:150px;display:grid;grid-template-columns:1fr 1fr;gap:20px}
.pill{border:4px solid;border-radius:26px;padding:16px 24px;font-size:40px;display:flex;align-items:center;gap:14px;box-shadow:5px 6px 0 #3a2e28}
.pill .dot{width:22px;height:22px;border-radius:50%;border:3px solid #3a2e28;flex:none}
.pill em{font-style:normal;margin-left:auto;font-size:30px;color:#6b5546}
"""
    body = f"""
<div class="big"><img src="{LOGO}"><br><div class="ribbon">{md(sat)}（六）– {md(sun)}（日）</div>
<h1>這個週末<br><span>帶小孩去哪玩？</span></h1><div class="sub">全台親子活動精選・往右滑 →</div></div>
{spark('top:150px;left:120px',70,'#f1b33b')}{spark('top:300px;right:110px',56,'#ee8fa6')}{spark('top:560px;left:90px',44,'#8bb9e3')}
<div class="pills">{pills}</div>
<div class="foot">爸~媽!!假日要去哪裡玩・<b>baba-mama.pages.dev</b></div>"""
    return page(body, css)


def region_html(region, items, sat, sun, idx, total):
    k, name, counties, color, bg = region
    mixed = len(counties) > 1
    rows = []
    for x in items:
        place = (x["c"].replace("臺", "台")[:2] + "・" if mixed else "") + (x["d"] or x["v"] or x["c"])
        fee = FEE.get(x["f"], "")
        rows.append(f"""<div class="row"><div class="ic" style="background:{bg}">{x['icon']}</div>
<div class="tx"><div class="nm">{e(short_name(x['n']))}</div>
<div class="mt">{e(date_line(x, sat, sun))}・{e(place)}{('・<span class="fee">' + e(fee) + '</span>') if fee else ''}</div></div></div>""")
    page_tag = f'<span class="pg">{idx}/{total}</span>' if total > 1 else ""
    css = f"""
.head{{position:absolute;top:50px;left:64px;display:flex;align-items:center;gap:14px}}
.brand{{left:auto;right:64px;top:40px}}
.rg{{font-size:58px;background:{bg};border:5px solid #3a2e28;border-radius:999px;padding:6px 34px;box-shadow:6px 7px 0 #3a2e28}}
.pg{{font-size:30px;color:#6b5546}}
.dates{{font-size:30px;color:#6b5546;margin-bottom:18px;display:flex;align-items:center;gap:10px}}
.dates i{{display:inline-block;width:18px;height:18px;border-radius:50%;background:{color};border:3px solid #3a2e28}}
.row{{display:flex;align-items:center;gap:24px;padding:13px 0;border-bottom:4px dashed #e6d8c2;min-height:162px}}
.row:last-child{{border-bottom:0}}
.ic{{width:112px;height:112px;border-radius:32px;border:4px solid #3a2e28;flex:none;display:flex;align-items:center;justify-content:center}}
.ic svg{{width:98px;height:74px}}
.tx{{min-width:0;flex:1}}
.nm{{font-size:40px;line-height:1.22;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}}
.mt{{font-size:28px;color:#6b5546;margin-top:4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.fee{{color:#c4502f}}
"""
    body = f"""
<div class="brand"><img src="{LOGO}"><div>爸~媽!!<small>這個週末去哪玩</small></div></div>
<div class="head"><span class="rg">{e(name)}</span>{page_tag}</div>
<div class="tape" style="top:126px;left:455px;background:{color};transform:rotate(-4deg)"></div>
<div class="card"><div class="dates"><i></i>{md(sat)}（六）– {md(sun)}（日）</div>{''.join(rows)}</div>
<div class="foot">時間、報名連結都在 <b>baba-mama.pages.dev</b></div>"""
    return page(body, css)


def end_html():
    css = """
.wrap{position:absolute;top:150px;left:0;right:0;text-align:center}
.wrap img{width:430px}
h2{font-size:64px;font-weight:normal;margin-top:30px}
.url{display:inline-block;margin-top:26px;font-size:52px;background:#fff3d6;border:5px solid #3a2e28;border-radius:999px;padding:12px 44px;box-shadow:7px 8px 0 #3a2e28}
.fl{font-size:38px;color:#6b5546;margin-top:44px;line-height:1.6}
.fl b{color:#3a2e28;font-weight:normal}
"""
    body = f"""<div class="wrap"><img src="{LOGO_FULL}"><h2>還有更多活動、景點、共融公園</h2>
<div class="url">baba-mama.pages.dev</div>
<div class="fl">每週四更新週末精選<br>追蹤 <b>@babamama.wherewego</b> 不錯過</div></div>
{spark('top:200px;left:110px',70,'#f1b33b')}{spark('top:420px;right:120px',56,'#ee8fa6')}{spark('bottom:200px;left:150px',48,'#7cc59a')}"""
    return page(body, css)


def captions(picks, sat, sun):
    lines = []
    for k, name, *_ in REGIONS:
        if picks[k]:
            tops = "、".join(short_name(x["n"], 14) for x in picks[k][:2])
            lines.append(f"📍{name}：{tops}…")
    hi = "\n".join(lines)
    head = f"📅 {md(sat)}（六）– {md(sun)}（日）這個週末帶小孩去哪玩？\n\n全台親子活動，依地區整理好了，往右滑找你家附近的 👉\n\n{hi}"
    tags = "#親子活動 #週末去哪裡 #親子景點 #台灣親子遊 #市集 #兒童劇"
    return {
        "fb": f"{head}\n\n每個活動的時間、地點、報名連結都在網站：\n👉 {SITE}/?from=fb\n\n{tags}",
        "ig": f"{head}\n\n每個活動的時間、地點、報名連結都在網站，連結在個人簡介 🔗\n每週四更新，記得追蹤不錯過！\n\n{tags} #雙寶爸",
        "threads": f"{head}\n\n完整資訊 👉 {SITE}/?from=threads",
    }


def gallery(outdir, files, caps, sat, sun):
    imgs = "".join(f'<a href="{f}" download><img src="{f}" loading="lazy"></a>' for f in files)
    blocks = "".join(
        f'<h3>{lab}</h3><textarea id="{k}" readonly>{e(caps[k])}</textarea><button onclick="navigator.clipboard.writeText(document.getElementById(\'{k}\').value);this.textContent=\'已複製\'">複製文案</button>'
        for k, lab in (("ig", "Instagram"), ("fb", "Facebook"), ("threads", "Threads")))
    (outdir / "index.html").write_text(f"""<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex">
<title>週末精選圖卡 {md(sat)}–{md(sun)}</title><style>
body{{font-family:system-ui,sans-serif;background:#fbf5e9;color:#3a2e28;margin:0;padding:16px;max-width:720px;margin:auto}}
.g{{display:grid;grid-template-columns:1fr 1fr;gap:10px}}.g img{{width:100%;border-radius:10px;border:2px solid #3a2e28}}
textarea{{width:100%;height:220px;font-size:15px;border-radius:10px;padding:10px;box-sizing:border-box}}
button{{font-size:16px;padding:8px 18px;border-radius:999px;border:2px solid #3a2e28;background:#fff3d6;margin:6px 0 14px}}
</style></head><body><h2>週末精選圖卡 {md(sat)}（六）–{md(sun)}（日）</h2>
<p>長按圖片可存到相簿（照順序 01、02…上傳成輪播）。</p><div class="g">{imgs}</div>{blocks}</body></html>""", encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date"); ap.add_argument("--skip", action="append", default=[])
    a = ap.parse_args()
    today = dt.date.fromisoformat(a.date) if a.date else taipei_today()
    sat = today + dt.timedelta(days=(5 - today.weekday()) % 7); sun = sat + dt.timedelta(days=1)
    picks = pick(load_events(), sat, sun, a.skip)
    outdir = ROOT / "social" / sat.isoformat(); outdir.mkdir(parents=True, exist_ok=True)
    for old in outdir.glob("*.png"): old.unlink()
    slides = [cover_html(sat, sun, {k: len(v) for k, v in picks.items()})]
    for r in REGIONS:
        items = picks[r[0]]
        chunks = [items[i:i + PER_SLIDE] for i in range(0, len(items), PER_SLIDE)]
        for i, ch in enumerate(chunks, 1):
            slides.append(region_html(r, ch, sat, sun, i, len(chunks)))
    slides.append(end_html())
    files = []
    with sync_playwright() as p:
        b = p.chromium.launch(); pg = b.new_page(viewport={"width": 1080, "height": 1350})
        for i, h in enumerate(slides, 1):
            tmp = outdir / "_tmp.html"; tmp.write_text(h, encoding="utf-8")
            pg.goto(tmp.as_uri()); pg.wait_for_timeout(400)
            name = f"{i:02d}.png"; pg.screenshot(path=str(outdir / name)); files.append(name)
        tmp.unlink(); b.close()
    caps = captions(picks, sat, sun)
    (outdir / "captions.txt").write_text("\n\n==========\n\n".join(f"[{k}]\n{v}" for k, v in caps.items()), encoding="utf-8")
    (outdir / "picks.json").write_text(json.dumps({k: [x["n"] for x in v] for k, v in picks.items()}, ensure_ascii=False, indent=1), encoding="utf-8")
    gallery(outdir, files, caps, sat, sun)
    print(f"{len(files)} slides -> social/{sat.isoformat()}/ ; picks:", {k: len(v) for k, v in picks.items()})


if __name__ == "__main__":
    main()
