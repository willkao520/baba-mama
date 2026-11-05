// 每天從「北台灣親子地圖 kidsmap.tw」抓公辦親子活動，轉成本站用的 kidsmap.json
// 用法：node scripts/kidsmap.mjs [來源檔或網址] [輸出檔]
import fs from "node:fs";
const SRC = process.argv[2] || "https://kidsmap.tw/data.json";
const OUT = process.argv[3] || "kidsmap.json";
const raw = SRC.startsWith("http")
  ? await (await fetch(SRC, { headers: { "User-Agent": "baba-mama-site (family outings directory)" } })).json()
  : JSON.parse(fs.readFileSync(SRC, "utf8"));

const tz = new Date(Date.now() + 8 * 3600e3);              // 台灣時間
const TODAY = tz.toISOString().slice(0, 10);
const LIMIT = new Date(tz.getTime() + 60 * 864e5).toISOString().slice(0, 10);
const WD = "日一二三四五六";
const md = d => { const [y, m, dd] = d.split("-").map(Number); const w = new Date(Date.UTC(y, m - 1, dd)).getUTCDay(); return `${m}/${dd}（${WD[w]}）`; };
const city = c => (c || "").replace(/^台/, "臺");
const KIND = { "親子館": "親子館", "圖書館": "圖書館", "運動中心": "運動中心", "博物館": "博物館", "展演": "表演場館" };
const ageKeys = (a0, a1, txt) => {
  if (a0 == null && a1 == null) {
    if (/寶寶|嬰|0-3|0～3|幼兒/.test(txt || "")) return ["baby", "pre"];
    return ["baby", "pre", "low", "high"];
  }
  const lo = a0 ?? 0, hi = a1 ?? 155, r = [];
  [["baby", 0, 47], ["pre", 48, 83], ["low", 84, 119], ["high", 120, 155]].forEach(([k, a, b]) => { if (lo <= b && hi >= a) r.push(k); });
  return r;
};
const ADULT = /限家長|成人|銀髮|長者|樂齡|孕婦|準爸媽|TRX|肌力訓練|瑜珈|皮拉提斯|飛輪|有氧/;
const out = [];
for (const x of raw.courses || []) {
  if (!x.url || !x.name) continue;
  if (x.a0 != null && x.a0 >= 156) continue;                 // 13 歲以上
  if (ADULT.test(x.name + (x.type || "")) && !/親子|兒童|幼兒|寶寶/.test(x.name)) continue;
  const ses = (x.sessions || []).filter(s => s.d && s.d >= TODAY && s.d <= LIMIT && s.st !== "closed");
  const longRun = x.range && x.range[1] >= TODAY && x.range[0] <= LIMIT;
  if (!ses.length && !longRun) continue;
  const a = ageKeys(x.a0, x.a1, x.ageText);
  if (!a.length) continue;
  let sesText, s, e;
  if (longRun && (!ses.length || ses.every(z => z.st === "onsite" || z.st === "info") && ses.length <= 2)) {
    s = x.range[0] < TODAY ? TODAY : x.range[0]; e = x.range[1];
    sesText = `${md(x.range[0])} ～ ${md(x.range[1])}，開放時間內`;
  } else {
    s = ses[0].d; e = ses[ses.length - 1].d;
    const seen = new Set(), list = [];
    for (const z of ses) { const k = z.d + z.t; if (seen.has(k)) continue; seen.add(k); list.push(`${md(z.d)}${z.t && z.t !== "00:00-00:00" ? " " + z.t.replace("-", "–") : ""}`); }
    sesText = list.slice(0, 4).join("、") + (list.length > 4 ? ` 等 ${list.length} 場` : "");
    if (x.term) sesText = x.term + "｜" + sesText;
  }
  // 名額：最近一場可報名的
  const nb = ses.find(z => z.st === "open" && z.left != null) || ses.find(z => z.st === "open") || ses.find(z => z.st === "soon") || ses[0];
  let cap = "見活動頁";
  if (nb) {
    if (nb.st === "open" && nb.left != null) cap = `最近一場剩 ${nb.left}${nb.cap ? "／" + nb.cap : ""} 位`;
    else if (nb.st === "open") cap = nb.cap ? `每場 ${nb.cap} 位，尚可報名` : "尚可報名";
    else if (nb.st === "full") cap = "最近場次已額滿，可看其他場次";
    else if (nb.st === "soon") cap = nb.opens ? `${md(nb.opens.slice(0, 10))} ${nb.opens.slice(11, 16)} 開放報名` : "即將開放報名";
    else if (nb.st === "onsite") cap = "現場參加，額滿為止";
  }
  const f = x.fee === 0 ? "free" : x.fee > 0 ? "paid" : /免費/.test(x.feeText || "") ? "free" : "check";
  const note = [x.ageText && x.ageText.length < 40 ? "對象：" + x.ageText : "", x.feeText ? "費用：" + x.feeText : "", x.place && x.place !== x.venue && x.place.length < 40 ? "地點：" + x.place : "", x.teacher && x.teacher !== x.venue && x.teacher.length < 20 ? "帶領：" + x.teacher : ""].filter(Boolean).join("　");
  out.push({
    n: x.name.replace(/【請於活動開始前.*?】/g, "").trim().slice(0, 80),
    t: KIND[x.kind] || (x.src === "ntsec" ? "科學館" : "親子館"),
    c: city(x.city), d: x.dist || "", v: x.venue || "", s, e,
    sub: (x.type || "").slice(0, 20), a, ses: sesText, cap,
    reg: (x.cond || "請看活動頁").slice(0, 120), l: x.url, note, f
  });
}
out.sort((p, q) => p.s.localeCompare(q.s));
const res = { built: raw.built || "", fetched: new Date().toISOString(), today: TODAY, items: out };
fs.writeFileSync(OUT, JSON.stringify(res));
console.log(`kidsmap: ${out.length} 筆（原始 ${(raw.courses || []).length}）→ ${OUT}，${(fs.statSync(OUT).size / 1024).toFixed(0)} KB`);
