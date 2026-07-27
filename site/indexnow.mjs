// IndexNow ping — notifies Bing/Yandex/Seznam/Naver of the current URL set so
// they crawl fresh episodes fast (Google does not support IndexNow). Runs at
// the end of `npm run build`, but only on Cloudflare Pages (CF_PAGES is set)
// so local builds don't ping. Never fails the build.
//
// Key must be live at https://podcast.jpnotes.dev/<key>.txt (site/public/).
// Same pattern as jpnotes.dev's indexnow.mjs in the japanese repo.
import fs from "node:fs";

const KEY = "b25394c3a16456aefab2502b078c56ed";
const HOST = "podcast.jpnotes.dev";

if (!process.env.CF_PAGES) {
  console.log("IndexNow: not a Cloudflare Pages build, skipping ping.");
  process.exit(0);
}

const sitemap = fs.readFileSync("dist/sitemap.xml", "utf-8");
const urlList = [...sitemap.matchAll(/<loc>(.*?)<\/loc>/g)].map((m) => m[1]);

if (urlList.length === 0) {
  console.log("IndexNow: no URLs found in dist/sitemap.xml, skipping.");
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
  console.log(`IndexNow: submitted ${urlList.length} URLs → HTTP ${res.status}`);
} catch (err) {
  console.log(`IndexNow: ping failed (non-fatal): ${err.message}`);
}
