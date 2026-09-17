// mermaid → PNG 的**本地**渲染通道（playwright 驱动本机 Chrome）。
//
// 为什么要有它：mermaid.ink 在线通道的字形由对方服务器决定 —— 图里写什么
// font-family 都没用，服务器没装就是没装。想让流程图用上指定字体（霞鹜文楷 /
// 思源宋体 / 思源黑体），只有本地渲染这一条路。顺带两个好处：图表内容不再
// 发给第三方，体检用的 SVG 也能一次拿到（不必再单独请求一次 /svg）。
//
// 用法（参数走 JSON 文件，避免命令行转义地狱）：
//   node mermaid_local.js <params.json>
// params.json:
//   {
//     "mmd":      "flowchart LR\n A-->B",        // 图源码
//     "config":   { ...mermaid config json... }, // themeVariables 等
//     "out":      "C:/abs/path/mermaid-1.png",   // PNG 输出
//     "width":    800,                           // 位图像素宽 = width × scale
//     "scale":    3,
//     "bg":       "#FFFFFF",
//     "fontCss":  "@font-face{...}",             // 可空
//     "mermaidJs":"C:/abs/path/mermaid.min.js",  // mermaid 库
//     "svgOut":   "C:/abs/path/diagram.svg"      // 可空；体检用
//   }
//
// 退出码：0 成功 / 非 0 失败（stderr 带原因）。

const fs = require('fs');
const path = require('path');
const os = require('os');
const { chromium } = require('playwright-core');

const DEFAULT_CHROME = 'C:/Program Files/Google/Chrome/Application/chrome.exe';

function candidateChrome() {
  if (process.env.WMP_CHROME) return process.env.WMP_CHROME;
  const list = [
    DEFAULT_CHROME,
    'C:/Program Files (x86)/Google/Chrome/Application/chrome.exe',
    'C:/Program Files/Microsoft/Edge/Application/msedge.exe',
    'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
  ];
  for (const p of list) if (fs.existsSync(p)) return p;
  return null;
}

function fileUrl(p) {
  return 'file:///' + path.resolve(p).replace(/\\/g, '/').replace(/^\//, '');
}

(async () => {
  const paramsFile = process.argv[2];
  if (!paramsFile) {
    console.error('[mermaid_local] 用法：node mermaid_local.js <params.json>');
    process.exit(2);
  }
  const P = JSON.parse(fs.readFileSync(paramsFile, 'utf8'));
  const mmd = P.mmd || '';
  const cfg = P.config || {};
  const width = parseInt(P.width || 800, 10);
  const scale = parseInt(P.scale || 3, 10);
  const bg = P.bg || '#FFFFFF';
  const chrome = candidateChrome();
  if (!chrome) {
    console.error('[mermaid_local] 找不到本机 Chrome/Edge，设 WMP_CHROME 指一下');
    process.exit(3);
  }
  if (!P.mermaidJs || !fs.existsSync(P.mermaidJs)) {
    console.error('[mermaid_local] 找不到 mermaid.js：' + (P.mermaidJs || '(未指定)'));
    process.exit(4);
  }

  const html =
    '<!DOCTYPE html>\n<html><head><meta charset="utf-8">\n<style>\n' +
    'html,body{margin:0;padding:0;background:' + bg + ';}\n' +
    '#c{display:inline-block;background:' + bg + ';}\n' +
    (P.fontCss || '') + '\n' +
    '#c svg{display:block;}\n' +
    '</style></head><body>\n<div id="c"></div>\n' +
    '<script src="' + fileUrl(P.mermaidJs) + '"></script>\n' +
    '<script>\n' +
    'window.__err=null;window.__ready=false;\n' +
    '(async function(){\n' +
    '  try{\n' +
    '    var SRC = ' + JSON.stringify(mmd) + ';\n' +
    '    var CFG = ' + JSON.stringify(cfg) + ';\n' +
    '    window.mermaid.initialize(Object.assign({startOnLoad:false,securityLevel:"loose"}, CFG));\n' +
    '    var r = await window.mermaid.render("wmplocal", SRC);\n' +
    '    var host = document.getElementById("c");\n' +
    '    host.innerHTML = r.svg;\n' +
    '    var svg = host.querySelector("svg");\n' +
    '    if(svg){\n' +
    '      svg.setAttribute("style","display:block;width:' + width + 'px;height:auto;max-width:none;");\n' +
    '      svg.removeAttribute("height");\n' +
    '    }\n' +
    '    window.__svg = svg ? svg.outerHTML : "";\n' +
    '  }catch(e){ window.__err = String((e && e.message) || e); }\n' +
    '  window.__ready = true;\n' +
    '})();\n' +
    '</script></body></html>\n';

  const td = fs.mkdtempSync(path.join(os.tmpdir(), 'wmp-mmd-'));
  const htmlPath = path.join(td, 'diagram.html');
  fs.writeFileSync(htmlPath, html, 'utf8');

  const browser = await chromium.launch({
    headless: true,
    executablePath: chrome,
    args: ['--allow-file-access-from-files', '--font-render-hinting=none'],
  });
  try {
    const page = await browser.newPage({
      viewport: { width: Math.max(width, 100), height: 800 },
      deviceScaleFactor: scale,
    });
    const errors = [];
    page.on('pageerror', (e) => errors.push(String(e.message || e)));
    await page.goto(fileUrl(htmlPath), { waitUntil: 'load' });
    await page.waitForFunction(
      'window.__ready === true || window.mermaidReady === true',
      null, { timeout: 30000 });

    const err = await page.evaluate(() => window.__err);
    if (err) {
      console.error('[mermaid_local] mermaid 渲染失败：' + err);
      process.exit(5);
    }
    if (P.svgOut) {
      const svg = await page.evaluate(() => window.__svg || '');
      if (svg) fs.writeFileSync(P.svgOut, svg, 'utf8');
    }
    const el = await page.$('#c svg');
    if (!el) {
      console.error('[mermaid_local] 页面里没有 svg（图源码可能不合法）');
      process.exit(6);
    }
    const box = await el.boundingBox();
    // 只做体检（量原始尺寸）时 P.out 为空，跳过栅格化，省一半时间
    if (P.out) {
      await el.screenshot({ path: P.out, omitBackground: false });
      console.log('[mermaid_local] OK ' + P.out +
        (box ? ' (' + Math.round(box.width) + 'x' + Math.round(box.height) + '@' + scale + 'x)' : ''));
    } else {
      console.log('[mermaid_local] OK (svg only) ' +
        (box ? Math.round(box.width) + 'x' + Math.round(box.height) : ''));
    }
    if (errors.length) console.error('[mermaid_local] 页面告警：' + errors.slice(0, 2).join(' | '));
  } finally {
    await browser.close();
    try { fs.rmSync(td, { recursive: true, force: true }); } catch (e) { /* 忽略 */ }
  }
})().catch((e) => {
  console.error('[mermaid_local] 失败：' + String((e && e.stack) || e));
  process.exit(1);
});
