# Changelog

本项目的所有重要变更都记录在此文件。

格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

版本号同步保存在根目录 `VERSION` 文件，打 tag 时用 `v<版本号>`（例：`v0.1.0`）。

## [0.6.0] - 2026-09-17

配图与代码块的渲染质量此前一直靠"手写色值 + 排版完肉眼看"来保证，这次把两件事
都变成脚本可推导、可自检的行为。核心是新增 `scripts/theme_vars.py`：**主题「设计变量
速查表」从此只有一个解析入口**，封面、插图、代码块三处共用。

### Added

- **`scripts/highlight_code.py`（新）**：把代码围栏转成**按语言着色**的代码块组件
  （通用库 1a 深色 / 1b 浅色）。支持 python / bash / json / javascript / yaml / sql /
  dockerfile 及 C 系语言，其余标识按 C 系处理，`text`/`prompt`/`md` 不着色。
  配色**从主题推导**而不是写死，因此 6 套内置主题与任何自定义主题
  （`theme-generator.md` 产出的标准 `theme-<id>.md`）都自动适配，不必逐主题维护配色表。
  "不突兀"由三条可核对的约束保证：关键词取主色相同色相、函数取主色 +24°；
  深色底上所有 token 明度锁在 `L≈0.73~0.82`、饱和度 `0.30~0.42`，全篇只有"亮度一致"
  这一种变化；字符串/数字用主色 +200°（近似互补）的低饱和暖色，**运算符与标点不着色**。
  顺带把手写必然出错的两件事封进脚本：`< > &` 转义、每行 `<p style="margin:0">`
  （而非 `white-space:pre`）。
  `--show-palette --all-themes` 可打印各主题配色用于排查"颜色突兀"。
- **`scripts/theme_vars.py`（新）**：主题变量表的统一解析器。字段映射按消费者分别声明
  （`SCHEMAS`：封面拿「次要文字」做副标题、插图拿「辅助文字」做连线色，语义本就不同），
  支持 3 位与 6 位十六进制，剥离标签里的括号说明。命不中的字段返回 `None` 并列入
  `missing` 由调用方提示，**不再静默兜底** —— 静默兜底正是下面两个 bug 藏了这么久的原因。
- `render_mermaid.py` 新增**可读性体检**：渲染前量出图形原始版式宽度，推算这张图发到
  正文里究竟是多大的字，低于 11px 时提示，并在换方向能好 1.25 倍以上时**自动把
  `flowchart LR` 改成正交方向**（实测七节点长链 `7.8px → 25.6px`）。
  新增 `--font-size` / `--target-size` / `--keep-direction` / `--no-size-check`。
- `render_mermaid.py` 新增**显示宽度自适应**：窄图按"让字号落在正文惯用的 17px 上下"
  收窄显示宽度，避免满宽拉出一屏 40px 巨字 + 两张屏高的图；位图按 `显示宽度 × scale`
  出，窄图不再白白出 3600px 的巨图（实测两份插图 176KB→112KB、166KB→64KB）。

### Fixed

- **插图 PNG 此前是半透明底，微信点开大图直接糊掉。** mermaid.ink 默认返回 alpha 通道
  的 PNG（实测 alpha 0~255），而微信的大图查看器是**黑底**，深色文字压在黑底上等于没画。
  现在请求固定带 `bgColor=FFFFFF`，产物为不透明 RGB，体积反而更小。
- **橄榄手记（olive-journal）的插图长期用着摸鱼绿的绿。** 它的变量表标签写的是
  「主题墨色」而非「主色」，`render_mermaid.py` 的标签清单里没有这一项，于是静默退回
  内置兜底色。统一走 `theme_vars` 后修好。同类问题还有摸鱼票据的次要文字是 3 位十六进制
  `#888`，两处正则只认 6 位，取不到就丢掉了它的暖纸灰。
- **主色是墨黑/灰的主题，代码块配色推导出来的色相是噪声。** 橄榄手记主色 `#1e1f23`、
  石墨极简 `#52525B`，色相取自它们只会得到一片与主题无关的灰蓝。现在改用**绝对彩度**
  （通道差）判断色相是否可信，不可信时改取主题登记的点睛强调色的色相
  （`#ed7b2f` / `#F97316`）。判据不能用 HSL 饱和度：`#1e1f23` 的 HSL 饱和度有 0.077
  看着"有一点彩"，实际通道差只有 5/255，纯属舍入噪声 —— HSL 饱和度会低估低明度深色。

### Changed

- `render_mermaid.py` / `make_assets.py` / `highlight_code.py` 三处各自维护的主题变量
  解析全部改为共用 `theme_vars`，删掉重复实现。
- 配置项 `mermaid.width` 语义变化：不再是"所有图的出图宽度"，而是**量不到原始宽度时的
  兜底**；正常每张图的宽度由脚本按图逐张计算。
- `references/common-components.md` 新增 **1a+/1b+ 节**：代码块着色的叠加方式
  （着色包外层、`<span leaf="">` 仍在内层）、三条约束、以及为什么色值必须由脚本推导。

## [Unreleased]

### 计划中

- 多图文（一次草稿投多篇）支持
- `publish.py status --publish-id XXX` 查询发布任务最终状态
- 封面裁剪比例 `cover_info.crop_percent_list` 支持（`2.35_1` / `1_1`）
- 图片消息（`article_type=newspic`）支持

## [0.5.1] - 2026-09-17

### Added

- `make_assets.py` 封面新增意象 `--motif ring`：在封面右侧那块极淡主色里点一个
  「环形节点 + 顺时针箭头 + 圆心文字」的循环意象，节点数用 `--motif-nodes` 对齐
  文章里的环节数（讲循环 / 流程 / 分步的文章直接可用），圆心文字分主副两行
  （`--motif-label` / `--motif-caption`）。
  实现上单独开一层 RGBA 再 `alpha_composite` —— PIL 的 `ImageDraw` 画在 RGBA
  画布上是**直接写像素、不做混色**，低透明度图形必须走图层合成（同 `_wash` 的理由）
- `make_assets.py` 新增 `--only {all,cover,diagram}`。此前只想更新封面也会连带
  生成 `diagram.png`，工作目录里总留一份用不上的插图，还得手工删

## [0.5.0] - 2026-09-17

### Changed

- **排版与校验链路整体换成 gzh-design 组件库范式，旧的自研排版层全部删除。**
  原先的排版是「JSON 预设 token → `apply_style.py` 注入模板 → `preflight.py` 52 条规则兜底」，
  输出的是 class 自由、靠预设注入样式的 HTML。现改为上游
  [isjiamu/gzh-design-skill](https://github.com/isjiamu/gzh-design-skill)（甲木 × 摸鱼小李，
  AGPL-3.0）的组件库范式：Agent 读主题组件库手工装配纯 `<section>` 内联样式 HTML，
  文字全部 `<span leaf="">` 包裹，由双关卡脚本确定性兜底。
  - **6 套主题组件库**取代 6 套 JSON 预设：摸鱼绿（默认）/ 红白色系 / 石墨极简 /
    留白禅意 / 摸鱼票据 / 橄榄手记。每套 20~41 个精细组件 + 设计变量表 + 文章类型
    配方表 + 完整骨架 + Markdown 映射规则
  - 新增 `references/common-components.md`（跨主题通用组件：代码块 / 图片 / GIF /
    小标签标题）、`theme-generator.md`（自定义主题生成器）、`format-normalize.md`
    （docx/pdf/纯文本 → Markdown）、`eval-cases.md`（回归用例）
  - **校验拆成双关卡**：`validate_gzh_html.py` 查产物（禁用标签 / `<span leaf>` /
    半角标点），`component_lint.py` 查组件库源头（`white-space:pre` / 正文虚线框 /
    平台禁用项）。取代原 `preflight.py` 的 52 条排版规则
  - 新增 `wrap_preview.py` + `assets/preview-template.html`：生成带「复制到公众号」
    按钮的预览页，一键把富文本复制到剪贴板
  - 新增 `extract_docx.py`：Word 转 Markdown

### Added

- `scripts/render_mermaid.py`：从 `enhance_content.py` 抽出的 mermaid 预渲染器，
  脱离主题 token 体系（改从主题库「设计变量速查表」取主色），在**排版之前**把
  ```mermaid 围栏渲染成 PNG 并产出工作副本。支持 `--theme` / `--list-themes` /
  `--check` / `--config` / `--no-remote`
- `preflight.py` 转为**只查微信接口侧硬约束**（标题 / 作者 / 摘要长度、正文 2 万字符
  与 1MB、图片体积格式、外链图、base64 图、残留 Markdown 围栏与 mermaid 源码、
  封面比例与分辨率、主题标识是否已注册）。排版类规则全部移交双关卡脚本
- `config.json` 用 `theme`（主题标识）取代 `style.preset` / `style.overrides`；
  移除 `code.highlight` / `code.copy_hint`（代码块改由通用组件库承担）
- `validate_skill.py` 检查项重做：新增「主题注册表与组件库一一对应」「组件库源头关
  （复用 `component_lint`）」「上游署名与授权文件在位」「旧链路资产已清退」四项守卫
- `assets/templates/config.example.json` 同步新字段；删除 `article.html` /
  `article.template.html` 两个旧模板
- `tools/make_theme_previews.py`：README 主题样例配图的生成器。**同一段内容 × 六套主题**，
  每套都用该主题组件库里的真实组件装配，再用本机 Chrome 无头模式截图、裁掉底部空白。
  产出 `docs/images/theme-<标识>.png`，README 的「六套主题」一节直接引用。
  这是为了让「主题长什么样」有据可查——原来是张主色对照表，看不出视觉差异；
  拿示意图又会有「README 与实际不一致」的隐患。改了组件库必须重跑，
  这条已写进 `CONTRIBUTING.md` 第 9 条
- `build_zip.py` 新增 `EXCLUDE_REL_PREFIXES`：`docs/images/`（README 配图）与 `tools/`
  （开发辅助脚本）不进分发包——它们只服务于 GitHub 上的仓库本身
- README 重做结构：新增「这个仓库是什么」（讲清 MIT + AGPL-3.0 的双授权边界与
  「排版侧原样搬上游、只在发布侧加东西」的分工）与「六套主题」配图页；
  「双关卡校验」「发布前体检」升为独立章节，license 徽章改为 MIT + AGPL-3.0

### Fixed

- **「正文 2 万字符」从 P0 阻断降为 P1 提示（WX022）**。上游组件库是「每个元素挂满
  内联样式 + `<span leaf>` 包裹」的写法，一篇 8700 字纯文本的文章装配出来 4.5 万字符，
  按旧规则直接卡死，等于新范式根本发不出去。于是先做实测再改规则：
  **2026-09-17 用 `draft/add` 发 45258 字符 → 返回 `media_id`；`draft/get` 回查得
  45390 字符、尾部与原文一致 → 完整落库、未截断**（多出的 132 字符是微信自己补的）。
  官方文档写的是「必须少于 2 万字符」，但接口并未校验。据此：
  - `preflight.py` WX022 降为 P1，并把依据从「官方硬约束」改为新的第四类
    「**文档口径，实测未强制**」（该类结论一律带时间戳与测法）
  - `publish.py` 的 `CONTENT_MAX_CHARS` 硬 `die()` 改为提示，改名 `CONTENT_SOFT_CHARS`；
    `1MB` 字节数保持 P0（改名 `CONTENT_MAX_BYTES`）
  - 删除已无意义的 WX101（「达到上限 95%」）
  - 剩余风险写进文档：**正式发布**（`freepublish` / 后台点发表）是否二次校验字数**未验证**
- **WX104 从「正文用了 h1~h6」改为「h1~h6 没写内联 font-size」，并降为 P2**。
  旧规则与上游主题库直接冲突——摸鱼绿的步骤卡组件（`theme-moyu-green.md` 第 349/365/379/661 行）
  本来就用 `<h4 style="font-size:15px;font-weight:800;color:#111827;margin:0;">`。
  真正的风险只是没写内联字号时平台默认标题样式顶上来，所以改成按标签逐个检查是否带
  `font-size`，命中才提示，并给出「照抄组件库写法」的处理办法
- **`make_assets.py` 改为主题驱动配色**。原来封面硬编码深色底 + 工程橙，主题换成浅色系
  （如摸鱼绿）后封面色调与正文完全脱节。现在从 `references/theme-<id>.md` 的
  「设计变量速查表」里解析 `主色调 / 标题色 / 正文色 / 辅助文字 / 极浅底`，
  支持 `-c config.json`（跟着 config 的 `theme` 走）、`--theme <id>`、`--dark`（回到旧深色版式）；
  读不到主题时给出提示并回退，不静默出错。`make_flow` 同步支持浅色主题
- 清理 `with_compliance` / `--no-compliance` 两处死参数（旧合规词库早已移除，传了也没作用，
  留着会让人误以为还有这类检查）

### Removed

- `scripts/apply_style.py`、`scripts/enhance_content.py`、`assets/styles/*.json`（6 套预设）、
  `references/style-presets.md`、`assets/templates/article.html`、
  `assets/templates/article.template.html`
- `publish.py` 的 `enhance` 子命令与 `--no-enhance` 参数

### CI/CD

- **发版流程改为「推送版本更新即自动打 tag + 发 Release」。** 原 `release.yml` 只监听
  `push: tags: v*`，必须有人手工 `git tag && git push --tags` 才会动——0.5.0 的代码已经推上
  main，tag 与 Release 却一直没有，就是这么漏的。现在：
  - 触发条件增加「main 分支上 `VERSION` 文件发生变化」，同时保留 tag 推送与手动触发
  - 新增两道发版前守卫：`VERSION` 必须是合法语义化版本；`CHANGELOG.md` 必须已有对应的
    `## [x.y.z]` 段落——不满足直接失败，避免发出没有变更记录的 Release
  - 步骤顺序改为「自检 → 打包 → 建 tag → 发 Release」，**都通过之后才创建 tag**，
    不留指向坏提交的 tag
  - 建 tag 幂等：远端已有同名 tag 就跳过
- **为什么打 tag 与发 Release 必须写在同一个 workflow 里**：GitHub 规定「用仓库自带的
  `GITHUB_TOKEN` 推送 tag，不会触发其他 workflow」（防递归）。若拆成「workflow A 打 tag →
  workflow B 监听 `v*` 发版」，B 一次都不会跑。这条限制已作为注释写在 `release.yml` 顶部，
  避免以后有人「顺手拆开优化」。
- **Release 说明改为取自 `CHANGELOG.md` 对应版本的段落**。原先用 action 自带的
  `generate_release_notes`，它只按「已合并的 PR」生成——本仓库是直推 main、不走 PR，
  实测生成出来只有一行 `Full Changelog` 链接，等于发了条没有说明的 Release。
  现在提取 `## [x.y.z]` 段落作为正文，并自动附上「上一版…本版」的 compare 链接
  （上一版由 tag 列表按版本号降序取，不依赖当前 tag 是否已存在）。
- **步骤顺序固定为「自检 → 打 tag → 检出 tag → 打包 → 发 Release」**。打包前先
  `git checkout refs/tags/<tag>`，保证 Release 附带的 zip 与 tag 内容严格一致。
  原顺序是「打包 → 打 tag」，一旦版本推上去之后 main 又多了别的提交（例如补修 CI），
  事后补发 Release 就会挂一个与 tag 对不上的包——`build_zip.py` 是会把
  `.github/workflows/` 和 `CHANGELOG.md` 打进包里的，这些恰好最容易在发版后被改动。
  已实测确认该不一致确实发生（v0.5.0 补发时包的来源提交与 tag 指向的提交不同），
  故把顺序纠正过来。

### Notes

- 上游排版链路为 **AGPL-3.0**，授权原文保留在 `LICENSE-gzh-design`，README / SKILL.md
  均标注来源与署名，请勿删除。本仓库自有部分（发布链路）仍为 MIT
- `SKILL.md` 重写为「排版链路 + 发布链路」双段式工作流，排版段完整保留上游的
  主题选择决策表、智能处理要求、视觉层级与 gotchas

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
