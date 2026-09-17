// 样张目视核对截图：把一篇主题样张的「顶部区 + 流程图 + 代码块」各截一张，
// 交给合成脚本拼成一张竖图，方便一次看清配色、卡片质感与代码块配色。
// 用法：node shot_article.js <html绝对路径> <输出目录> <名字前缀> [宽度=390]
const { chromium } = require('playwright-core');

const CHROME = 'C:/Program Files/Google/Chrome/Application/chrome.exe';

(async () => {
  const [file, outDir, name, wArg] = process.argv.slice(2);
  const W = parseInt(wArg || '390', 10);
  const browser = await chromium.launch({ headless: true, executablePath: CHROME });
  const page = await browser.newPage({ viewport: { width: W, height: 1600 }, deviceScaleFactor: 2 });
  await page.goto('file:///' + file.replace(/\\/g, '/'), { waitUntil: 'load' });
  await page.waitForTimeout(500);

  const shots = {};
  const cap = async (key, clip) => {
    if (!clip) return;
    await page.screenshot({
      path: `${outDir}/${name}-${key}.png`,
      fullPage: true,
      clip: { x: Math.max(0, clip.x), y: Math.max(0, clip.y),
              width: Math.min(W - Math.max(0, clip.x), clip.w),
              height: clip.h },
    });
    shots[key] = `${outDir}/${name}-${key}.png`;
  };

  const full = await page.evaluate(() => document.documentElement.scrollHeight);
  await cap('top', { x: 0, y: 0, w: W, h: Math.min(1250, full) });

  const boxOf = (sel) => page.evaluate((sel) => {
    const el = document.querySelector(sel);
    if (!el) return null;
    const r = el.getBoundingClientRect();
    return { x: r.x + window.scrollX, y: r.y + window.scrollY, w: r.width, h: r.height };
  }, sel);

  const dia = await boxOf('img[src*="mermaid-1"]');
  if (dia) await cap('diagram', { x: dia.x, y: dia.y - 8, w: dia.w, h: Math.min(dia.h + 16, 900) });

  const code = await page.evaluate(() => {
    const p = [...document.querySelectorAll('p')]
      .find((el) => /monospace/.test(el.getAttribute('style') || ''));
    if (!p) return null;
    let s = p.closest('section');
    while (s && s.parentElement && !/overflow-x/.test(s.getAttribute('style') || '')) {
      s = s.parentElement;
    }
    const r = (s || p).getBoundingClientRect();
    return { x: r.x + window.scrollX, y: r.y + window.scrollY, w: r.width, h: r.height };
  });
  if (code) await cap('code', { x: code.x, y: code.y - 8, w: code.w, h: Math.min(code.h + 16, 1000) });

  await browser.close();
  console.log(JSON.stringify(shots));
})();
