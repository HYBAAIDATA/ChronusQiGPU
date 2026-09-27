#!/usr/bin/env node
import { writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { chromium } from "playwright";

const here = dirname(fileURLToPath(import.meta.url));
const playfair = pathToFileURL(join(here, "../brand-fonts/PlayfairDisplay-Variable.ttf")).href;
const garamond = pathToFileURL(join(here, "../brand-fonts/EBGaramond.ttf")).href;

function cassiniPath({ a = 1.18, c = 1, samples = 900, width = 360, height = 188, pad = 10 }) {
  const pts = [];
  for (let i = 0; i < samples; i += 1) {
    const th = (2 * Math.PI * i) / samples;
    const disc = a ** 4 - c ** 4 * Math.sin(2 * th) ** 2;
    const r2 = c ** 2 * Math.cos(2 * th) + Math.sqrt(Math.max(disc, 0));
    const r = Math.sqrt(Math.max(r2, 0));
    pts.push([r * Math.cos(th), r * Math.sin(th)]);
  }
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
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

const css = `
@font-face { font-family: "Playfair Display"; src: url("${playfair}") format("truetype"); font-weight: 400 900; font-display: block; }
@font-face { font-family: "EB Garamond"; src: url("${garamond}") format("truetype"); font-weight: 500; font-display: block; }
html, body { margin:0; padding:0; width:1200px; height:630px; background:#0B0B0C; overflow:hidden; }
.stage { width:1200px; height:630px; display:flex; flex-direction:column; align-items:center; justify-content:center; }
h1 { margin:0; color:#EEEAE2; font-family:"Playfair Display", serif; font-weight:500; font-size:92px; letter-spacing:0.46em; margin-right:-0.46em; line-height:1; font-kerning:none; font-feature-settings:"liga" 0, "kern" 0; }
p { margin:26px 0 0 0; color:#7D9A86; font-family:"EB Garamond", serif; font-weight:500; font-size:17px; letter-spacing:0.055em; line-height:1.2; }
svg.mark { display:block; margin:0 0 40px 0; }
`;

const lockup = `
    <h1>PYTHIA</h1>
    <p>Algebraic mining operator — SHA-256d is the sole accept authority.</p>
`;

const vesica = `<svg class="mark" width="360" height="200" viewBox="0 0 360 200" fill="none" xmlns="http://www.w3.org/2000/svg">
  <circle cx="130" cy="100" r="96" stroke="#C8CCD4" stroke-width="1.7"/>
  <circle cx="230" cy="100" r="96" stroke="#C8CCD4" stroke-width="1.7"/>
</svg>`;

const cassiniPeanut = `<svg class="mark" width="360" height="188" viewBox="0 0 360 188" fill="none" xmlns="http://www.w3.org/2000/svg">
  <path d="${cassiniPath({ a: 1.18, width: 360, height: 188 })}" stroke="#C8CCD4" stroke-width="1.7" stroke-linejoin="round"/>
</svg>`;

const cassiniOval = `<svg class="mark" width="360" height="188" viewBox="0 0 360 188" fill="none" xmlns="http://www.w3.org/2000/svg">
  <path d="${cassiniPath({ a: 1.42, width: 360, height: 188 })}" stroke="#C8CCD4" stroke-width="1.7" stroke-linejoin="round"/>
</svg>`;

function pageHtml(mark) {
  return `<!DOCTYPE html><html><head><meta charset="utf-8"><style>${css}</style></head>
<body><div class="stage">${mark}${lockup}</div></body></html>`;
}

writeFileSync(join(here, "og-vesica.html"), pageHtml(vesica));
writeFileSync(join(here, "og-cassini-peanut.html"), pageHtml(cassiniPeanut));
writeFileSync(join(here, "og-cassini-oval.html"), pageHtml(cassiniOval));

const faviconPreview = `<!DOCTYPE html><html><head><meta charset="utf-8">
<style>
html,body{margin:0;background:#4a4a4a}
.row{display:flex;gap:16px;padding:16px;align-items:center}
img.px16{width:16px;height:16px}
img.px32{width:32px;height:32px}
img.px64{width:64px;height:64px}
</style></head>
<body>
<div class="row">
  <img class="px16" src="${pathToFileURL(join(here, "favicon.svg")).href}" alt="16">
  <img class="px32" src="${pathToFileURL(join(here, "favicon.svg")).href}" alt="32">
  <img class="px64" src="${pathToFileURL(join(here, "favicon.svg")).href}" alt="64">
</div>
</body></html>`;
writeFileSync(join(here, "favicon-sizes.html"), faviconPreview);

const browser = await chromium.launch({
  headless: true,
  args: ["--no-sandbox", "--disable-dev-shm-usage"],
});

async function shot(htmlFile, out, w = 1200, h = 630) {
  const page = await browser.newPage({ viewport: { width: w, height: h }, deviceScaleFactor: 1 });
  await page.goto(pathToFileURL(join(here, htmlFile)).href, { waitUntil: "load" });
  await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(150);
  await page.screenshot({ path: join(here, out), type: "png" });
  await page.close();
}

await shot("og-vesica.html", "og-vesica.png");
await shot("og-cassini-peanut.html", "og-cassini-peanut.png");
await shot("og-cassini-oval.html", "og-cassini-oval.png");
await shot("favicon-sizes.html", "favicon-sizes.png", 280, 96);
await browser.close();
console.log("variants written");
