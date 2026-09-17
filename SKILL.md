---
name: wechat-mp-publisher-skill
description: 微信公众号图文排版与发布技能。当用户要求「发公众号」「发一篇公众号文章/推文」「公众号排版」「推到公众号草稿箱」「把这篇发到微信公众号」时使用。排版侧采用 gzh-design 组件库范式：6 套精选主题（摸鱼绿/红白雪/石墨极简/留白禅意/摸鱼票据/橄榄手记）+ 跨主题通用组件库（代码块/图片/GIF/小标签），支持 Markdown / Word(.docx) / PDF / 纯文本输入，按文章类型配方装配纯 <section> 内联样式 HTML（文字全部 <span leaf> 包裹），双关卡校验（component_lint 查组件库源头 + validate_gzh_html 查产物）后生成带「复制」按钮的预览页；发布侧通过微信官方 API 完成 access_token 获取、mermaid 预渲染成 PNG、正文图片上传换链、封面永久素材上传、图文草稿创建，可选正式发布。内置错误码中文翻译、IP 白名单诊断与白名单生效轮询。
agent_created: true
---

# 微信公众号图文排版与发布

把一篇文章排成可直接粘贴进公众号编辑器的 HTML，再（可选）用微信官方 API 推进草稿箱。

**两条链路，职责分明，别混用：**

| 链路 | 归谁管 | 产物 |
|---|---|---|
| **排版**（主题选型、组件装配、合规校验） | `references/` 组件库 + 双关卡脚本 | 纯 `<section>` 正文 HTML + 预览页 |
| **发布**（上传图片、建草稿、正式发布） | `scripts/publish.py` + `preflight.py` | 公众号草稿箱里的图文 |

排版规则**全部沉淀在组件库里**，不要凭记忆手写 HTML——组件库里有什么就用什么。发布规则**全部沉淀在接口体检里**，不要靠"记得住"。

---

## 一、能力边界（先判断可行性，再动手）

微信接口权限由**账号类型 + 认证状态**决定，这是硬约束：

| 能力 | 可用范围 |
|---|---|
| 拿凭证 / 上传正文图片 / 上传封面素材 / 建草稿 | ✅ 绝大多数账号，**已实测个人未认证订阅号可用** |
| API 正式发布（freepublish） | ❌ 仅认证账号。**个人主体无法微信认证 → 永久不可用** |

**行动规则**：

- 个人主体账号 → 只做到建草稿，最后一步引导用户到 mp 后台「内容与互动 → 草稿箱」手动点「发表」。**不要反复重试发布**，`48001` 是账号类型限制，重试无意义。
- 企业/组织主体已认证账号 → 全链路可用，可执行发布。
- 无法判断账号类型时，先跑 `check`，再跑 `draft`，用实际报错决定。

详细权限矩阵、实测记录与接口字段约束见 `references/wechat-api-reference.md`。

## 二、前置条件

1. **AppID / AppSecret**：在**微信开发者平台** `developers.weixin.qq.com/platform` 获取，不在 mp 后台。
   扫码登录 → 我的业务与服务 → 我的业务 → 公众号 → 基础信息 → 开发密钥。
   AppSecret 默认隐藏，点「启用」后**只显示一次**。
2. **IP 白名单**：必须包含调用方的**公网 IPv4 出口 IP**。
   - 取 IPv4：`curl -4 ipv4.icanhazip.com`（`curl ifconfig.me` 可能返回 IPv6，微信不认）。
   - 配置入口：微信开发者平台 → 公众号详情页 → API IP白名单。
   - 改完通常要**管理员扫码确认**，且**有生效延迟**。
   - 报 40164 时直接读 `errmsg` 里的 IP，脚本会自动提取提示。
3. **封面图**：必填。`scripts/make_assets.py` 可生成 900×383 的（需 pillow）。
4. **正文**：Markdown / docx / pdf / 纯文本 → 排出 HTML。

> 只想排版、不推草稿？**第 3、4 项不需要**，直接走第三节开始的排版链路，产物是 HTML + 预览页。

---

## 三、排版工作流

### Step 0：输入与格式归一化

用户可能给：Markdown 文本或 `.md` 路径（直接进 Step 1）、`.docx`、`.pdf`、`.txt`/无标记纯文本、网页富文本。

**非 Markdown 输入必须先读 `references/format-normalize.md`** 按其规则转成 Markdown 并做结构确认：docx 走 `scripts/extract_docx.py`，PDF 用分页读取+清噪，纯文本按标题启发式推断结构。

用户说「直接排 / 自动排 / 一键 / 不用问」→ 进**全自动模式**：跳过结构确认与选主题提问，自动推断结构、按题材自选主题，交付时附决策说明。

### Step 1：选主题

读 `references/theme-index.md`（主题信息的**单一来源**），据题材主动推荐最契合的一套，再让用户一步确认：

| 主题 | 主色 | 适合 |
|---|---|---|
| 摸鱼绿（默认） | `#059669` | 教程、测评、清单、工具盘点（卡片丰富、信息密度高） |
| 红白色系 | `#DC2626` | 深度分析、观点、力量感话题（经典编辑风） |
| 石墨极简风 | `#52525B` | 设计、科技评论、专业观点、高端品牌 |
| 留白禅意风 | `#4A5D52` | 禅意、极简生活、深度随笔（呼吸感最强） |
| 摸鱼票据风 | `#059669` | 工具对比、创意评测（票据视觉隐喻） |
| 橄榄手记 | `#1e1f23` | 内刊手记、深度评测、案例复盘（信息密度偏高） |

- **用户已指定** → 直接用，不问。
- **题材有明确契合** → 单问确认：「建议用 XX（理由），确认还是换一套？」选项给推荐项 + 1~2 个备选。
- **无明显倾向** → 默认推荐摸鱼绿放第一位，用 AskUserQuestion 让用户选。
- **全自动模式** → 不提问，选题材最契合的，交付时说明理由。
- **都不满意** → 走 `references/theme-generator.md` 生成新主题，登记后回到本步。
- **同一篇只用一套主题，不跨主题混用组件。**

### Step 2：读组件库（两份）

1. 据 theme-index 的「组件库文件」列，Read 该主题专属库 `references/theme-{标识}.md`（引言卡、章节标题、正文标记、签名等）。
2. **同时 Read** 通用增量库 `references/common-components.md`（代码块、图片/GIF、小标签标题——所有主题共用，套当前主题色）。

**后续生成完全依据这两份组件库，HTML 一律从中取、不要手写。**

### Step 3：解析结构 + 判定文章类型

| 元素 | 识别规则 |
|---|---|
| 文章标题 | `# 标题` 或 frontmatter `title` |
| 开头引言 | 文章最开头的 `> 引用` 块 |
| 章节 / 子章节 | `##` / `###` |
| 加粗 / 高亮 / 下划线 | `**文字**` / `==文字==` / `<u>文字</u>` 或 `++文字++` |
| 图片 / GIF | `![说明](URL)`、`![](xxx.gif)` |
| 代码 / 命令 / Prompt | ` ``` 围栏 ``` `、行内 `` `code` `` → **按语言着色须跑 `highlight_code.py`**，见 Step 4 |
| 表格 / 列表 / 分割线 | `\|` 表格、`- ` / `1. `、`---` |
| mermaid | ` ```mermaid ` → **必须先跑 `render_mermaid.py` 转 PNG**，见 Step 4 |

**然后判定文章类型**（取主导类型，可复合）：教程/操作指南、盘点/工具清单、观点/深度分析、访谈/人物特稿、数据复盘/报告、生活/情感随笔、案例实战。判定依据：步骤和命令多→教程；并列条目多→盘点；引语和人物叙事多→访谈；数字和对比多→数据；论证推演多→观点。

### Step 4：按配方装配 HTML

**先查所选主题库的「文章类型 → 组件组合配方」表**，按文章类型定核心组件组合与点缀组件——不要拿到组件库就逐段随机选，配方保证同类文章的排版气质稳定。

然后依主题库的**「完整文章模板骨架」**装配：

- **骨架顺序以主题库为准**，不同主题骨架不同，不要套用其它主题的骨架。
- **行内标记按语义找组件**（组件编号各库不统一，以语义为准）：`**加粗**`→主色加粗；`==高亮==`→渐变背景高亮；`++文字++`→下划线；`>引用`→引用高亮块。
- 来自通用库的：` ``` 代码块 ``` `→1a 深色/1b 浅色；行内 `` `code` ``→1c；图片→2a、GIF→2b、待补素材→2c；小标题/强调→3a–3e。
- **优先级：先查主题库映射规则表**——该主题有等价语义组件就用主题库版本；没有才用通用库 3x 并按换色规则换成主题色。
- **强调与小标题用「小标签/左竖条」，不要用四周虚线框**（`dashed` border）。唯一例外：主题库明确定义的虚线组件（如摸鱼绿的 quote-box）和通用库 2c 待补素材占位。

**mermaid 图先渲染再装配**（在 Step 5 校验之前）：

```bash
python <skill>/scripts/render_mermaid.py article.md --theme moyu-green
#   → 产出 article.mermaid.md（围栏已换成 ![](assets/mermaid-N.png)）
#   → 产出 assets/mermaid-1.png、mermaid-2.png …
#   通道自动选：本地 Chrome（默认，字体可控且内容不出本机）→ 本地 mmdc → mermaid.ink
#   图内字体默认霞鹜文楷（fonts.DEFAULT_MERMAID_PRESET）；换别的：--font-preset serif
#   想要系统字：--font-preset system（非 system 时必须走本地通道）
python <skill>/scripts/render_mermaid.py --list-themes      # 查主题标识
python <skill>/scripts/render_mermaid.py --list-fonts       # 看字体预设解析到哪些文件
```

**"图看不清"的根因是原始版式宽度，不是位图像素不够。** mermaid.ink 会按请求宽度缩放，
请求宽度在"位图→正文"这步又被抵消，最终正文里的字号只剩：

```
正文里实际字号 = 图内字号 × 正文宽度 ÷ 图形原始宽度
```

所以横排长链（`flowchart LR` 七节点）原始宽 1389px，正文里只剩 3.8px —— 手机上是一团灰。
**真正的杠杆是换方向或拆图**，不是调大 `--width`。脚本已把这件事自动化：

- 渲染前先量图形原始宽度，正文里字号低于 11px 且换方向能好 1.25 倍以上时，
  **自动把 `flowchart LR` 改成正交方向**，并在输出里写明 `3.8px → 12.4px`；
- 窄图（原始宽度本来就小）反过来**收窄显示宽度**，让字号落在正文惯用的 17px 上下，
  免得满宽拉出一屏 40px 巨字 + 两张屏高；
- 出图**强制不透明底**（`bgColor=FFFFFF`）。mermaid.ink 默认返回半透明 PNG，
  而微信点开大图是**黑底查看器**，深色文字压在黑底上等于没画。

**图内字体**：**默认霞鹜文楷**（`fonts.DEFAULT_MERMAID_PRESET`，图内都是小字号说明
文字，楷体比雅黑好认）。想换：装好字体文件后加
`--font-preset system|serif|sans|rounded`（或在 `config.json` 的 `mermaid.font_preset` 里定一次）。
**换字必须走本地通道** —— mermaid.ink 的服务器上没有你的字体，写什么 `font-family` 都白搭。
本地通道 = node + playwright-core + 本机 Chrome（缺哪样都会在输出里说明原因并自动退回在线通道）。
默认预设**自带降级**：本机没字体文件或没本地通道时，图内安静退回系统字体并打印 `[i]`
说明（人显式指定的预设则不降级，会明确告诉你为什么不生效）。

**"正文宽度"取手机值 328px，不是桌面网页的 677px。** 328 = 360dp 机型 360 − 两侧留白
16×2（见 `theme_vars.MOBILE_CONTENT_W`，插图与代码块共用这一个数）。早期版本按 677 算，
把图像在正文里的字号高估近一倍 —— "显示宽 677、正文里 17px"的结论，在手机上其实是
328、8.6px；同一处错误也让代码块误判"75 列也放得下"，实际手机上要折行。

要改行为：`--font-size` 图内字号、`--target-size` 期望正文字号、`--keep-direction`
不自动换方向、`--no-size-check` 跳过体检（省一次请求）。

**代码块按语言着色再装配**：

```bash
python <skill>/scripts/highlight_code.py article.md --theme moyu-green -o code.html
#   --lang python 只取该语言；--style light 出通用库 1b 浅色版
#   --scheme calm 回到单色克制版；--wrap 改回折行（不横滑）
#   --check-widths 只看"哪几行会横滑"，不出 HTML
#   --show-palette --all-themes 打印全部主题的高亮配色
```

配色**从主题库的设计变量速查表推导**，所以 6 套内置主题和任何自定义主题都自动适配，
不用为每套主题维护一份高亮配色表。除配色外还有两件事必须由脚本做，手写必错：

- **色彩丰富**：以主色色相为起点铺一圈色环 —— 关键词留在主色相本身（`+0°`，保住主题
  身份），函数 / 数字 / 字符串 / 内置 / 类型依次 `+35° / +70° / +140° / +195° / +262°`。
  六个色相同处一个明度带（深色底 `L≈0.68~0.78`）与一个饱和度带（`S≈0.45~0.62`）——
  **丰富来自色相、秩序来自明度与饱和度**，抽掉色相只看灰度，整块是平的。关键词与类型
  加粗；**运算符与标点不着色**（给标点上色是"满屏彩点"的主要来源）；
- **缩进与对齐**：行首空格与连续空格一律写 `&nbsp;`。源码空格会被 HTML 折叠 ——
  4 空格缩进整层消失、对齐在某一列的行尾注释全挤到代码后面。全角空格 `　` 能缩进但
  **对不齐列**（宽约 1.67 个半角字符，不是整 2 倍）；
- **长行横滑，不折行**：外层 `section` 给 `overflow-x:auto`，每行 `<p>` 再内联
  `white-space:nowrap`（微信会注入 `white-space:normal`，内联样式优先级高于它的任何
  选择器）。折行会把行尾注释甩到下一行开头，读者分不清它属于哪句；预计超宽时顶栏右侧
  出「👉 左右滑动」提示 —— 手机上横向滚动条是隐藏的，不提示没人知道能滑。

主色若是墨黑或灰（橄榄手记 `#1e1f23`、石墨极简 `#52525B`），色相是舍入噪声，
脚本自动改取主题登记的点睛强调色的色相（`#ed7b2f` / `#F97316`）——见
`scripts/theme_vars.py` 的 `chroma()`。

装配时把 `mermaid-N.png` 当普通图片，用主题库/通用库的图片组件引用（不要留 ```mermaid 源码，会当正文发出去）。

### Step 5：双关卡校验（强制）

```bash
# 产物关：查禁用标签、<span leaf> 包裹、半角标点
python <skill>/scripts/validate_gzh_html.py <装配好的.html>

# 源头关：只有改过组件库时才需要跑
python <skill>/scripts/component_lint.py <skill 目录>
```

**ERROR 清零才算完成**；半角标点 WARNING 也要修到 0（实际使用中最高频的返工点）。报错就回 Step 4 改。

### Step 6：输出

**产物是纯 `<section>…</section>` 正文片段**，从全局容器开始，**不要包 `<!DOCTYPE>`/`<html>`/`<head>`/`<body>`**——公众号编辑器只接受正文片段。

1. **干净正文文件**：存到工作目录，命名 `{原文件名}_排版_{主题中文名}({英文标识}).html`。
2. **带「复制」按钮的预览页**：
   ```bash
   python <skill>/scripts/wrap_preview.py <干净正文.html>
   ```
   产出 `{...}_预览.html`，浏览器打开后右上角「复制到公众号」，点一下即把渲染后的富文本复制到剪贴板，再到公众号编辑器 Ctrl/⌘+V。按钮和脚本只在预览外壳里，**不在被复制的 section 内**。
3. 告知用户：**打开 `{...}_预览.html` → 点右上角「复制」→ 编辑器粘贴**；并给出干净正文路径作为兜底，附校验结论。

### 生成时的智能处理（本 skill 的特色，必须做）

1. **章节自动编号**：按 `##` 顺序分配 `01/02/03…`；末章若为结语类，用主题库指定的结语编号变体（如 `∞`），未指定时沿用数字。
2. **英文标签**：据中文章节标题生成（实测→TEST、教程→TUTORIAL、总结→SUMMARY…），主题库有槽位时使用。
3. **正文关键词下划线（核心特色）**：**每个正文段落**主动找出 1–3 个最重要的短语，用 theme-index 的「正文下划线 CSS」标记。优先核心观点、结论、关键数据、专有名词；短语 4–15 字；整段无要点可不标。**即使原文没有任何加粗也要主动加**——它是出现频率最高的基础标记。
4. **引言关键词高亮**：识别开头金句里的核心词，用高亮组件标记。
5. **目录提取**：从所有 `##` 取前 3 个作为导读要点（主题库有目录组件时）。
6. **开头引言卡署名**：有署名就写「—— 作者名」，没有就用与主题相关的简短落款或省略。**不要固定写别人的人名。**
7. **尾部作者签名区（仅末尾一处）**：默认不写死人名，用 `{{作者名}}` 占位；原文末尾已有签名段就沿用原文署名。互动引导句可保留通用文案。
8. **列表转换**：按主题库映射规则处理；无专属组件时转为带缩进的正文段落。
9. **中文全角标点**：正文标点一律全角（，。！？：；""''（）——…）。**生成时直接写弯引号，不要先写直引号再事后替换。例外**：代码块、行内代码、英文专名/URL/标识符内部保持原样。

### 视觉层级（3 层递进，所有主题通用）

| 层级 | 作用 | 频率 | 手段 |
|---|---|---|---|
| 锚点层 | 最强锚点：产品名/步骤/CTA/核心金句 | 全文 ≤ 5 处 | 主色加粗、深色底白字引用 |
| 标记层 | 正文关键词 | 每段 1–3 处 | 下划线标记 |
| 容器层 | 引用块、概念标签、长句强调 | 按需 | 浅底引用、荧光笔、徽章 |

### 平台红线（核心，完整检查交给校验脚本）

- **禁止**：`<style>`/`<script>`/`<div>`、`class`/`id` 属性、`position:fixed/absolute/sticky`、`float`、`@media`/`@keyframes`、`display:grid`、CSS 变量、外部字体/CSS。
- **必须**：样式全部内联 `style`；所有文字节点用 `<span leaf="">文字</span>` 包裹（否则粘贴后样式丢失）。
- **可用**：`display:flex`（有限）、`linear-gradient`、`border-radius`、`box-shadow`、`<section>/<p>/<span>/<strong>/<img>/<h3>`。

### Gotchas（真实排版踩过的坑）

- **漏 `<span leaf>` 包裹**是最常见的致命错——粘贴后样式整片丢失。靠 Step 5 兜底，别跳过。
- **下划线逐段落实**：不要整段划线，也不要有的段标有的段漏；列表项里的关键描述同样要标。
- **章节编号错乱**：严格按 `##` 顺序，不跳号；结语编号变体只用于末章。
- **签名区有且仅有末尾一个**：原文末尾已有签名/「点赞在看转发」段落时**并入**这唯一的签名区，不要保留原文段又再生成一个。
- **图片说明硬造**：只有 `![说明](url)` 里真有说明才生成说明组件，空 alt 不要编造。
- **图片自适应、不铺满**：`<img>` 一律 `max-width:100%;height:auto;display:block;margin:0 auto`，**不用 `width:100%`**（小图会被拉伸变糊）；只有表格/封面卡/流程图才用 `width:100%`。
- **目录是精选不是全量**：展示精选的 3 个核心看点，章节多于 3 个时挑最重要的 3 个。
- **代码块要紧凑、忌大空白**：每行一个 `<p style="margin:0">`，**绝不用 `white-space:pre`**；缩进只用全角空格 `　`，行距靠 `line-height:1.6`。
- **代码/Prompt 必须用代码块组件**，不要塞进普通段落或引用块。
- **待补素材居中**：`【插入…】`、待录屏/GIF/视频/成果图用通用库 2c 居中占位板块。
- **原文内容遗漏**：每个段落、每张图都要转换，不得漏；不自行增删原文实质内容。
- **占位图残留**：组件里带名片图占位而没真实 URL 时，整行删掉。

### 自定义主题（想要内置 6 套之外的风格）

读 `references/theme-generator.md` 并严格按其流程：收集偏好（一次问全）→ 生成区块库 HTML 存 `assets/theme-previews/{id}.html` 供整页确认 → 转标准 `references/theme-{id}.md`（补 `<span leaf>`、补齐五章节）→ 登记 `theme-index.md` → `component_lint.py` 到 0 ERROR。之后与内置主题完全同权。

---

## 四、发布工作流

### Step 1：准备工作目录

```bash
mkdir -p wechat-publish/assets
cp <skill>/assets/templates/config.example.json wechat-publish/config.json
# 编辑 config.json：appid / appsecret / theme / article.title / cover_file / content_file
```

`theme` 填 Step 1 选定的主题标识（纯记录 + 给 mermaid 取色用）。

### Step 2：装配正文 → 双关卡校验

见第三节 Step 4–5。产物落在 `wechat-publish/article.html`（或在 skill 外用你自己的工作目录）。

### Step 3：封面

```bash
# 配色与皮肤跟着 config 的 theme 走，文案读 config 的 cover 段；-o 是输出目录
python <skill>/scripts/make_assets.py -c wechat-publish/config.json -o wechat-publish/assets \
    --title "文章标题" --subtitle "副标题" --date "2026.09"
```

需 `pillow`。默认出两张：`cover.png`（900×383，微信推荐比例）和 `diagram.png`（正文插图占位）。
**配色从主题库 `references/theme-<id>.md` 的「设计变量速查表」解析**（主色调/标题色/正文色/辅助文字/
极浅底/**点睛色**），封面与正文成套。`--theme <id>` 手动指定，`--dark` 回到旧的深色橙调版式。
`--only cover` 只要封面。

**文案优先放 `config.json` 的 `cover` 段**（brand/title/subtitle/date/motif…），命令行参数只做覆盖：
优先级 **命令行 > `cover` 段 > `article.title` > 内置默认**，运行时会打印来源。别每次都拼一长串参数。

**版式与皮肤**：几何规格在 `scripts/cover_spec.py` 的 `SPEC`（唯一来源，比例 900:383 是微信列表页
裁切的硬约束）；主题气质由 `THEME_SKINS` 的皮肤决定——底色、竖条宽度与颜色、外框描边（票据的
2px 黑硬边）、圆角、底纹（票据撕票虚线 / 禅意极细线）、字型（禅意衬线）。**同色主题靠皮肤区分，
不要去改主题库色值**：摸鱼绿与摸鱼票据风主色同为 `#059669`、石墨极简与留白禅意都偏无彩，
改色值会牵连正文排版。

**字体**：封面默认跟随系统（微软雅黑），流程图默认霞鹜文楷（见 `fonts.DEFAULT_MERMAID_PRESET`）。
换字体加 `--font-preset`，或在 `config.json` 里定一次（封面读 `font.preset`，图读
`mermaid.font_preset`）：`wenkai`（霞鹜文楷，楷体）/ `serif`（思源宋体标题 + 思源黑体正文）/
`sans`（思源黑体）/ `rounded`（MiSans，圆润科技风）。**两边共用 `scripts/fonts.py` 这一份
预设清单**（同一个名字在两边含义一致，不会出现"封面认这个文件、图认那个族名"），
但默认值刻意不同：封面是大标题、字形即视觉，保持系统字最稳；图内是小字号说明文字，
楷体更好认。**想让整套统一，就在 config 里两处都写上同一个值**——只写一处会得到
"封面换了字、图没换"的半吊子状态。字体文件不进分发包：放到
`~/.workbuddy/fonts/`（或 `<skill>/assets/fonts/`、`WMP_FONT_DIR`），缺了自动退回系统字体
并在 stderr 说明，不会崩也不会悄悄变。

挑字体先出对比图（同一版封面 + 同一张流程图 × 各预设，一眼看完）：

```bash
python <skill>/scripts/font_samples.py --src wechat-publish --out wechat-publish/showcase/_fonts
#   产出 font-samples.png；想只看某几套：--presets system,wenkai
```

封面右侧那块极淡主色默认空着。讲**循环 / 流程 / 分步**的文章用 `--motif ring` 在那里点一个环形意象
（N 个节点 + 顺时针箭头 + 圆心文字），`--motif-nodes` 填文章里的环节数：

```bash
python <skill>/scripts/make_assets.py -c wechat-publish/config.json -o wechat-publish/assets \
    --title "Agent Loop 运行原理" --subtitle "一次循环的七个环节" --date "2026.09" \
    --motif ring --motif-nodes 7 --motif-caption "7 STEPS" --only cover
```

圆心文字分主副两行（`--motif-label` 默认 `LOOP`、`--motif-caption` 默认空）。不想要意象就不加 `--motif`。

想先看**全部主题的封面长什么样**再决定用哪套（也用于验收新主题）：

```bash
python <skill>/scripts/cover_wall.py --title "文章标题" --subtitle "副标题" --date "2026.09" \
    --motif ring --motif-nodes 7 -o cover-wall
```

出 `cover-wall/cover-wall.png`，每格标注主题名 / 主色 / 点睛色 / 皮肤摘要。

### Step 4：发布前体检

```bash
python <skill>/scripts/preflight.py -c wechat-publish/config.json
```

**只查微信接口侧硬约束**（标题 32 字 / 作者 16 字 / 摘要 120 字 / 正文 1MB / 图片体积格式 / 外链图 / 残留围栏与 mermaid 源码）。排版问题不在这里查——那是 `validate_gzh_html.py` 的活。

> 「正文 2 万字符」这条**只提示不阻断**：官方文档写 2 万，但 2026-09-17 实测 `draft/add` 接受 45258 字符、回查 `draft/get` 得 45390 字符且尾部一致（完整落库未截断）。详见 `references/wechat-api-reference.md` 第二节。主题组件库是「每个元素挂满内联样式 + `span leaf` 包裹」的写法，体积天然是纯文本的 5~10 倍，压到 2 万以下会大幅牺牲版式，所以没再当硬约束。

输出 **P0 阻断 / P1 警告 / P2 建议** 三级清单，每项带「现象 + 处理」。

- 有 P0 → 退出码 1，**先修掉再往下走**。
- P1/P2 → 退出码 0，逐条判断。`--warn-only` 强制返回 0，`--json` 给 CI 用。

### Step 5：建草稿

```bash
python <skill>/scripts/publish.py draft -c wechat-publish/config.json
```

按顺序：**跑体检 → 取 token → 正文图上传换链 → 封面传永久素材 → 建草稿 → 回查确认**。
成功标志：输出 `draft media_id = ...`。
逃生口：`--no-preflight`（不建议）。

### Step 6：发布

- 认证账号：`publish.py publish --media-id <草稿id> -y`。`-y` 仅在用户已明确授权时使用；发布不可撤回，会真实推送给粉丝。
- 个人账号：**不要尝试**。告知用户到 mp 后台草稿箱手动点「发表」，并提醒个人订阅号每天有群发次数限制。

---

## 五、命令速查

| 命令 | 作用 |
|---|---|
| `render_mermaid.py article.md --theme X` | 排版前把 ```mermaid 渲染成 PNG，产出工作副本 |
| `render_mermaid.py --list-themes` | 列出已注册主题标识 |
| `highlight_code.py article.md --theme X` | 代码围栏 → 按语言着色的代码块组件（零依赖） |
| `highlight_code.py --check-widths` | 只看"哪几行会横滑"，不出 HTML |
| `highlight_code.py --show-palette --all-themes` | 打印各主题的高亮配色，排查"颜色突兀" |
| `validate_gzh_html.py <html>` | **产物关**：禁用标签 / `<span leaf>` / 半角标点 |
| `component_lint.py <skill>` | **源头关**：扫组件库反模式（改过主题库才需要） |
| `wrap_preview.py <html>` | 生成带「复制到公众号」按钮的预览页 |
| `extract_docx.py <docx>` | Word 转 Markdown |
| `preflight.py -c 配置` | 发布前体检（接口侧），`--json` / `--warn-only` / `--quiet` |
| `publish.py check` | 验凭证 + 白名单，不发内容 |
| `publish.py preflight` | 等价于单独跑 preflight.py |
| `publish.py draft` | 建草稿（安全档，推荐默认）。发请求前自动体检 |
| `publish.py publish` | 建草稿并立即发布 |
| `publish.py publish --media-id XXX -y` | 发布草稿箱里已有的一篇 |
| `publish.py list` / `--full` | 列草稿箱（`--full` 出完整 media_id） |
| `publish.py delete --media-id XXX -y` | 删除指定草稿（破坏性，需显式给 id） |
| `publish.py token -f` | 强制刷新 access_token（遇 40001 时用） |
| `watch_ip.py --draft` | 轮询等白名单生效，通了自动建草稿 |
| `make_assets.py` | 生成封面（需 pillow）；文案读 `config.cover`，`--motif ring` 加环形意象 |
| `cover_spec.py` | 封面几何规格 + 主题皮肤（单一来源；直接跑它可自检规格） |
| `cover_wall.py` | 出「同一篇文章 × 全部主题」的封面墙（换主题前预览 / 新主题验收） |
| `fonts.py` | 字体预设的唯一入口（封面 Pillow 与流程图浏览器共用一份）；直接跑可看解析结果 |
| `font_samples.py --src X --out Y` | 字体对比样张（封面 + 流程图 × 各预设），选字用 |
| `mermaid_local.js` | 流程图的本地渲染通道（playwright + 本机 Chrome；字体可控、内容不出本机） |
| `validate_skill.py` | 仓库自检（改完 skill 必跑，含封面规格与配色、字体预设接线护栏） |

通用参数：`-c 路径` 指定配置（默认按「当前目录/config.json → 脚本目录/config.json」查找）、`-f` 强制刷新 token、`-y` 跳过发布确认。
凭证也可用环境变量：`WECHAT_MP_APPID` / `WECHAT_MP_APPSECRET`。

---

## 六、平台约束全貌

写内容时最容易翻车的几条，数值都是官方原文口径（完整表见 `references/wechat-api-reference.md`）：

| 约束项 | 上限 | 超了会怎样 |
|---|---|---|
| 标题 | 32 字 | 微信直接报错 |
| 作者 | 16 字 | 直接报错 |
| 摘要 | 120 字（留空自动抓正文前 54 字） | 直接报错 |
| 正文体积 | **小于 1MB** | 直接报错 |
| 正文字符数 | 2 万（文档口径，**实测未强制**） | 见下方说明 |
| 原文链接 | 1KB | 直接报错 |
| 正文图片 | 仅 jpg/png，单张 < 1MB | 报 40005 / 40009 |
| 封面 | 必填，bmp/png/jpg/gif，< 10MB | 报 40007 |
| 外链图 | **不允许**，会被静默过滤 | 不报错，图直接没了 |
| `<style>` / `class` / JS | 会被剥离 | 不报错，样式全丢 |

> **2 万字符这条是文档口径，实测没强制**：官方写 `content`「必须少于 2 万字符，小于 1M」，
> 但 2026-09-17 实测 `draft/add` 接受 45258 字符、`draft/get` 回查得 45390 字符且尾部一致
> （完整落库、未截断）。本技能据此把它降为 **P1 提示（WX022）**，不阻断。
> 原因很实在：主题组件库是「每个元素挂满内联样式 + `span leaf` 包裹」的写法，
> 体积天然是纯文本的 5~10 倍，硬压到 2 万以下等于放弃版式。
> **1MB 字节数没有放松**，仍是 P0。剩余风险：正式发布（`freepublish` / 后台点发表）
> 是否会二次校验字数**未验证**，真报错再按主题库的精简组件重排或拆篇。
>
> **判长度别用 `wc -c`**：它数的是 UTF-8 字节，中文按 3 字节计，会把 1.6 万字的文章显示成 2.1 万。以 `preflight.py` 的 Python `len(html)` 输出为准。
>
> **微信兼容铁律**（主题库已按此写好）：装饰性空元素内部要放 `<span leaf=""><br></span>` 占位；不要把 `font-size`/`border-bottom` 打在 `<strong>` 上；同一个 `<p>` 里不混多个字号；不用 `position:absolute` 做划线；无内容的结构化区域整块删掉。
>
> **窄屏适配铁律**（全主题通用，覆盖 PC / 平板 / 各档手机）：手机正文最窄按 **288px** 算（320dp 机型），主流 360dp 是 328px，平板与 PC 只会更宽——**所有排版判断以 288px 为下限**。眉题/标签文字 `font-size ≤12px` 且 `letter-spacing ≥2px` 必须加 `white-space:nowrap` 并限字数（字距 2px ≤12 字符、4px ≤8 字符）；"标签+日期/星级"同行放不下就写成**确定性两行**，禁止靠 flex-wrap 挤压（X5 内核会把一侧挤出边界，实测）；多行代码块一律用通用库 1a/1b 横滑结构（外层 `overflow-x:auto` + 每行内联 `white-space:nowrap`，禁 `white-space:pre`，缩进用 `&nbsp;`）；固定 `width` 不得超 288px。交付前按 288px 视口自查一遍，并跑 `validate_gzh_html.py` 让窄屏类 warning 清零——该脚本会自动拦截这几类坏法。

---

## 七、排障要点

- 报 **40164**：白名单没配或没生效。拿 `errmsg` 里的 IP 核对后台是否保存 + 管理员是否扫码。用 `watch_ip.py` 挂着等，不要反复手点。
- 报 **48001**：账号类型限制，尤其 `freepublish`。转手动发布路径，别重试。
- 报 **40001**：token 被别处刷新导致缓存失效，`token -f` 重取。
- 报 **40007**：封面素材缺失，体检的 `WX040/WX041` 会提前拦。
- 报 **40005 / 40009**：正文图格式或体积不对，体检的 `WX030/WX031` 会提前拦。
- **代码块没有缩进、行尾注释全挤到代码后面**：手写时用了源码空格，被 HTML 折叠了（行首空格整层消失、连续空格压成一个）。用 `highlight_code.py` 生成，它会把行首与连续空格转成 `&nbsp;`。
- **代码块在手机上折行、对齐乱了**：漏了 `overflow-x:auto` + 逐行 `white-space:nowrap`。另外别拿桌面宽度判断"放不放得下"——手机正文只有 328px。
- **粘贴到公众号后样式全丢**：漏了 `<span leaf="">` 包裹。跑 `validate_gzh_html.py` 定位。
- **正文图片不显示**：用了外链图。改成 `assets/xxx.png` 本地相对路径，脚本自动上传换链。
- **正文莫名其妙超限**：先确认是 HTML 长度不是纯文本字数。另外本地编辑器/预览器会注入 `data-page-node-id` 之类记账属性，会把长度撑大——`preflight.py` / `publish.py` / `validate_gzh_html.py` 都会自动剥离，无需手工清理。
- **mermaid 图里印出 `<br data-page-node-id="…">`**：编辑器注入的记账属性污染了 mermaid 源码，会让它认不出 `<br/>`、当字面文本画出来。渲染完**一定要看一眼 PNG**——这类污染不报错、只画错。
- 发布提交成功但后台看不到：`errcode=0` 只代表任务提交成功，发布有延迟，最终结果走事件推送。
- 完整错误码表见 `references/wechat-api-reference.md` 第三节。

---

## 八、安全约束

- `config.json` 与 `.token_cache.json` 含密钥，**不要写入 git**，不要回显完整 AppSecret。
- 正式发布不可撤回。执行前必须让用户明确知情，默认只建草稿。
- AppSecret 若在对话或日志中明文出现过，提醒用户正式使用前到开发者平台重置。

---

## 九、仓库与迭代

本技能同时是开源仓库 `SkyBiuBiu/wechat-mp-publisher-skill`，仓库根目录即技能根目录。

> ⚠️ **上游署名（不可删除）**：排版链路（`references/theme-*.md`、`common-components.md`、
> `theme-generator.md`、`format-normalize.md`、`eval-cases.md`、`theme-index.md`、
> `assets/preview-template.html`、`assets/sample-article.md`，以及
> `scripts/validate_gzh_html.py`、`component_lint.py`、`wrap_preview.py`、`extract_docx.py`）
> 来自 [**isjiamu/gzh-design-skill**](https://github.com/isjiamu/gzh-design-skill)，
> 原创 **甲木 × 摸鱼小李**，授权 **AGPL-3.0**（原文见 `LICENSE-gzh-design`）。
> 这部分内容不得删改署名，也不得闭源再分发。

| 想找什么 | 去哪 |
|---|---|
| 主题清单与下划线色值（单一来源） | `references/theme-index.md` |
| 某套主题的全部组件 | `references/theme-{标识}.md` |
| 代码块/图片/GIF/小标签（跨主题通用） | `references/common-components.md` |
| 生成自定义主题 | `references/theme-generator.md` |
| docx/pdf/纯文本 → Markdown | `references/format-normalize.md` |
| 触发用例与回归核对 | `references/eval-cases.md` |
| 接口约束、权限矩阵、错误码 | `references/wechat-api-reference.md` |
| 面向人的完整手册 | `docs/manual.md` |
| 版本变更记录 | `CHANGELOG.md` |
| 开发约定与发版流程 | `CONTRIBUTING.md` |

**改动本技能前**：先读 `CONTRIBUTING.md` 的三条硬规则（零第三方依赖、跨平台、绝不提交密钥），改完执行 `python scripts/validate_skill.py` 自检，必须全绿。

改主题库组件时，改完必跑 `component_lint.py`；改产物装配逻辑时，改完必跑 `validate_gzh_html.py`。这两个脚本构成「改→验→修」闭环，不要绕过。

---

## 十、长文搬运与拆篇

把现成 HTML 文档（深色设计系统、Mermaid 图、高亮代码块）转成公众号图文时的实操要点：

1. **mermaid 图先跑 `render_mermaid.py` 渲染成 PNG**，装配时按图片组件引用，不要手动截图。
2. **代码块不要转图片**：用通用库 1a/1b 代码块组件，文字可选中、手机长按即复制。公众号剥 `<script>`，JS 一键复制按钮活不下来，「长按复制」是唯一可靠路径。
3. **深色设计系统 → 浅色内联样式**：正文转白底配色，代码块保留深色底；`display:grid`/CSS 变量公众号不可靠，须在装配时解析成具体值，多栏布局改纵向堆叠。
4. **拆篇只在必要时做**。2 万字符已不是硬约束（见第六节实测），主题组件库动辄 4~5 万字符也发得出去，
   所以**先按 `preflight.py` 的结果判断**：只有接口真回字数错误、或平台侧出现异常时才拆。
   真拆的话：按章节组成系列，标题用「主题①/②/③」编号，每篇独立 config（独立封面）逐篇跑 `draft`，篇尾加系列导航。
5. **推送前跑 `preflight.py`**：搬运场景最容易出的是图片路径断裂、残留围栏、上一篇残留内容。体检比人眼翻得快。
