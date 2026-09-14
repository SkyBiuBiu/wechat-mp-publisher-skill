# 风格路线参考

公众号正文的风格由**两层**共同决定，改风格要两层一起改，只改一层会拧：

| 层 | 管什么 | 谁来执行 |
|---|---|---|
| **视觉层** | 配色、字号、行高、圆角、卡片/表格/代码块的样式 | `scripts/apply_style.py` 按预设 token 渲染模板 |
| **写作层** | 语气、开篇方式、段落长度、小标题形式、emoji 用法、收尾 | 写正文时遵循预设 `writing` 段的约束（AI 或人） |

预设文件在 `assets/styles/*.json`，每条路线一个文件，包含这两层的定义。

## 一、六条路线怎么选

| 预设 id | 名字 | 视觉印象 | 语气 | 适合 |
|---|---|---|---|---|
| `engineering-orange` | 工程橙 | 深灰表头 + 橙色左竖线卡片，克制 | 结论先行，像交接文档 | 实战教程、架构拆解、踩坑复盘、工具评测 |
| `minimal-paper` | 极简纸感 | 无彩色块，只有留白和细横线 | 平静有判断，允许有观点 | 观点随笔、方法论、行业观察 |
| `terminal-green` | 终端绿 | 深色代码块当主角，绿色强调 | 直给可执行，每条结论配命令 | 源码分析、CLI 教程、配置详解、报错定位 |
| `magazine-warm` | 杂志暖调 | 暖米底、圆角卡片、引文块 | 有温度不说教，第一人称叙事 | 项目复盘、访谈、团队故事、年度总结 |
| `business-blue` | 商务蓝 | 蓝表头 + 编号要点，严谨 | 客观有依据，判断后面跟数据 | 方案说明、选型对比、阶段汇报 |
| `checklist-qa` | 清单问答 | 青绿 Q/A 块 + 步骤条，扫读友好 | 干脆，一问一答 | FAQ、SOP 流程、避坑清单、排错速查 |

选不准就看题材：**教人做事** → 工程橙 / 终端绿；**讲一个判断** → 极简纸感 / 商务蓝；**讲一件事** → 杂志暖调；**回答问题** → 清单问答。

> 默认 `engineering-orange`。它是唯一被标记为默认的预设（`apply_style.py --list` 里带 `*`）。

## 二、视觉层：token 字典

16 个 token，全部可在 `--set`、`config.style.overrides` 或自定义预设里改。

| token | 含义 | 取值要求 | 工程橙的默认值 |
|---|---|---|---|
| `primary` | 主题色：强调字、左竖线、步骤条 | `#rgb` / `#rrggbb` | `#d94f22` |
| `primary_soft` | 主题浅底：要点卡片背景 | 同上 | `#faf7f4` |
| `text` | 正文文字色 | 同上 | `#3f3f3f` |
| `text_strong` | 加粗/小标题文字色 | 同上 | `#222222` |
| `muted` | 次要文字：图注、引用、页脚 | 同上 | `#8a8a8a` |
| `border` | 分隔线、表格行线 | 同上 | `#eeeeee` |
| `card_bg` | 卡片/问答块背景 | 同上 | `#f7f8fa` |
| `code_bg` | 代码块背景 | 同上 | `#16181d` |
| `code_text` | 代码块文字 | 同上 | `#e8eaee` |
| `table_head_bg` | 表头背景 | 同上 | `#333333` |
| `table_head_text` | 表头文字 | 同上 | `#ffffff` |
| `font_size` | 正文字号 | 数字 + `px/em/rem/%` | `16px` |
| `line_height` | 行高 | 纯数字或带单位 | `1.8` |
| `letter_spacing` | 字间距 | 同上 | `0.4px` |
| `radius` | 圆角 | 同上 | `3px` |
| `para_margin` | 段间距 | 同上 | `18px` |

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

## 三、写作层：每条路线的约束

`writing` 段里六个字段各管一件事，写正文时逐条对照：

| 字段 | 管什么 |
|---|---|
| `tone` | 整体语气，决定用词和句式 |
| `opening` | 第一段怎么写，决定读者会不会往下滑 |
| `heading` | 小标题的形式与长度 |
| `paragraph` | 段落长度与拆分规则 |
| `emoji` | 允许、克制还是禁用 |
| `closing` | 结尾落在哪 |
| `avoid` | 明确要避开的写法 |

各路线摘要：

| 预设 | 开篇 | 段落 | emoji | 收尾 |
|---|---|---|---|---|
| 工程橙 | 第一段直接给结论或痛点，禁「大家好」 | ≤3 行（约 90 字） | 禁用 | 落到「什么场景用、什么场景别用」 |
| 极简纸感 | 从具体场景或反常识观察切入 | 2-3 行，允许单句成段 | 禁用 | 留一个判断或开放问题，不总结全文 |
| 终端绿 | 先给环境前提（系统/版本/依赖）再给目标 | ≤2-3 行，代码不夹段落里 | 禁用 | 给验证命令与预期输出 |
| 杂志暖调 | 一个时间点或场景细节先入现场 | 长短交替，关键判断单独成段 | 克制，最多 1-2 个 | 落到具体的人或下一步 |
| 商务蓝 | 第一段给结论摘要 | 能表格就不写段落 | 禁用 | 给下一步动作与时间点 |
| 清单问答 | 开门见山说「适用场景 + 几条」 | 结论一句 + 补充说明 | 允许 ✅❌，其他不用 | 一张速查表 / 最容易漏的 3 件事 |

**所有路线的共同底线**（公众号平台的硬约束，跟风格无关）：

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
# 编辑 my-style.json：改 tokens 颜色，改 writing 的 tone/opening/paragraph 等
python scripts/apply_style.py --style-file my-style.json -o article.html
```

导出的文件里 `tokens` 可以只留想改的几项，没写的会继承工程橙的默认值；`writing` 段是纯文本说明，改它不影响渲染，但会约束写作。

想把自定义风格固化成团队资产，就把它放到 `assets/styles/<你的 id>.json`，这样 `--list`、`preflight.py` 的预设校验都会认它。

### 3. 只改写作约束、不动视觉

直接把要求写在给 AI 的指令里，例如「用工程橙的视觉，但语气参考极简纸感」。视觉由渲染决定，写作由指令决定，两者可以解耦。

## 五、渲染与校验的关系

```
config.json 的 style 段 ─┐
                        ├→ apply_style.py → article.html ─→ preflight.py → publish.py draft
assets/styles/*.json ───┘                                        ↑
                                                          也校验 style 段本身是否合法
```

- `apply_style.py` 只负责把 token 灌进模板，**不检查内容**。
- `preflight.py` 检查内容，同时校验 `style.preset` 是否存在、`style.overrides` 的键是否合法，
  并按预设的 `emoji` 策略检查正文有没有违反（例如工程橙禁 emoji，正文里出现就会提示 `WX215`）。

一次完整的风格化发布：

```bash
python scripts/apply_style.py --preset terminal-green -o work/article.html   # 1. 定风格
# 2. 把 article.html 改成自己的内容
python scripts/preflight.py -c work/config.json                              # 3. 体检
python scripts/publish.py draft -c work/config.json                          # 4. 建草稿
```
