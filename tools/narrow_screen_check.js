// 多档宽度溢出测量：body/documentElement scrollWidth 不得超视口；
// 同时验证代码块横滑容器真的可滚（scrollWidth > clientWidth）。
const { chromium } = require('playwright-core');

const WIDTHS = [288, 320, 328, 342, 375, 390, 414, 428, 768, 1280];

(async () => {
  const file = 'file:///' + process.argv[2].replace(/\\/g, '/');
  const browser = await chromium.launch({
    headless: true,
    executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe',
  });
  let fail = 0;
  for (const w of WIDTHS) {
    const page = await browser.newPage({ viewport: { width: w, height: 1200 } });
    await page.goto(file, { waitUntil: 'load' });
    const r = await page.evaluate(() => {
      const de = document.documentElement, body = document.body;
      const sw = Math.max(de.scrollWidth, body.scrollWidth);
      // 找出把页面撑宽的元素（排除横滑容器内部：有 overflow-x 的祖先之内不算）
      const offenders = [];
      const inScroller = (el) => {
        for (let a = el.parentElement; a; a = a.parentElement) {
          const ov = getComputedStyle(a).overflowX;
          if (ov === 'auto' || ov === 'scroll') return true;
        }
        return false;
      };
      const vw = de.clientWidth;
      document.querySelectorAll('body *').forEach((el) => {
        const rect = el.getBoundingClientRect();
        if (rect.width > 0 && rect.right > vw + 0.5 && !inScroller(el)) {
          offenders.push(el.tagName + '.' + (el.getAttribute('style') || '').slice(0, 40) +
            ' right=' + Math.round(rect.right));
        }
      });
      // 代码块横滑验证：找 overflow-x:auto 容器，看内容是否真超宽可滚
      let scroller = null;
      document.querySelectorAll('section').forEach((el) => {
        if (getComputedStyle(el).overflowX === 'auto' && el.scrollWidth > el.clientWidth + 2) {
          scroller = { sw: el.scrollWidth, cw: el.clientWidth };
        }
      });
      return { sw, vw, offenders: offenders.slice(0, 4), scroller };
    });
    const ok = r.sw <= r.vw;
    if (!ok) fail++;
    console.log(
      `${ok ? 'PASS' : 'FAIL'} @${String(w).padStart(4)}px  page=${r.sw}/${r.vw}` +
      (r.scroller ? `  代码横滑: 内容${r.scroller.sw}px/可视${r.scroller.cw}px ✔` : '') +
      (r.offenders.length ? `  溢出元素: ${r.offenders.join(' | ')}` : ''));
    await page.close();
  }
  await browser.close();
  process.exit(fail ? 1 : 0);
})();
