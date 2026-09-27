#!/usr/bin/env node
import { writeFileSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { chromium } from "playwright";

const here = dirname(fileURLToPath(import.meta.url));
const htmlPath = join(here, "og.html");
const pngPath = join(here, "og-raw.png");
const faviconHtmlPath = join(here, "favicon-preview.html");
const faviconPngPath = join(here, "favicon-16.png");

function cassiniPath({ a = 1.18, c = 1, samples = 720, width = 320, height = 168, pad = 8 }) {
  const pts = [];
  for (let i = 0; i < samples; i += 1) {
    const th = (2 * Math.PI * i) / samples;
    const disc = a ** 4 - c ** 4 * Math.sin(2 * th) ** 2;
    const r2 = c ** 2 * Math.cos(2 * th) + Math.sqrt(Math.max(disc, 0));
    const r = Math.sqrt(Math.max(r2, 0));
    pts.push([r * Math.cos(th), r * Math.sin(th)]);
  }
  let minX = Infinity;
  let minY = Infinity;
  let maxX = -Infinity;
  let maxY = -Infinity;
  for (const [x, y] of pts) {
    if (x < minX) minX = x;
    if (y < minY) minY = y;
    if (x > maxX) maxX = x;
    if (y > maxY) maxY = y;
  }
  const innerW = width - pad * 2;
  const innerH = height - pad * 2;
  const scale = Math.min(innerW / (maxX - minX), innerH / (maxY - minY));
  const ox = (width - (maxX - minX) * scale) / 2 - minX * scale;
  const oy = (height - (maxY - minY) * scale) / 2 - minY * scale;
  return pts
    .map(([x, y], i) => `${i === 0 ? "M" : "L"}${(ox + x * scale).toFixed(2)},${(oy + y * scale).toFixed(2)}`)
    .join(" ")
    .concat(" Z");
}

const oval = cassiniPath({});
const playfair = pathToFileURL(join(here, "../brand-fonts/PlayfairDisplay-Variable.ttf")).href;
const garamond = pathToFileURL(join(here, "../brand-fonts/EBGaramond.ttf")).href;
const cormorant = pathToFileURL(join(here, "../brand-fonts/CormorantGaramond-Medium.ttf")).href;
const faviconSvg = pathToFileURL(join(here, "favicon.svg")).href;

const html = `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<style>
@font-face {
  font-family: "Playfair Display";
  src: url("${playfair}") format("truetype");
  font-weight: 400 900;
  font-style: normal;
  font-display: block;
}
@font-face {
  font-family: "EB Garamond";
  src: url("${garamond}") format("truetype");
  font-weight: 500;
  font-style: normal;
  font-display: block;
}
@font-face {
  font-family: "Cormorant Garamond";
  src: url("${cormorant}") format("truetype");
  font-weight: 500;
  font-style: normal;
  font-display: block;
}
html, body {
  margin: 0;
  padding: 0;
  width: 1200px;
  height: 630px;
  background: #0B0B0C;
  overflow: hidden;
}
.stage {
  width: 1200px;
  height: 630px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}
svg.mark {
  width: 320px;
  height: 168px;
  display: block;
  margin: 0 0 36px 0;
}
h1 {
  margin: 0;
  color: #EEEAE2;
  font-family: "Playfair Display", serif;
  font-weight: 500;
  font-size: 92px;
  letter-spacing: 0.46em;
  margin-right: -0.46em;
  line-height: 1;
  font-kerning: none;
  font-feature-settings: "liga" 0, "kern" 0;
}
p {
  margin: 26px 0 0 0;
  color: #7D9A86;
  font-family: "EB Garamond", "Cormorant Garamond", serif;
  font-weight: 500;
  font-size: 17px;
  letter-spacing: 0.055em;
  line-height: 1.2;
}
</style>
</head>
<body>
  <div class="stage">
    <svg class="mark" viewBox="0 0 320 168" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <path d="${oval}" stroke="#C8CCD4" stroke-width="1.35" stroke-linejoin="round"/>
    </svg>
    <h1>PYTHIA</h1>
    <p>Algebraic mining operator — SHA-256d is the sole accept authority.</p>
  </div>
</body>
</html>
`;

const faviconPreview = `<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
html,body{margin:0;padding:0;background:#888;width:64px;height:64px}
img{width:16px;height:16px;image-rendering:pixelated;display:block;margin:24px}
</style></head>
<body><img src="${faviconSvg}" alt=""></body></html>
`;

writeFileSync(htmlPath, html);
writeFileSync(faviconHtmlPath, faviconPreview);

const browser = await chromium.launch({
  headless: true,
  args: ["--no-sandbox", "--disable-dev-shm-usage"],
});
const page = await browser.newPage({
  viewport: { width: 1200, height: 630 },
  deviceScaleFactor: 1,
});
await page.goto(pathToFileURL(htmlPath).href, { waitUntil: "load" });
await page.evaluate(() => document.fonts.ready);
await page.waitForTimeout(200);
await page.screenshot({ path: pngPath, type: "png" });

const favPage = await browser.newPage({
  viewport: { width: 64, height: 64 },
  deviceScaleFactor: 2,
});
await favPage.goto(pathToFileURL(faviconHtmlPath).href, { waitUntil: "load" });
await favPage.screenshot({ path: faviconPngPath, type: "png" });
await browser.close();
console.log("wrote", pngPath, faviconPngPath);
