// IndexNow ping — notifies Bing/Yandex/Seznam/Naver of new and changed URLs so
// they crawl fresh episodes fast (Google does not support IndexNow). Runs in
// CI after the deploy (.github/workflows/deploy.yml sets INDEXNOW=1), so local
// builds don't ping. Never fails the build.
//
// Key must be live at https://podcast.jpnotes.dev/<key>.txt (site/public/).
// Same pattern as jpnotes.dev's indexnow.mjs in the japanese repo.
import fs from "node:fs";

const KEY = "b25394c3a16456aefab2502b078c56ed";
const HOST = "podcast.jpnotes.dev";

if (!process.env.INDEXNOW) {
  console.log("IndexNow: not the CI deploy, skipping ping.");
  process.exit(0);
}

// Submit only what changed (as jpnotes.dev does): IndexNow wants new or
// updated URLs, not the whole site on every deploy (2 deploys a day × ~530
// URLs). The "before" is the sitemap saved by CI just before the deploy
// (prev-sitemap.xml), else the live one.
function parse(xml) {
  const map = new Map();
  for (const block of xml.split("<url>").slice(1)) {
    const loc = block.match(/<loc>(.*?)<\/loc>/)?.[1];
    if (loc) map.set(loc, block.match(/<lastmod>(.*?)<\/lastmod>/)?.[1] || "");
  }
  return map;
}

const current = parse(fs.readFileSync("dist/sitemap.xml", "utf-8"));
let previous = null;
try {
  if (fs.existsSync("prev-sitemap.xml")) previous = parse(fs.readFileSync("prev-sitemap.xml", "utf-8"));
  else {
    const res = await fetch(`https://${HOST}/sitemap.xml`, { signal: AbortSignal.timeout(10000) });
    if (res.ok) previous = parse(await res.text());
  }
} catch { /* first deploy or network trouble: submit everything */ }

const homes = new Set([`https://${HOST}/`, `https://${HOST}/zh/`]); // episode lists change daily
const urlList = [...current.keys()].filter(loc =>
  !previous || homes.has(loc) || !previous.has(loc) || previous.get(loc) !== current.get(loc));

if (urlList.length === 0) {
  console.log("IndexNow: nothing changed, skipping.");
  process.exit(0);
}

const body = {
  host: HOST,
  key: KEY,
  keyLocation: `https://${HOST}/${KEY}.txt`,
  urlList, // IndexNow accepts up to 10,000 URLs per request
};

try {
  const res = await fetch("https://api.indexnow.org/indexnow", {
    method: "POST",
    headers: { "Content-Type": "application/json; charset=utf-8" },
    body: JSON.stringify(body),
  });
  // 200 = accepted, 202 = accepted & key validation pending. Both are success.
  console.log(`IndexNow: submitted ${urlList.length} new/changed of ${current.size} URLs → HTTP ${res.status}`);
} catch (err) {
  console.log(`IndexNow: ping failed (non-fatal): ${err.message}`);
}
