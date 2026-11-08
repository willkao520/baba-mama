# 產生給 Google 搜尋用的靜態頁面：每個縣市一頁、每種景點分類一頁，加上 sitemap.xml
# 用法：python3 scripts/seo.py   （需要 playwright + chromium）
import html, json, os, subprocess, sys, time, datetime
from urllib.parse import quote
from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = "https://baba-mama.pages.dev"
OUT = os.path.join(ROOT, "tw")
SLUG = {"基隆市":"keelung","臺北市":"taipei","新北市":"new-taipei","桃園市":"taoyuan","新竹市":"hsinchu-city","新竹縣":"hsinchu-county","宜蘭縣":"yilan",
 "苗栗縣":"miaoli","臺中市":"taichung","彰化縣":"changhua","南投縣":"nantou","雲林縣":"yunlin","嘉義市":"chiayi-city","嘉義縣":"chiayi-county",
 "臺南市":"tainan","高雄市":"kaohsiung","屏東縣":"pingtung","花蓮縣":"hualien","臺東縣":"taitung","澎湖縣":"penghu","金門縣":"kinmen","連江縣":"matsu"}
CSLUG = {"博物館・美術館":"museum","科學・教育館":"science","主題樂園":"theme-park","動物園・水族館":"zoo","農場・牧場":"farm","採果・釣魚":"picking","觀光工廠":"factory",
 "文化・鐵道園區":"culture","室內遊戲・親子館":"indoor","森林・自然":"nature"}
AGE = {"baby":"0–3歲","pre":"4–6歲","low":"小一～小三","high":"小四～小六"}
FEE = {"free":"免費","paid":"付費","deal":"門票優惠","check":"費用待確認"}

def load_data():
    srv = subprocess.Popen([sys.executable, "-m", "http.server", "8799"], cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1.5)
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(); pg = b.new_page()
            pg.goto("http://localhost:8799/index.html"); pg.wait_for_timeout(1500)
            pg.wait_for_function("liveCourses.length>500 || performance.now()>15000", timeout=20000)
            data = pg.evaluate("""()=>{const f=d=>d?`${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`:null;
              const pick=x=>({n:x.n,c:x.c,d:x.d||'',t:x.t||'',note:x.note||'',a:x.a||[],f:x.f||'',io:x.io||'',v:x.v||'',s:f(x.S),e:f(x.E),cc:x.cc||'',ses:x.ses||'',
                 l:Array.isArray(x.l)?x.l[1]:(x.l||''),r:x.r||''});
              return {order:COUNTY_ORDER,region:REGION,ev:liveEvents.map(pick),pk:PARKS.map(pick),pl:PLACES.map(pick),co:liveCourses.filter(x=>x.sub!=='官方活動總表').map(pick)};}""")
            b.close(); return data
    finally:
        srv.kill()

e = html.escape
def maps(x): return "https://www.google.com/maps/search/?api=1&query=" + quote(f"{x.get('v') or x['n']} {x['c']}{x['d']}")
def ages(x): return "・".join(AGE[a] for a in x["a"] if a in AGE) if len(x["a"]) < 4 else "全年齡"
def date(x):
    if not x.get("s"): return ""
    s = x["s"][5:].replace("-", "/"); en = (x.get("e") or "")[5:].replace("-", "/")
    return s if not en or en == s else f"{s}–{en}"

def item(x, kind):
    bits = [f'<a class="map" href="{e(maps(x))}" rel="nofollow noopener" target="_blank">📍 {e(x["c"])}{"・"+e(x["d"]) if x["d"] else ""}</a>']
    if kind in ("ev", "co") and date(x): bits.insert(0, f'<span class="dt">{e(date(x))}</span>')
    meta = " ".join(filter(None, [ages(x), FEE.get(x["f"], ""), {"in":"室內","out":"戶外","both":"室內外"}.get(x["io"], "")]))
    link = x["l"] if x["l"] and "google.com/search" not in x["l"] else ""
    off = f' <a href="{e(link)}" rel="nofollow noopener" target="_blank">{"報名・官網" if kind=="co" else "官網"} ↗</a>' if link else ""
    note = f"<p>{e(x['note'][:140])}</p>" if x["note"] else ""
    extra = f'<div class="ses">{e(x["ses"][:120])}</div>' if kind == "co" and x.get("ses") else ""
    return f'<li><h3>{e(x["n"])}</h3><div class="m">{" ".join(bits)} <span class="tg">{e(meta)}</span>{off}</div>{extra}{note}</li>'

CSS = """body{margin:0;font-family:"Noto Sans TC",system-ui,sans-serif;background:#fbf6ec;color:#3a2e28;line-height:1.6}
.w{max-width:900px;margin:0 auto;padding:18px 16px 60px}a{color:#2f6fb0}
header a.home{font-weight:700;text-decoration:none;color:#3a2e28;font-size:18px;display:inline-flex;align-items:center;gap:8px}h1{font-size:26px;margin:14px 0 6px}
.lead{color:#6b5a50}.cta{display:inline-block;background:#f1b33b;border:2.5px solid #3a2e28;border-radius:14px;padding:10px 18px;color:#3a2e28;font-weight:700;text-decoration:none;box-shadow:3px 3px 0 #3a2e28;margin:10px 0}
h2{margin:28px 0 8px;font-size:21px;border-bottom:2px dashed #d9c9b4;padding-bottom:4px}ul{list-style:none;padding:0;margin:0}
li{background:#fff;border:2px solid #3a2e28;border-radius:14px;padding:10px 14px;margin:10px 0}li h3{margin:0 0 4px;font-size:17px}
.m{font-size:14px}.dt{background:#fff3d6;border-radius:8px;padding:0 6px;margin-right:6px}.tg{color:#6b5a50}.ses{font-size:13px;color:#6b5a50}
li p{margin:4px 0 0;font-size:14px}nav.links a{display:inline-block;margin:4px 8px 4px 0}.more{font-size:14px}footer{margin-top:40px;font-size:13px;color:#6b5a50}"""

def page(path, title, desc, body, crumbs=""):
    url = f"{SITE}/tw/{path}"
    doc = f"""<!DOCTYPE html><html lang="zh-Hant-TW"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(title)}</title><meta name="description" content="{e(desc)}"><link rel="canonical" href="{url}">
<meta property="og:type" content="website"><meta property="og:title" content="{e(title)}"><meta property="og:description" content="{e(desc)}">
<meta property="og:url" content="{url}"><meta property="og:image" content="{SITE}/og.png"><meta name="twitter:card" content="summary_large_image">
<link rel="icon" type="image/png" sizes="32x32" href="/icons/favicon-32.png"><link rel="apple-touch-icon" href="/icons/apple-touch-icon.png"><style>{CSS}</style></head><body><div class="w">
<header><a class="home" href="/"><img src="/icons/logo-mark.png" width="40" height="40" alt="">爸~媽!!假日要去哪裡玩</a>{crumbs}</header>{body}
<footer>資料整理自各縣市政府、場館與主辦單位公開資訊，出發前請再到官方網站確認。更新日期：{datetime.date.today().isoformat()}　<a href="/">回首頁用年齡、縣市篩選 →</a></footer>
</div></body></html>"""
    os.makedirs(os.path.dirname(os.path.join(OUT, path)), exist_ok=True)
    open(os.path.join(OUT, path), "w", encoding="utf-8").write(doc)
    return url

def main():
    d = load_data(); urls = [SITE + "/"]
    counties = [c for c in d["order"] if any(x["c"] == c for k in ("ev","pk","pl","co") for x in d[k])]
    nav = '<nav class="links">' + "".join(f'<a href="/tw/{SLUG[c]}.html">{e(c)}</a>' for c in counties) + "</nav>"
    catnav = '<nav class="links">' + "".join(f'<a href="/tw/cat-{s}.html">{e(c)}</a>' for c, s in CSLUG.items()) + "</nav>"
    for c in counties:
        ev = [x for x in d["ev"] if x["c"] == c]; pk = [x for x in d["pk"] if x["c"] == c]
        pl = [x for x in d["pl"] if x["c"] == c]; co = [x for x in d["co"] if x["c"] == c]
        q = quote(c)
        body = f'<h1>{e(c)}親子景點、共融公園與親子活動</h1><p class="lead">{e(c)}帶小孩去哪玩？整理 {len(pk)} 座共融公園、{len(pl)} 個親子景點、{len(ev)} 個近期親子活動、{len(co)} 場公辦親子課程（圖書館、親子館、運動中心）。</p>'
        body += f'<a class="cta" href="/?c={q}">打開互動版，依年齡和室內外篩選 →</a>'
        if ev: body += f'<h2>{e(c)}近期親子活動（{len(ev)}）</h2><ul>' + "".join(item(x, "ev") for x in ev[:60]) + "</ul>"
        if pk: body += f'<h2>{e(c)}共融公園・特色遊戲場（{len(pk)}）</h2><ul>' + "".join(item(x, "pk") for x in pk[:150]) + "</ul>" + (f'<p class="more"><a href="/?tab=pk&c={q}">看全部 {len(pk)} 座 →</a></p>' if len(pk) > 150 else "")
        for cat in CSLUG:
            xs = [x for x in pl if x["t"] == cat]
            if xs: body += f'<h2>{e(c)}{e(cat)}（{len(xs)}）</h2><ul>' + "".join(item(x, "pl") for x in xs) + "</ul>"
        if co: body += f'<h2>{e(c)}公辦親子活動・課程（近期 {len(co)} 場）</h2><ul>' + "".join(item(x, "co") for x in co[:80]) + "</ul>" + (f'<p class="more"><a href="/?tab=co&c={q}">看全部 {len(co)} 場，依分類篩選 →</a></p>' if len(co) > 80 else "")
        body += "<h2>其他縣市</h2>" + nav + "<h2>依景點類型</h2>" + catnav
        urls.append(page(f"{SLUG[c]}.html", f"{c}親子景點・共融公園・親子活動推薦｜爸~媽!!假日要去哪裡玩",
            f"{c}帶小孩去哪玩？{len(pk)} 座共融公園、{len(pl)} 個親子景點、近期親子活動與免費公辦親子課程，依年齡整理，點一下開地圖導航。", body))
    for cat, s in CSLUG.items():
        xs = [x for x in d["pl"] if x["t"] == cat]
        if not xs: continue
        body = f'<h1>全台{e(cat)}親子景點（{len(xs)} 個）</h1><p class="lead">依縣市整理全台適合 0–12 歲小孩的{e(cat)}，附地圖導航和官網連結。</p><a class="cta" href="/?tab=pl&cat={quote(cat)}">打開互動版篩選 →</a>'
        for c in counties:
            ys = [x for x in xs if x["c"] == c]
            if ys: body += f'<h2>{e(c)}（{len(ys)}）</h2><ul>' + "".join(item(x, "pl") for x in ys) + "</ul>"
        body += "<h2>其他類型</h2>" + catnav + "<h2>依縣市</h2>" + nav
        urls.append(page(f"cat-{s}.html", f"全台{cat}親子景點推薦｜爸~媽!!假日要去哪裡玩", f"全台 {len(xs)} 個適合帶小孩去的{cat}，依縣市整理，附地圖導航與官網。", body))
    hub = '<h1>全台親子景點・共融公園・親子活動 地區索引</h1><p class="lead">選縣市或景點類型，看帶小孩可以去哪裡。</p><a class="cta" href="/">打開互動版 →</a><h2>依縣市</h2>' + nav + "<h2>依景點類型</h2>" + catnav
    urls.append(page("index.html", "全台親子景點・共融公園・親子活動 地區索引｜爸~媽!!假日要去哪裡玩", "依縣市與景點類型整理的全台親子景點、共融公園、親子活動索引。", hub))
    today = datetime.date.today().isoformat()
    sm = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + "".join(f"<url><loc>{u}</loc><lastmod>{today}</lastmod></url>\n" for u in urls) + "</urlset>\n"
    open(os.path.join(ROOT, "sitemap.xml"), "w").write(sm)
    open(os.path.join(ROOT, "robots.txt"), "w").write(f"User-agent: *\nAllow: /\nDisallow: /admin.html\nSitemap: {SITE}/sitemap.xml\n")
    print(f"seo: {len(urls)} 頁")

if __name__ == "__main__":
    main()
