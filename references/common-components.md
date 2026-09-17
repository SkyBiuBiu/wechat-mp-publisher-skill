# 通用增量组件库 —— 代码块 · 图片/GIF · 小标签标题

> **跨所有主题通用**。主题专属组件（引言卡、章节标题、签名等）读各自主题库；本文件提供三类**所有主题都需要**的组件：代码块、图片/GIF、小标签标题。
>
> **配色占位**：下面用红白色系（主色 `#DC2626`、浅底 `#FEF2F2`、浅标 `#FEE2E2`、深字 `#991B1B`）做示例。换其它主题时，把这几个值替换为该主题"设计变量速查表"里的对应色；代码块深色版各主题可共用，浅色版用主题主色做左竖条。
>
> **平台限制**：同主题库——禁 `<style>/<script>/class/id/div/position/float/@media/grid`，只用内联 + `flex`，文字全部 `<span leaf="">` 包裹。

---

## 一、代码块组件（Markdown ``` 围栏 → 这里）

文章里的代码、命令、Prompt 提示词、配置等，**必须用代码块组件**，不要塞进普通段落或引用块。代码块内的英文、半角符号、缩进都要原样保留（代码不适用"中文全角标点"规则）。

### 1a. 深色代码块（默认，技术感强，适配所有主题）

```html
<section style="margin:0 0 20px;border-radius:8px;overflow:hidden;background:#1E293B;border-left:3px solid #059669;box-shadow:0 4px 16px -8px rgba(15,23,42,0.4);">
  <section style="display:flex;align-items:center;padding:9px 14px;background:#172B25;">
    <span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:#FF5F56;margin-right:7px;font-size:0;line-height:0;overflow:hidden;">.</span>
    <span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:#FFBD2E;margin-right:7px;font-size:0;line-height:0;overflow:hidden;">.</span>
    <span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:#27C93F;font-size:0;line-height:0;overflow:hidden;">.</span>
    <span style="margin-left:12px;font-size:12px;color:#64748B;font-family:Consolas,Monaco,monospace;letter-spacing:1px;"><span leaf="">python</span></span>
    <span style="margin-left:auto;font-size:11px;color:#9CA3AF;white-space:nowrap;"><span leaf="">👉 左右滑动</span></span>
  </section>
  <section style="padding:11px 14px;overflow-x:auto;-webkit-overflow-scrolling:touch;white-space:nowrap;">
    <p style="margin:0;font-family:'SF Mono',Consolas,Monaco,monospace;font-size:13px;line-height:1.6;color:#E2E8F0;white-space:nowrap;"><span leaf="">def make_skill(name):</span></p>
    <p style="margin:0;font-family:'SF Mono',Consolas,Monaco,monospace;font-size:13px;line-height:1.6;color:#E2E8F0;white-space:nowrap;"><span leaf="">&nbsp;&nbsp;&nbsp;&nbsp;return f"已生成 {name}"</span></p>
    <p style="margin:0;font-family:'SF Mono',Consolas,Monaco,monospace;font-size:13px;line-height:1.6;color:#E2E8F0;white-space:nowrap;"><span leaf="">print(make_skill("gzh-design"))</span></p>
  </section>
</section>
```

要点（**关键，避免大段空白与折行错位**）：

① 顶栏三色圆点 + 语言名（无语言可删该 span）；顶栏底色往主题色相偏一点（`#172B25` 是摸鱼绿的），
不用所有主题共用一个 `#0F172A`；
② **每行代码用一个 `<p style="margin:0;...">`，不要用 `white-space:pre`**——否则 HTML 源码里
span 前的缩进和行间换行会被原样渲染成大左缩进 + 空行；
③ **行首空格与连续空格一律写 `&nbsp;`**。这是唯一能同时保住缩进**和列对齐**的写法：
源码空格会被 HTML 折叠（4 空格缩进整层消失、对齐在某一列的行尾注释全挤到代码后面），
全角空格 `　` 能缩进但对不齐列（它比半角字符宽约 1.67 倍，不是整 2 倍）；
④ **长行横滑，不折行**：外层 `section` 给 `overflow-x:auto;-webkit-overflow-scrolling:touch;white-space:nowrap;`，
每行 `<p>` 再内联一次 `white-space:nowrap` —— 微信会往页面注入 `white-space:normal`，
内联样式优先级高于它的任何选择器，这一层是防它把横滑改回折行；
⑤ 预计超宽时顶栏右侧给「👉 左右滑动」提示（与主题库横滑卡组的说法一致）——
手机上横向滚动条是隐藏的，不提示读者根本不知道能滑；
⑥ `border-left:3px solid` 换当前主题主色，让"这块是哪个主题的代码"一眼可辨；
⑦ 行距只靠 `line-height:1.6` 控制，padding 用 `11px 14px`，保持紧凑。

> 手写这几条很容易漏（尤其 ③ 的 `&nbsp;`），所以正篇文章的代码块都应该由
> `scripts/highlight_code.py` 生成，见下面 1a+ 节。

### 1b. 浅色代码块（适配浅色温和主题，如玫瑰粉/天蓝/焦糖棕）

```html
<section style="margin:0 0 20px;border-radius:8px;overflow:hidden;background:#F6F8FA;border:1px solid #E5E7EB;border-left:3px solid #DC2626;">
  <section style="padding:7px 14px;border-bottom:1px solid #E5E7EB;">
    <span style="font-size:12px;color:#9CA3AF;font-family:Consolas,Monaco,monospace;letter-spacing:1px;"><span leaf="">bash</span></span>
  </section>
  <section style="padding:11px 14px;overflow-x:auto;-webkit-overflow-scrolling:touch;white-space:nowrap;">
    <p style="margin:0;font-family:'SF Mono',Consolas,Monaco,monospace;font-size:13px;line-height:1.6;color:#24292F;white-space:nowrap;"><span leaf="">npx skills add gzh-design</span></p>
  </section>
</section>
```

（左竖条 `#DC2626` 换成当前主题主色；多行同 1a：每行一个 `<p style="margin:0">`，不用 `white-space:pre`，
缩进与对齐用 `&nbsp;`，行内也内联 `white-space:nowrap`。超宽提示要把顶栏排成
`display:flex;align-items:center` 才能把提示推到右侧。）

### 1a+/1b+. 按语言着色（在 1a / 1b 的结构上叠一层 token 颜色）

1a / 1b 的上面两个示例是**单色**的 —— 每行都是同一个字色。代码超过十行就会糊成一片灰，
读不出结构。给 token 上色只需在原结构上把文本再包一层：**着色包外层、`<span leaf="">` 仍在内层**：

```html
<p style="margin:0;font-family:'SF Mono',Consolas,Monaco,monospace;font-size:13px;line-height:1.6;color:#E2E8F0;white-space:nowrap;">
  <span style="color:#94E6CC;font-weight:bold;"><span leaf="">for</span></span><span leaf=""> step </span><span style="color:#94E6CC;font-weight:bold;"><span leaf="">in</span></span><span leaf=""> </span><span style="color:#DFA4B8;"><span leaf="">range</span></span><span leaf="">(max_steps):</span>
</p>
```

（`#94E6CC` 是摸鱼绿的关键词色、`#DFA4B8` 是内置函数色，**这两个值别抄** —— 下面这段是你的。）

**不要手写这些色值**，跑脚本，配色由主题推导：

```bash
python scripts/highlight_code.py article.md --theme moyu-green -o code.html
python scripts/highlight_code.py --show-palette --all-themes   # 看各主题的配色
python scripts/highlight_code.py article.md --check-widths     # 哪几行会横滑
```

为什么必须由脚本推导：手写必然出现"这套主题用了这个绿、下套主题忘了改"的漂移，而且
每篇文章都要重新编一遍色值。脚本从主题库的「设计变量速查表」里取色相，6 套内置主题与
任何自定义主题（见 `theme-generator.md`）都自动适配。

**色彩丰富但不突兀**，靠的是把两件事分开（改配色时守住）：

1. **丰富来自色相**：以主题主色的色相为起点铺一圈色环 —— 关键词留在主色相本身
   （`+0°`，保住主题身份），函数 / 数字 / 字符串 / 内置 / 类型依次取
   `+35° / +70° / +140° / +195° / +262°`。早期版本把全部 token 压在主色相 ±24° 内，
   结果整块糊成一个色 —— 这是这一版改掉的核心问题；
2. **秩序来自明度与饱和度**：深色底上六个色相同处一个明度带 `L≈0.68~0.78`、
   一个饱和度带 `S≈0.45~0.62`，所以色相虽多、亮度是一个。判据不是"好不好看"，
   而是"抽掉色相看灰度，整块是不是平的"；
3. **关键词与类型加粗**，结构在彩色里立得住；**运算符与标点仍然不着色** ——
   给标点上色是"满屏彩点"的主要来源。

配色方案另有 `--scheme calm`：回到早期的单色克制版（只有关键词/函数/字符串/数字着色、
全篇一个对比色），适合留白禅意这类本来就要素的主题。

支持 python / bash / json / javascript / yaml / sql / dockerfile 及 C 系语言（go/rust/java…），
其余标识按 C 系处理，`text`/`prompt`/`md` 等不着色。浅色主题用 `--style light` 出 1b 版。

> 主色是墨黑或灰的主题（橄榄手记 `#1e1f23`、石墨极简 `#52525B`）色相不可信，脚本会自动
> 改取主题登记的点睛强调色（`#ed7b2f` / `#F97316`）的色相。判据是通道差而非 HSL 饱和度：
> `#1e1f23` 的 HSL 饱和度有 0.077 看着"有一点彩"，实际通道差只有 5/255，纯属舍入噪声。

> 想换回折行（不横滑）：`--wrap`。**只在读者确实不需要列对齐时用** —— 行尾对齐的注释被
> 折到下一行后，读者会分不清它属于哪一句。

改配色后回归看 `python tools/make_code_preview.py`（同一段代码 × 六套主题，页面按手机
正文宽度 328px 排版，横滑与否在这里就能看出来）。

### 1c. 行内代码（正文中的 `code` 短片段）

```html
<span style="background:#F1F5F9;color:#DC2626;padding:1px 6px;border-radius:4px;font-family:'SF Mono',Consolas,Monaco,monospace;font-size:14px;"><span leaf="">SKILL.md</span></span>
```

（文字色 `#DC2626` 换主题主色；底色保持中性浅灰。）

---

## 二、图片 / GIF 组件（Markdown `![](...)` → 这里）

文章里**每一处图片、GIF、截图占位都要保留并转成下面的组件**，不得遗漏；`src` 原样保留用户给的 URL 或相对路径。GIF 动图与普通图片都用 `<img>`（公众号原生支持 GIF 自动播放），区别只在加不加"动图"角标说明。

### 2a. 标准图片（带说明）

```html
<section style="background:#FFF;border-radius:12px;padding:6px;border:1px solid #E5E7EB;box-shadow:0 4px 12px -2px rgba(0,0,0,0.08);margin-bottom:8px;">
  <section style="margin:0;border-radius:8px;overflow:hidden;">
    <span leaf=""><img src="图片URL" style="max-width:100%;height:auto;display:block;margin:0 auto;"></span>
  </section>
</section>
<p style="font-size:12px;color:#9CA3AF;text-align:center;margin:0 0 24px;">
  <span leaf="">— 图片说明文字</span>
</p>
```

无说明文字时删掉下方 `<p>`，并把图片容器 `margin-bottom` 改回 `10px`。

> **图片尺寸自适应**：`<img>` 用 `max-width:100%;height:auto;display:block;margin:0 auto`——按图片自身尺寸显示并居中，大图缩到容器宽、小图保持原尺寸，**不用 `width:100%` 强制铺满**（小图被拉伸会糊）。

### 2b. GIF 动图（同图片，加"GIF 动图"角标）

```html
<section style="background:#FFF;border-radius:12px;padding:6px;border:1px solid #E5E7EB;box-shadow:0 4px 12px -2px rgba(0,0,0,0.08);margin-bottom:8px;">
  <section style="margin:0;border-radius:8px;overflow:hidden;">
    <span leaf=""><img src="动图URL.gif" style="max-width:100%;height:auto;display:block;margin:0 auto;"></span>
  </section>
</section>
<p style="text-align:center;margin:0 0 24px;">
  <span style="display:inline-block;background:#FEE2E2;color:#991B1B;font-size:11px;font-weight:700;padding:1px 8px;border-radius:4px;margin-right:6px;"><span leaf="">GIF 动图</span></span>
  <span style="font-size:12px;color:#9CA3AF;"><span leaf="">动图说明文字</span></span>
</p>
```

（角标底色 `#FEE2E2` → 主题浅底色，字色 `#991B1B` → 主题深字色，取自该主题"设计变量速查表"；无色块的极简主题改用细线描边胶囊：边框与字色用主题主色、背景透明。）若原文只写了图片但没给 URL，用 `src="图片URL"` 占位并在交付时提醒用户补图，**不要凭空编造图床链接**。

---

### 2c. 待补素材占位（**居中板块**，用于 GIF / 录屏 / 视频 / 成果图待补处）

文章里 `【插入xxx】`、待录屏、待补 GIF/视频/截图等占位，一律用这个**居中**板块，不要用左对齐的提示块。所有排版风格通用，浅底柔虚线框 + 居中图标与说明，一眼看出"此处待补"。

```html
<section style="margin:0 0 24px;padding:30px 20px;border:1.5px dashed #DAD7D2;border-radius:14px;background:#FAFAF8;text-align:center;">
  <p style="margin:0 0 10px;font-size:26px;line-height:1;"><span leaf="">🎬</span></p>
  <p style="margin:0;font-size:14px;font-weight:700;color:#9CA3AF;letter-spacing:1px;"><span leaf="">待补素材</span></p>
  <p style="margin:8px 0 0;font-size:13px;color:#B8B5B0;line-height:1.7;"><span leaf="">此处插入：创建 skill 的录屏演示</span></p>
</section>
```

- 图标按素材类型换：🎬 视频/录屏、🖼 图片、📊 信息图、📎 附件。
- 这是**唯一允许用虚线框（dashed）的场景**——因为它表达"占位/待补"语义，与正文强调用的小标签不冲突。
- 各主题可把虚线色/底色微调成主题中性色，但保持居中、留白、柔和。

---

## 三、小标签标题组件（突出标题/强调，**替代虚线框**）

> **设计取向**：强调一段内容或起一个小标题时，优先用下面的"小标签 / 左竖条"形式，**不要用四周虚线框（dashed）包一个标题**——虚线框笨重、抢戏。小标签更轻、更现代。
>
> **使用优先级**：先查所选主题库的映射规则——主题库有等价语义组件（自己的金句块/提示块/小标题）就用主题库版本保持气质一致；没有时才用本节组件并按下面规则换色。
>
> **换色规则**（示例为红白色值，按所选主题"设计变量速查表"替换）：
> - 3a 左竖条 `#DC2626` → 主题主色；3b 药丸底 `#DC2626` → 主题主色（字保持白）
> - 3c 序号药丸底 `#FEE2E2` → 主题浅底色，序号字 `#991B1B` → 主题深字色
> - 3d/3e 块底 `#FEF2F2` → 主题浅底色，竖条/类型标签 `#DC2626` → 主题主色
> - **无色块的极简主题**（留白禅意/石墨极简等）：3a 竖条细化为 `2–3px`，3d/3e 去掉底色、只留左竖条 + 大留白，贴合该主题气质。

### 3a. 左竖条小标题（最推荐，干净）

```html
<p style="margin:28px 0 14px;font-size:16px;font-weight:800;color:#1C1917;line-height:1.5;border-left:4px solid #DC2626;padding-left:12px;">
  <span leaf="">小标题文字</span>
</p>
```

### 3b. 药丸标签小标题（实色底，最醒目）

```html
<p style="margin:28px 0 14px;">
  <span style="display:inline-block;background:#DC2626;color:#FFFFFF;font-size:14px;font-weight:700;padding:5px 16px;border-radius:6px;"><span leaf="">小标题文字</span></span>
</p>
```

### 3c. 序号药丸 + 标题（清单/步骤）

```html
<p style="margin:24px 0 12px;font-size:15px;font-weight:800;color:#1C1917;line-height:1.6;">
  <span style="display:inline-block;background:#FEE2E2;color:#991B1B;border-radius:5px;padding:1px 9px;margin-right:8px;font-weight:900;"><span leaf="">01</span></span>
  <span leaf="">要点标题</span>
</p>
```

### 3d. 金句引用（左竖条版，取代旧的虚线框金句）

```html
<section style="margin:0 0 24px;background:#FEF2F2;border-radius:0 10px 10px 0;border-left:4px solid #DC2626;padding:16px 20px;">
  <p style="font-size:16px;font-weight:800;color:#991B1B;margin:0;line-height:1.8;">
    <span leaf="">「这里是核心观点或关键金句」</span>
  </p>
</section>
```

### 3e. 提示 / 旁注块（左竖条 + 类型小标签，取代旧的虚线提示框）

```html
<section style="margin:0 0 24px;background:#FEF2F2;border-radius:0 8px 8px 0;border-left:4px solid #DC2626;padding:14px 18px;">
  <p style="margin:0 0 6px;">
    <span style="display:inline-block;background:#DC2626;color:#FFFFFF;font-size:11px;font-weight:700;padding:2px 10px;border-radius:4px;letter-spacing:1px;"><span leaf="">提示</span></span>
  </p>
  <p style="font-size:14px;color:#374151;margin:0;line-height:1.8;">
    <span leaf="">提示或旁注的正文内容</span>
  </p>
</section>
```

类型小标签文字可换：`提示` / `注意` / `重点` / `Prompt` / `旁注` 等。整块**没有任何 dashed 边框**，靠左竖条 + 浅底 + 小标签区分层次。

---

## 选用速记

| 文章里出现 | 用哪个组件 |
|---|---|
| ` ``` 代码 / 命令 / Prompt 围栏 ``` ` | 1a 深色（默认）或 1b 浅色代码块 |
| 行内 `` `code` `` | 1c 行内代码 |
| `![](图片)` | 2a 标准图片 |
| `![](xxx.gif)` 或注明动图 | 2b GIF 动图 |
| 想给一段起小标题 / 强调 | 3a 左竖条（首选）/ 3b 药丸 / 3c 序号 |
| `> 金句` | 3d 金句左竖条块 |
| 提示 / 注意 / 旁注 | 3e 提示左竖条块（**不要用虚线框**） |
