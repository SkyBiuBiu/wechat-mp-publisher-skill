# Changelog

本项目的所有重要变更都记录在此文件。

格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

版本号同步保存在根目录 `VERSION` 文件，打 tag 时用 `v<版本号>`（例：`v0.1.0`）。

## [Unreleased]

### 计划中

- 多图文（一次草稿投多篇）支持
- `publish.py status --publish-id XXX` 查询发布任务最终状态
- 封面裁剪比例 `cover_info.crop_percent_list` 支持（`2.35_1` / `1_1`）
- 图片消息（`article_type=newspic`）支持

## [0.4.0] - 2026-09-16

### Changed

- **预设不再定义写作，只定义视觉**。六条路线预设原本各带一个 `writing` 段，用 `tone` /
  `opening` / `heading` / `paragraph` / `emoji` / `closing` / `avoid` 七个字段规定文章
  怎么写 —— 开篇必须怎样、小标题必须怎样、收尾必须落在哪。结果是同一路线的文章结构被
  锁死：工程橙的 `closing` 甚至写明了「收尾落到『所以什么场景该用、什么场景别用』」，
  每篇末尾都会长出一段选型清单。现整个 `writing` 段已从预设移除，预设只剩 `tokens`
  （配色 / 字号 / 间距）与 `code_highlight`（代码高亮）—— 文章写什么、分几节、怎么收尾，
  由正文自己的论证逻辑决定。
  - `SKILL.md` 第三节从「风格路线」改为「视觉风格」，写明预设不约束文章内容与结构
  - `references/style-presets.md` 的写作层章节改写为「写作：预设不参与」，给出按内容
    选结构的对照（教人做事 → 操作顺序 / 讲机制 → 是什么·怎么运作·边界 / 复盘 → 时间线 /
    问答 → 按问题组织）
  - `best_for` 改称「常配题材」，`apply_style.py --list` 输出时标注（参考，不限制你写什么）
  - `validate_skill.py` 新增守卫：预设含 `writing` 段、或有未识别的顶层键，即判为不合格
  - `README.md`、`docs/manual.md`、`assets/templates/config.example.json` 同步：术语统一为
    「视觉风格」，预设表去掉「语气」列，改为「视觉观感 + 常配题材（参考）」；`manual.md`
    第五节标题相应从「选风格路线」改为「选视觉风格」
  - 连带下线 `WX215`（唯一依赖 `writing.emoji` 的检查），体检规则 53 → 52

### Fixed

- **`publish.py list` 把 media_id 截断到 24 字符**，而删除草稿必须用完整 media_id ——
  等于列出来的 ID 没法直接用于 `delete`，得另外想办法取。现加 `--full` 开关输出完整 ID；
  默认仍截断，避免刷屏。配合 `delete --media-id` 就能走完「确认是哪一版 → 删掉」的闭环
- **编辑器注入的记账属性会污染成稿**：本地编辑器/预览器会往 HTML 里塞
  `data-page-node-id="…"` 之类的记账属性，注入点包括代码块与 mermaid 源码里的
  `<br/>`。混进 mermaid 源码后，mermaid 认不出这个 `<br>`、把它当字面文本渲染，
  图上会直接印出 `<br data-page-node-id="…">`。三处同步修掉：
  - `enhance_content.py` 渲染前剥离（含 ``` 围栏与 `<pre><code>` 两条路径）
  - `preflight.py` 与 `publish.py` 同样剥离，保证「体检的就是发送的」
  - `preflight.py` 的 2 万字符计数不再把这些属性算进去 —— 一份 1.5 万字符的稿子
    曾因此被误报成 22976 字符、判 P0 阻断
- `make_assets.py` 封面标题折行：旧版按 `len(title)` 对半切，英文标题会断在词中间
  （`Agent = Harness + Model` → `Agent = Harn` / `ess + Model`），且不测像素宽度，
  长标题会溢出画布。现改为：英文在空格处断、中文按 `textlength` 从视觉中点找断点，
  并支持用 `\n` 手动指定换行
- `preflight.py` WX112 误报：`enhance_content.py` 重建的代码卡片用单个 `<p>` 承载整段
  代码，天然超过 250 字，此前会被逐条报成「超长段落」。现按 `font-family:…monospace`
  识别并跳过 —— 代码卡片的长短由代码决定，不是排版问题
- `validate_skill.py` 密钥扫描：跳过 `.token_cache*.json`（.gitignore 已忽略的运行时
  产物，必然含 AppID）。此前只要在仓库内跑过一次请求，自检就会恒红
- `CHANGELOG.md` 有两个重复的 `## [Unreleased]` 与 `### Docs` 标题，合并为一

### Docs

- README 重构（两轮）：修正版本徽章（0.2.0 → 动态 v/tag）、token 数（16 → 17）、
  体检规则数（51 → 53）、封面建议（900×383 → 2x 高清 1800×766），补充 mermaid 高清
  与图片高清门槛说明；随后去掉「人/AI 双读者」「给 AI agent 的指引」等元叙事与模板化
  结构，改为自然叙述，消除 AI 味
- 仓库改名为 wechat-mp-publisher-skill：GitHub 仓库名、技能目录名、SKILL.md name、
  clone/badge URL、zip 产物名、User-Agent 与自检 banner 全部同步更新（旧 URL 由 GitHub 自动重定向）

## [0.3.5] - 2026-09-16

图片高清门槛：所有图片（封面 / 流程图 / 配图）发布前强制体检清晰度。

### Added

- 体检新规则 WX116（P1）：封面宽 <1200px 会糊；WX218（P1）：正文图片宽 <750px 会糊
- `make_assets.py` 素材生成升为 2x 高清（封面 1800×766、插图 1800×840，坐标/字号统一按倍率缩放）

### Changed

- WX212 封面门槛 600px → 1800px（未达 2x 高清报 P2 建议）
- WX213 正文图"过大"改为「宽 >2400px 且体积 >500KB」才提示，
  不再误报高清长图（如 3600px 宽的 mermaid 渲染图）
- SKILL.md / wechat-api-reference.md 同步登记新规则与依据类别

## [0.3.4] - 2026-09-16

mermaid 图高清化修复。

### Fixed

- mermaid.ink 远程通道此前漏传 `scale`/`width` 参数，输出的图固定为默认低分辨率，
  手机端放大显示会糊；现在与本地 mmdc 通道一致，按配置的 scale/width 高清渲染
- 默认值从 scale=2/width=800 提升到 scale=3/width=1200（约 13 倍像素），
  配置文件与模板同步

## [0.3.3] - 2026-09-16

新增 `heading_size` token + 六套预设美观度优化。

### Added

- 新增 token `heading_size`（小标题字号）：模板小标题不再跟正文同字号，
  层级由预设独立控制（工程橙/终端绿/商务蓝/清单问答 17px、极简纸感 18px、杂志暖调 19px）

### Changed

- 六套预设视觉微调：工程橙圆角 4→6px、浅底更饱和；极简纸感表头改浅灰底带
  （不再白底隐身）、圆角 2→3px；终端绿行高 1.75→1.8；
  杂志暖调表头改米白浅底 + 深棕字（杂志编辑风）；模板代码块示例同步为抗清洗结构

## [0.3.2] - 2026-09-16

代码卡片改为「公众号编辑器抗清洗」结构：实测 mp 后台打开草稿并保存时，
会把 `<section>` 上的 `background` 剥掉（深色卡片退回白底纯文本），
本次移除 `display:flex` / `rgba()` / `white-space:pre-wrap` / `overflow:hidden`，
语言徽标与「长按复制」合并为单行，字体族去掉 `&#39;` 实体，
背景与圆角直接写在单个 `<section>` 上，`word-break:break-all` 保留兜底长行折行。

### Changed

- `scripts/enhance_content.py` 的 `build_code_section()` 重构为最小依赖结构
- `references/style-presets.md` 补充代码卡片兼容性说明

## [0.3.1] - 2026-09-16

六套风格预设全面优化：配色协调 + 对比度 + 代码高亮联动。

### Changed

- 六套预设 token 全面重调：主色加深至 WCAG AA 对比度、中性色与主色冷暖底调统一、
  次要文字加深（图注/页脚可读）、圆角与字号按风格重新校准
- 每套预设新增顶层 \code_highlight\ 色板，与正文色系联动：
  工程橙/杂志暖调 = 暖调深底代码板；终端绿 = 绿调 GitHub 板；
  极简纸感 = 浅纸底墨色板；商务蓝/清单问答 = 冷调深底板

## [0.3.0] - 2026-09-14

两条新能力：**mermaid 渲染**与**代码块重建**（不转图片、可复制），
由新增的 `scripts/enhance_content.py` 提供，`draft` 前自动执行。

### Added

- `scripts/enhance_content.py` —— 内容增强器，零依赖
  - `mermaid`：```mermaid 围栏 / `<div class="mermaid">` 渲染成 PNG 并替换为
    `<img>`（本地 mmdc 优先，mermaid.ink 远程兜底；公众号剥 JS 与 SVG 文字，
    PNG 是唯一稳妥形态）。涉密图表可设 `mermaid.remote: false` 强制本地渲染
  - `code`：```lang 围栏与 `<pre><code>` 重建为全内联样式代码卡片：
    深底 + 语言徽标 + 离线语法高亮（python / js / java / go / bash / json /
    yaml / sql / html / css / diff），缩进 `&nbsp;`、换行 `<br>` 双保险，
    文字可选中、手机长按即复制——不转图片
  - 就地更新自动留 `.bak`；`--dry-run` / `-o` / `--no-highlight` / `--no-copy-hint` 可选
- `publish.py enhance` 子命令；`draft` 前自动跑增强，`--no-enhance` 跳过
- preflight 新增 2 条 P1（总规则 49 → 51）：`WX216` 残留 Markdown 围栏 /
  mermaid 源码、`WX217` `<pre>`/`<code>` 缺内联 `white-space` 样式
- 预设 JSON 支持可选 `code_highlight` 段覆盖高亮配色（默认按 `code_bg` 明暗自动选板）

### Changed

- `draft` 流程变为：增强 → 体检 → 取 token → 换链 → 建稿
- 体检 WX008 的处理建议更新为增强管线，不再建议把代码截图成图片

## [0.2.0] - 2026-09-14

两条线：**发布前约束体检**（把会翻车的地方在本地拦掉）与
**推文风格路线**（六条预设 + 三级自定义）。

### Added

- `scripts/preflight.py` —— 发布前体检，零依赖，不连微信、不需要凭证
  - 分 **P0 阻断 / P1 警告 / P2 建议** 三级，每项带「现象 + 处理」，
    输出末尾附正文字数进度条与图片/表格/封面统计
  - P0（19 条）：标题 32 字、作者 16 字、摘要 120 字、正文 2 万字符 / 1MB、
    原文链接 1KB、封面缺失/超 10MB/格式、正文图缺失/超 1MB/格式、外链图、
    base64 内嵌图、`<script>`
  - P1（16 条）：正文字数接近上限、`<style>`/`class`/`on*=`/iframe 等会被剥离的写法、
    站内锚点、图片缺宽度、表格缺 `border-collapse`/`padding`、超长段落、`h1`~`h6`、
    封面比例偏离 2.35:1、合规风险词
  - P2（14 条）：摘要留空、原文链接留空、评论未开、空段落、连续 `<br>`、
    字号行高越界、图片过多/分辨率过大、样式预设未选或 overrides 非法
  - 合规词库覆盖广告法绝对化用语、诱导分享/关注、站外导流、金融投资承诺、医疗疗效，
    **定位是风险提示而非违规判定**，`--no-compliance` 可整体跳过
  - `--json` 结构化输出，`--warn-only` 只报告不拦截
  - `errmsg` 之外的另一种前置防御：字数超限、图片超 1MB 这类问题以前要等微信报错
- `scripts/apply_style.py` —— 风格渲染器，把预设 token 灌进正文模板
  - `--list` / `--preset` / `--style-file` / `--set K=V` / `--dump` / `--show-tokens`
  - 自动读 `config.json` 的 `style` 段（`preset` + `overrides`），命令行参数优先级最高
  - token 键名与取值双重校验：颜色必须 `#rgb`/`#rrggbb`，尺寸必须带单位，
    写错直接报错，不会静默失效
- `assets/styles/` —— 六条风格路线预设（JSON，含视觉 token 与写作约束两段）
  - `engineering-orange` 工程橙（默认，技术干货）
  - `minimal-paper` 极简纸感（观点长文）
  - `terminal-green` 终端绿（源码与 CLI 教程）
  - `magazine-warm` 杂志暖调（叙事复盘）
  - `business-blue` 商务蓝（方案汇报）
  - `checklist-qa` 清单问答（FAQ / SOP / 排错）
- `assets/templates/article.template.html` —— 带 `{{token}}` 占位符的正文积木库，
  13 个可拆装的块（容器/开篇/强调/要点卡片/小标题/正文/表格/图片/引用/代码块/步骤条/问答/页脚）
- `references/style-presets.md` —— 风格路线选择表、16 个 token 字典与取值约束、
  写作层六个字段的含义、三级自定义方式、渲染与校验的关系
- `references/wechat-api-reference.md` 扩充
  - 字段约束表按官方原文口径补全（`image_info` 最多 20 张、`cover_info.ratio` 取值、
    商品数上限、`media_id` 长度），并标注 `content` 描述里「2kb」与「2 万字符」的自相矛盾
  - 新增第六节「本地预检口径」：全部 49 条检查项按 **官方硬约束 / 实测行为 / 经验阈值** 标注依据
  - 新增第七节「明确未覆盖的边界」：群发次数、审核规则、多图文、图片消息、封面裁剪坐标
- `SKILL.md` 新增第三节「风格路线」（选风格的方法与执行要求）、
  第四节「平台约束」（硬上限速查 + HTML 长度口径提醒）、Step 4「发布前体检」步骤

### Changed

- `publish.py draft` 现在**发请求前自动跑一次体检**，P0 未通过就地中止（此时还没联网）
  - 新增 `preflight` 子命令（转发给体检脚本，缺凭证也能跑）
  - 新增 `--no-preflight` 与 `--no-compliance` 两个逃生口
- `watch_ip.py --draft` 支持透传 `--no-preflight`
- `config.example.json` 新增 `style` 段（`preset` + `overrides`）与封面比例说明
- `validate_skill.py` 新增第 7 项检查：预设与文件名、token 字典、模板占位符三方对齐；
  必需文件清单加入新增的 4 个文件

### 兼容性

- 配置文件向后兼容：`style` 段可省略，省略时渲染用默认预设 `engineering-orange`，
  体检会给一条 P2 提示。
- `assets/templates/article.html` 保留可用（手工版样板），与新的占位符模板并存。

## [0.1.0] - 2026-09-14

首个可用版本。整条链路在**个人未认证订阅号**（公众号 `ImSkyBiuBiu`）上完成真实环境验证。

### Added

- `scripts/publish.py` —— 主脚本，零第三方依赖，仅用 Python 标准库，Windows / Linux 通用
  - 子命令：`check` / `draft` / `publish` / `list` / `delete` / `token`
  - `check`：仅验证凭证与 IP 白名单，不产生任何内容
  - `draft`：取 token → 正文图上传换链 → 封面传永久素材 → 建草稿 → 回查确认
  - `publish --media-id <id>`：发布草稿箱已有的一篇，不重复建稿
  - `delete --media-id <id>`：删除指定草稿（破坏性操作，需显式给 id）
  - token 本地缓存（7200s 有效期，提前 300s 失效），`-f` 强制刷新
  - 错误码中文翻译；40164 自动从 `errmsg` 提取被拒 IP
  - 正文 HTML 处理：剥离注释 → 识别本地相对路径图片 → 上传换链
  - 标题 32 字 / 摘要 120 字 / 正文 2 万字符本地预校验
- `scripts/watch_ip.py` —— 白名单生效轮询器，40164 消失后自动接管后续动作
- `scripts/make_assets.py` —— 生成封面（900×383）与正文插图，需 `pillow`，文案可配
- `scripts/validate_skill.py` —— 仓库自检：结构、frontmatter、语法编译、密钥扫描、引用路径
- `scripts/build_zip.py` —— 零依赖打包分发 zip，排除密钥与本机状态
- `references/wechat-api-reference.md` —— 接口字段约束、权限矩阵（文档口径 vs 实测）、错误码全表、白名单机制、正文 HTML 约束
- `assets/templates/article.html` —— 全内联样式的正文骨架
- `assets/templates/config.example.json` —— 配置模板
- `SKILL.md` —— WorkBuddy 技能入口
- 配套：MIT 许可证、CHANGELOG、CONTRIBUTING、GitHub Actions CI 与 Release 工作流

### 实测发现（写入 `references/wechat-api-reference.md`）

- 官方文档口径称 `material/add_material` 与 `draft/add` 仅服务号可用，
  实测**个人未认证订阅号全通**，无 `48001`。
- `freepublish/submit`（API 正式发布）实测返回 `48001 api unauthorized`。
  个人主体公众号无法申请微信认证，**该能力对个人号永久不可用**，属账号类型限制而非配置问题。
- AppID / AppSecret 的获取入口已从 mp 后台迁移至**微信开发者平台**
  （`developers.weixin.qq.com/platform`），旧路径文档失效。
