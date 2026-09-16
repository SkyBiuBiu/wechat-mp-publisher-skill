# 视觉风格参考

公众号正文的**视觉**由预设决定：配色、字号、行高、圆角、卡片/表格/代码块的样式，全部写在
`assets/styles/*.json` 里，每条路线一个文件，由 `scripts/apply_style.py` 按 token 渲染进模板。

**预设只管视觉，不管文章内容与结构。** 写什么题材、分几节、每节讲什么、怎么开篇怎么收尾，
由正文自己的论证逻辑决定。预设文件里没有任何写作约束字段，这是刻意的 —— `validate_skill.py`
会拦住试图加回去的人。

## 一、六条路线怎么选

| 预设 id | 名字 | 视觉印象 | 常配题材 |
|---|---|---|---|
| `engineering-orange` | 工程橙 | 深暖灰表头 + 橙左竖线卡片，暖调橙韵 | 实战教程、架构拆解、踩坑复盘、工具评测 |
| `minimal-paper` | 极简纸感 | 无彩色块，白底细线留白，浅纸底代码 | 观点随笔、方法论、行业观察 |
| `terminal-green` | 终端绿 | 深色代码块当主角，绿调高亮，冷灰正文 | 源码分析、CLI 教程、配置详解、报错定位 |
| `magazine-warm` | 杂志暖调 | 暖陶米白底、大圆角卡片、暖调代码块 | 项目复盘、访谈、团队故事、年度总结 |
| `business-blue` | 商务蓝 | 藏蓝表头 + 冷灰正文，严谨汇报体 | 方案说明、选型对比、阶段汇报 |
| `checklist-qa` | 清单问答 | 青绿 Q/A 块 + 步骤条，扫读友好 | FAQ、SOP 流程、避坑清单、排错速查 |

「常配题材」只是挑配色时的参考，不限制你写什么。

选不准就看题材：**教人做事** → 工程橙 / 终端绿；**讲一个判断** → 极简纸感 / 商务蓝；**讲一件事** → 杂志暖调；**回答问题** → 清单问答。

> 默认 `engineering-orange`。它是唯一被标记为默认的预设（`apply_style.py --list` 里带 `*`）。

## 二、视觉层：token 字典

17 个 token，全部可在 `--set`、`config.style.overrides` 或自定义预设里改。

| token | 含义 | 取值要求 | 工程橙的默认值 |
|---|---|---|---|
| `primary` | 主题色：强调字、左竖线、步骤条 | `#rgb` / `#rrggbb` | `#c2410c` |
| `primary_soft` | 主题浅底：要点卡片背景 | 同上 | `#fff2e9` |
| `text` | 正文文字色 | 同上 | `#3d3a36` |
| `text_strong` | 加粗/小标题文字色 | 同上 | `#1d1a17` |
| `muted` | 次要文字：图注、引用、页脚 | 同上 | `#78716c` |
| `border` | 分隔线、表格行线 | 同上 | `#efe5de` |
| `card_bg` | 卡片/问答块背景 | 同上 | `#f7f2ed` |
| `code_bg` | 代码块背景 | 同上 | `#1c1917` |
| `code_text` | 代码块文字 | 同上 | `#f5f0ea` |
| `table_head_bg` | 表头背景 | 同上 | `#2b2119` |
| `table_head_text` | 表头文字 | 同上 | `#fdf3ec` |
| `font_size` | 正文字号 | 数字 + `px/em/rem/%` | `15px` |
| `heading_size` | 小标题字号（比正文大 2-3px 拉开层级） | 同上 | `17px` |
| `line_height` | 行高 | 纯数字或带单位 | `1.8` |
| `letter_spacing` | 字间距 | 同上 | `0.3px` |
| `radius` | 圆角 | 同上 | `6px` |
| `para_margin` | 段间距 | 同上 | `16px` |

**改动约束**（写错会被脚本直接拦下，不会静默生效）：

- 颜色必须是 `#rgb` 或 `#rrggbb`，不支持 `red`、`rgb()`、`var(--x)`。
  `var()` 尤其别用 —— 公众号会剥掉 CSS 变量定义，只剩一个无效值。
- 尺寸必须是数字 + 单位。`line_height` 允许纯数字（`1.8`）。
- 正文字号建议 15-16px，行高 1.75-1.9。体检脚本会对超出范围的取值给 P2 提示。
- **底色必须浅**。公众号正文是白底，深底配深字在手机上直接看不清；深色只用在代码块。

### 代码高亮配色（可选）

预设 JSON 顶层可加 `code_highlight` 段，覆盖 `enhance_content.py` 代码卡片的着色
（只写想覆盖的键，其余按 `code_bg` 明暗自动选深/浅默认板）：

| 键 | 作用 | 深底默认 | 浅底默认 |
|---|---|---|---|
| `keyword` | 关键字 / YAML·JSON 键 | `#ff7b72` | `#cf222e` |
| `string` | 字符串 | `#a5d6ff` | `#0a3069` |
| `comment` | 注释 | `#8b949e` | `#6e7781` |
| `number` | 数字 | `#79c0ff` | `#0550ae` |
| `function` | 函数调用 / HTML 属性 | `#d2a8ff` | `#8250df` |
| `variable` | Shell 变量 | `#ffa657` | `#953800` |

> **六套内置预设都自带与正文色系联动的代码高亮板**（写在各自预设的 `code_highlight` 段）：
> 工程橙 / 杂志暖调 = 暖调深底代码板；终端绿 = 绿调 GitHub 板；
> 极简纸感 = 浅纸底墨色板；商务蓝 / 清单问答 = 冷调深底板。
> 想整体换口味时，改预设的 `code_highlight` 即可，正文 token 不用动。

**代码卡片兼容性（实测）**：公众号 mp 后台打开草稿并保存时，会把 `<section>` 上的
`background` 剥掉，导致深色卡片退回白底纯文本。`enhance_content.py` 生成的代码卡片
已按「编辑器抗清洗」结构输出：背景/圆角写在单个 `<section>` 上，语言徽标与
「长按复制」合并为单行，不用 `display:flex` / `rgba()` / `white-space:pre-wrap`，
代码行靠 `<br>` + `&nbsp;` 保换行与缩进，`word-break:break-all` 兜底长行折行。
另注意：API 直接建草稿样式完整保留；若在 mp 后台手动保存过草稿，样式可能被清洗，
需重新用 `publish.py draft` 重建。

## 三、写作：预设不参与

预设里没有写作约束，因为**同一套配色要用在任何题材、任何结构上**。语气、人称、详略、
分几节、每节讲什么、怎么收尾，按这篇的实际需要定：

| 这篇想干什么 | 结构自然长成什么样 |
|---|---|
| 教人做事 | 按操作顺序走，一步一节 |
| 讲清一个机制 | 按「是什么 → 怎么运作 → 边界在哪」走 |
| 复盘一件事 | 按时间线走 |
| 回答问题 | 按问题组织，一问一节 |

要特定语气就在指令里说清楚，例如「结论先行、不要铺垫」「第一人称讲过程」「按给同行的密度写」，
跟选哪条配色路线无关。

**所有路线共同的底线**（公众号平台的硬约束，跟风格无关）：

- 不用「最」「第一」「唯一」「100%」这类绝对化表述 —— 广告法风险，详见 `SKILL.md` 的风控清单。
- 不放微信号、QQ、手机号、二维码 —— 平台禁止站外导流。
- 不诱导分享、集赞、强制关注。
- 金融保险类内容不做承诺性表述（保本、稳赚、零风险）。

## 四、自定义：三种粒度

### 1. 微调几个 token（最常用）

```bash
# 命令行临时改
python scripts/apply_style.py --preset engineering-orange --set primary=#1f4e8c

# 写进 config.json，长期生效（推荐）
```

```json
"style": {
  "preset": "business-blue",
  "overrides": { "primary": "#1f4e8c", "font_size": "16px" }
}
```

写了 `style.overrides` 之后，`apply_style.py` 不带 `--preset` 直接跑就会用这套配置（先读 `config.json` 的 `style.preset`，再用 `overrides` 覆盖）。
键名必须与 token 字典一致，写错会被 `apply_style.py` 拦下，`preflight.py` 也会报 `WX214`。

### 2. 基于内置预设改一版自己的（完整控制）

```bash
python scripts/apply_style.py --preset magazine-warm --dump my-style.json
# 编辑 my-style.json：只改 tokens（颜色 / 字号 / 间距 / 圆角）
python scripts/apply_style.py --style-file my-style.json -o article.html
```

导出的文件里 `tokens` 可以只留想改的几项，没写的会继承工程橙的默认值。预设里没有写作相关字段，
所以换配色不会顺带改掉写作方式。

想把自定义风格固化成团队资产，就把它放到 `assets/styles/<你的 id>.json`，这样 `--list`、`preflight.py` 的预设校验都会认它。

### 3. 只改写作方式、不动视觉

直接把要求写在给 AI 的指令里，例如「用工程橙的视觉，说话像给同事讲」。视觉由渲染决定，
写作由指令决定，两者本来就解耦。

## 五、渲染与校验的关系

```
config.json 的 style 段 ─┐
                        ├→ apply_style.py → article.html ─→ preflight.py → publish.py draft
assets/styles/*.json ───┘                                        ↑
                                                          也校验 style 段本身是否合法
```

- `apply_style.py` 只负责把 token 灌进模板，**不检查内容**。
- `preflight.py` 检查内容，同时校验 `style.preset` 是否存在、`style.overrides` 的键是否合法。

一次完整的风格化发布：

```bash
python scripts/apply_style.py --preset terminal-green -o work/article.html   # 1. 定风格
# 2. 把 article.html 改成自己的内容
python scripts/preflight.py -c work/config.json                              # 3. 体检
python scripts/publish.py draft -c work/config.json                          # 4. 建草稿
```
