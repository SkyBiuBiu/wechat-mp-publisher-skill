# Changelog

本项目的所有重要变更都记录在此文件。

格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

版本号同步保存在根目录 `VERSION` 文件，打 tag 时用 `v<版本号>`（例：`v0.1.0`）。

## [0.9.1] - 2026-09-17

0.9.0 交付后的一轮完整自查，把漏改的地方补齐。

### Fixed

- **主题样张的标题不再写死文章名**：`build_theme_showcase.py` 原先把"Agent Loop 运行原理"
  硬编码进标题，换一篇稿子跑这个脚本标题就跟内容对不上了。现在从源 `config.json` 的
  `article.title` 取主标题（只取冒号前那段），前缀与标题之间补上分隔空格，
  并按微信 32 字硬上限自动裁剪。
- **删除草稿不再把截断的 media_id 扔给微信**：`publish.py delete` 现在先校验 id 长度，
  截断的 id 直接提示改用 `list --full` 取完整值；40007 的错误码提示也从
  "封面素材可能被删了"改为列出两种真实原因（id 截断 / 素材已删）。

### Docs

- 预设清单补齐 `rounded`：`fonts.py` 模块文档串、`config.example.json` 的 `_font` 说明。
- 0.9.0 段补记：`rounded`(MiSans) 预设、半截字体文件的 sfnt 完整性校验、
  以及被宽 `except` 吞掉的 `_axis_name` 未定义问题。

## [0.9.0] - 2026-09-17

封面与流程图可以换字体了，并且**换的是同一套字体**；流程图多了一条**本地渲染**通道 ——
图内字形终于可控，图表内容也不再离开本机。

起因很直接：字一直是"系统装了什么就用什么"。封面走 Pillow（认字体文件）、流程图走
mermaid.ink（字体在**对方服务器**上找）—— 两边都不认"预设"这个概念，`fontFamily` 写了也白写，
于是"换个好看的字体"这件事在两条链路上都做不到。

### Added

- **`scripts/fonts.py`：字体预设的唯一入口。** 五个预设 —— `system`（系统黑体，默认）/
  `wenkai`（霞鹜文楷）/ `serif`（思源宋体标题 + 思源黑体正文）/ `sans`（思源黑体）/
  `rounded`（MiSans，圆润科技风：标题 Demibold + 正文 Regular）。
  封面与流程图**共用这一份清单**：Pillow 要文件路径、浏览器要族名 + `@font-face`，
  两边各写一份必然漂成"封面换了字、图没换"。查找顺序 `WMP_FONT_DIR` →
  `<skill>/assets/fonts/` → `~/.workbuddy/fonts/` → 系统字体，缺哪个角色退回哪个角色
  并在 stderr 说明（**不静默变**）。字体文件不入分发包：一套中文 17~26MB，
  `build_zip.py` 已排除 `assets/fonts/` 与 `assets/vendor/`。
- **`scripts/mermaid_local.js`：流程图的本地渲染通道**（playwright 驱动本机 Chrome）。
  把 mermaid.js 与 `@font-face` 一起喂进浏览器，图内字形可控；顺带两个好处：图表内容不再
  发给第三方，体检用的 SVG 与出图用**同一份渲染**（原先体检走 mermaid.ink，字号估算与
  实际出图可能不是一回事）。找不到 mermaid.js 时按需下载一份到 `assets/vendor/` 缓存。
  通道顺序变为 **本地 Chrome → mmdc → mermaid.ink**，走到哪条、为什么没走本地都会打印。
- **`scripts/font_samples.py`：选字对比样张。** 同一版封面 + 同一张流程图 × 各预设，
  拼成一张 `font-samples.png`。字体好不好看文字描述不出来，只能看。
- `render_mermaid.py` 新增 `--font-preset` / `--list-fonts` / `--no-local`；
  非 `system` 预设会**强制**走本地通道（在线通道看不到 `@font-face`）。
- `make_assets.py` 新增 `--font-preset` / `--list-fonts`，并支持 `config.json` 的 `font.preset`。
- `config.json` 新增 `font.preset`、`mermaid.local`、`mermaid.font_preset`。
- `validate_skill.py` 第 10 项：字体预设接线（两处消费方是否都接了 `fonts.py`、
  本地通道脚本与 `@font-face` 是否在位、族名是否只从 `fonts.FAMILY_TPL` 生成、
  本机可用预设等）。

### Fixed

- **可变字体默认实例是最细档**：思源宋体默认 `wght=200`（ExtraLight）、思源黑体默认
  `wght=100`（Thin）—— 不显式设字重轴，封面标题会是一副"细细的、怪怪的"样子，
  还容易被误判成"字体没换成功"。
- **Pillow 的轴名是 bytes**（`b'Weight'`），`str()` 之后是 `"b'weight'"`，
  与 `"weight"` 匹配不上 → 字重设置静默失效。已按字节解码后比对。
- **半截字体文件也会被选中**：Pillow 的 `truetype` 是惰性加载，下载到一半的字体能"成功打开"，
  渲染时才缺字（现象是封面画成一堆默认位图字，且不报错）。现在按 sfnt 表目录校验
  `offset + length <= 文件长度`（TTC 先解 `ttcf` 头），坏文件跳过继续找下一个候选，
  而不是整体退回系统字体。
- **宽 `except` 吞掉了"函数不存在"**：`_weight_range` 调用了一个从未定义的 `_axis_name`，
  `NameError` 被 `except Exception: pass` 静默吃掉，字重区间查询一直在用默认值。
  现已补上定义（bytes 轴名统一解码），两处共用。

### Notes

- 封面观感取决于机器上有没有对应字体：没有就退回系统黑体（行为与 0.8.0 一致），
  所以这个版本对没装字体的环境是**无感升级**。

## [0.8.0] - 2026-09-17

封面从"配色跟着主题走"升级为**一套显式版式规格 + 可辨的主题质感皮肤**。
起因是六主题封面并排看时暴露的三个问题（都不是报错，而是观感退化）：

| 问题 | 根因 |
|---|---|
| **橄榄手记封面整张灰白** | `make_cover` 里 `accent = theme["primary"]` —— 点睛色被赋成了主色。它主色是墨黑 `#1e1f23`，登记的强调橙 `#ed7b2f` 全程没上场 |
| **石墨极简 / 留白禅意看不出"有颜色"** | 右下色块透明度只有 26、环形意象的环 60 / 节点 96，主色基本隐形 |
| **摸鱼绿与摸鱼票据风几乎一模一样** | 两者主色同为 `#059669`，底、色块、环、线条全同色；唯一的差异来自字体 fallback 的偶然 |

> ⚠️ **封面观感会变**：所有主题的封面都重新调过，已发布过的旧封面与新稿不一致，需要重出。

### Added

- **`scripts/cover_spec.py`**：封面的**几何规格**（`SPEC`）与**主题质感皮肤**
  （`THEME_SKINS`）的单一来源。原先这些坐标散在 `make_cover()` 的绘制逻辑里，
  "风格统一"靠的是代码恰好只有一份，而不是一份写下来的规格 —— 既没法断言，
  也容易漂。现在 `SPEC` 收全了画布 / 竖条 / 品牌行 / 标题单双行基线 / 分隔线 /
  副标题 / 日期 / 右下色块 / 环形意象的每一个数，`make_cover` 不写字面坐标。
  直接跑 `python scripts/cover_spec.py` 可自检（比例、元素是否出画布、基线顺序、
  环形意象是否侵入文字区）。
- **点睛色角色 `accent`（封面侧）**：`theme_vars.SCHEMAS["cover"]` 新增该角色，
  候选顺序为「强调橙 / 强调色 / 点睛色 / 标签文字色 / 下划线标记色 / 荧光笔色」。
  橄榄手记 `#ed7b2f`、石墨极简 `#F97316` 因此真正上了封面（环 / 竖条 / 品牌方块 / 分隔线），
  没登记点睛色的主题（摸鱼绿 / 红白 / 摸鱼票据风）按设计回退主色。
  禅意没有前三项中的任何一个，取到的是 `标签文字色 #3D5046`（深墨绿）而**不是**
  `下划线标记色 #B5C8BC` —— 后者太淡，画成 2px 线会直接消失。
- **主题质感皮肤**：底色倾向、竖条宽度与颜色、外框描边、圆角、底纹、字型。
  同色 / 近无彩主题靠它区分，**不动主题库任何色值**：
  摸鱼票据风 = 米黄纸底 + 2px 黑硬边 + 12px 黑竖条 + 撕票虚线 + 直角；
  摸鱼绿 = 近白底 + 8px 绿竖条 + 大圆角；留白禅意 = 直角 + 一条极细底线 + **衬线标题** + 纯白底；
  石墨极简 = 5px 石墨灰竖条 + 小圆角 + 橙色只占 3 处。未登记皮肤的新主题按主色**彩度**
  自动推导（近无彩则自动把点睛色提为主视觉色），不会重蹈"封面整张没颜色"。
- **`scripts/cover_wall.py`**：出「同一篇文章 × 全部主题」的**封面墙**，每格标注
  主题名 / 主色 / 点睛色 / 皮肤摘要。这是"同色主题会不会看混"的验收口，
  也是新增主题的自动验收口（登记进 `theme-index.md` 后重跑就该出现）。
- **`config.json` 的 `cover` 段**：封面文案（brand/title/subtitle/date/motif…）
  收口到配置，优先级 **命令行 > `cover` 段 > `article.title` > 内置默认**，
  运行时打印生效来源。没有该段的老配置照常工作。

### Changed

- **封面的主色占比整体提高**：右下色块透明度 26 → 34（皮肤可调）、环形意象的环
  60 → 92、节点 96 → 132、分隔线 94×2px → 140×3px，品牌行前加一枚点睛色方块。
- **日期色比副标题再浅一档**（`theme_vars.mix` 往底色混合 35%）：摸鱼票据风只有
  「次要文字」一个灰档位，`aux` 与 `body` 会取到同色，靠这一步拉开层次，
  不必让主题库为封面多登记色值。
- **`theme_vars.asset_theme()` 返回值新增 `accent` 与 `accent_own`**；`cover.aux`
  候选末尾追加「次要文字」（修摸鱼票据风 `aux` 缺失导致的静默回退）。
- **`build_theme_showcase.py`** 不再重复拼一长串封面参数，改为把 `cover` 段写进
  每版 `config.json`。
- **内置深色版式（`--dark`）** 随之获得同样的层次（更长的分隔线、更清晰的环、品牌方块），
  配色仍是原来的深色橙调。

### Docs

- `docs/manual.md` 封面章节扩写：规格与皮肤表、`cover` 段与优先级、封面墙用法。
- `README.md` / `SKILL.md`：封面能力描述与脚本清单补 `cover_spec.py` / `cover_wall.py`。
- `assets/templates/config.example.json` 补 `cover` 段示例。

### Fixed

- **`validate_skill.py` 新增封面护栏**（第 9 项检查）：①规格自洽（比例 / 不出画布 /
  基线顺序 / 环形意象位置）②画布比例与 `preflight.COVER_RATIO` **同源比对**
  （两处各写一个数就会漂）③六套主题的六个封面角色**全部非 None**（缺失会静默回退兜底色）
  ④**主题登记了点睛色时断言它不等于主色** —— "登记了却没用上"从此会 FAIL，
  且不需要人工白名单（判定条件是"速查表里能否解析出 accent"，自动成立）
  ⑤皮肤表 key 必须都已注册到 `theme-index.md` ⑥`make_cover` 里不许再出现字面坐标（防回潮）。

## [0.7.4] - 2026-09-17

### Fixed

- **`build_theme_showcase.py --push` 的 access_token 互相失效**：`publish.py` 是按
  `config.json` **所在目录**找 `.token_cache.json` 的，所以六个样张目录各自持有一份缓存；
  而公众号的 `access_token` 是**单点有效**的——逐版各自去换 token，后换的会让先换的失效，
  表现为"推第一版成功、推第二版 40001"（手工绕过办法是把主目录的缓存逐个拷过去）。
  现在 `--push` 会**先为基准目录取一次 token，再把这份缓存分发给每一版**，全程不重复换 token。

### Docs

- `docs/manual.md` 的主题样张章节补记该机制，省得以后又去手工拷缓存。

## [0.7.3] - 2026-09-17

修一个**交付缺口**：v0.7.2 的头号新特性 `build_theme_showcase.py` 放在了 `tools/` 下，
而 `build_zip.py` 的 `EXCLUDE_REL_PREFIXES` 会整目录排除 `tools/` ——
**从分发包（zip）安装的用户拿不到六主题样张流水线**，只有克隆仓库的人能用。
而它是面向用户的能力（"所有预设各推一版到草稿箱"是用户的真实诉求），
不是 `make_theme_previews.py` / `make_code_preview.py` 那类开发辅助。

### Changed

- **`build_theme_showcase.py` 由 `tools/` 移入 `scripts/`** —— 与其它 user-facing
  脚本同级，现在**随分发包一起发布**。脚本内部的路径解析（`SKILL = dirname(HERE)`
  + `SKILL/scripts`）在移动后结果一致，无需改动逻辑；仅更新了 docstring 里的用法示例。
- `tools/` 的定位收窄为"纯开发辅助、需本机 Chrome/playwright、不进分发包"
  （`make_theme_previews.py` / `make_code_preview.py` / `shot_article.js` /
  `narrow_screen_check.js`），README 目录树与说明同步对齐。

## [0.7.2] - 2026-09-17

新增「同一篇文章 × 全部预设」的**主题样张流水线**：一次生成六版可推送的成稿
（每版含按主题配色的 mermaid 流程图与着色代码块），逐版推进草稿箱横向对比。
起因是用户要求"所有预设都推送一版到草稿箱，要体现流程图、代码等格式"——
光看主题索引的色值表想象不出成篇效果。

### Added

- **`scripts/build_theme_showcase.py`**：以一篇已排好的基准稿（`article.html` +
  `article.md` + `config.json`）为输入，输出 `moyu-green / red-white /
  graphite-minimal / zen-whitespace / moyu-ticket / olive-journal` 六版成稿。
  换掉的是**主题身份**而非版式骨架，所以每版都继承基准稿的 288px 窄屏加固：
  ① 配色（主题变量表色板）；② 结构质感（圆角倍率、卡片描边、阴影气质——
  票据=硬阴影黑描边、禅意/石墨/橄榄=细线无影、红白=淡红描边）；
  ③ 字体与代码块（字体栈、标题衬线与否、深色/浅色代码块）；
  ④ mermaid 按主题重渲、代码块用 `highlight_code.palette()` 重生成。
  产出还含一份 `index.html` 六版并排对比页；`--push` 可逐版推草稿箱。
- **`tools/shot_article.js`**：样张目视核对截图（playwright，顶部区/流程图/代码块
  三段），供人工或模型审阅渲染结果——脚本量不出"配色扎不扎眼"。

### Fixed

- **主题变量标签别名缺口**：红白系缺 `light`/`tint`、石墨极简缺 `body`，导致
  `render_mermaid` 的插图配色与封面底色**静默回退中性默认色**（不报错，只是
  画出来不是主题色）。`theme_vars.SCHEMAS` 补齐别名：`主色调背景` → light、
  `主色调极浅` → tint、`次要文字色` → diagram body。三处均为"只增不删"的
  标签追加，不影响既有主题已取到的色。
- **`theme_vars.py` 模块头**补记"标签只增不删"的原因（删标签会让某主题静默
  退化成兜底色）。

## [0.7.1] - 2026-09-17

窄屏适配从"摸鱼绿单主题修复"推广为**全主题 + 生成器 + 校验器**的三层兜底：
用户要求"检查其他预设与主题库都具备这个能力，不再发生，并覆盖市面全部终端
（PC / 平板 / 各档手机）"。基准宽度定为 288px（320dp 手机正文下限）、328px
（360dp 主流），平板与 PC 只会更宽——以最窄档为下限即全终端覆盖。

### Fixed

- **摸鱼票据风 · 票据封面顶栏**：标签 `letter-spacing:4px` 与星级同行，288px 手机
  上必然把星级挤出边界。字距收到 2px、双侧加 `white-space:nowrap`，规矩写明
  {{头部标签}} ≤8 字符。
- **摸鱼票据风 · 票脚**：`VALID FOR ONE READ` + `ADMIT ONE 🎫` 两条合计约 330px，
  单行 `justify-between` 在窄屏必溢出。改成**确定性两行**（上行左对齐、下行右对齐）。
- **橄榄手记 · 头图卡眉题行**：标签 10px/字距 3px 与日期同行、卡片内宽仅 ~224px，
  与摸鱼绿眉题同病。字距收 2px、双侧 nowrap，规矩写明标签 ≤12 字符、日期用短格式。
- **橄榄手记 · 头图卡底部摘要条**：`flex-wrap` 挤压结构（X5 内核会把标签整个挤出
  边界，摸鱼绿实测同类问题）改成摘要一行 + 标签一行的确定性两行。
- **橄榄手记 · 三处分节条（组件 4/5/9）**：大字距标签与右侧文字同行，全部补
  nowrap 并写明字数上限。
- **全主题库小字大字距标签**（石墨极简 / 红白 / 留白禅意 / 摸鱼绿 / 票据 / 橄榄
  共 30+ 处）：`font-size ≤12px` 且 `letter-spacing ≥2px` 的标签统一补
  `white-space:nowrap`——都是单行语义标签，加 nowrap 零副作用。
- **石墨极简 / 红白 / 留白禅意 · 三列看点卡**：288px 下单卡内宽仅 ~60px，补
  "看点 ≤6 字、等高"硬规矩，并给出"改单列清单"的降级方案。
- **摸鱼绿 · toc 顶栏与 PART 小字、橄榄手记 PART/END 小字**：补 nowrap。

### Added

- **`validate_gzh_html.py` 窄屏体检**（warning 级，5 类自动拦截）：① 固定
  `width` > 288px（带 `max-width` 的插图豁免）；② 小字大字距未 nowrap；
  ③ 代码块用 `white-space:pre`；④ 较长代码行缺内联 nowrap（微信注入
  `white-space:normal` 会把横滑改回折行）；⑤ 有代码块但全文无 `overflow-x:auto`。
- **`tools/narrow_screen_check.js` + `tools/narrow_fixture.html`**：playwright
  多档宽度（288/320/328/342/375/390/414/428/768/1280）回归测量——页面
  scrollWidth 不得超视口、代码块横滑容器真可滚、列出撑宽页面的元素。
- **`theme-generator.md` 生成提示词新增 7.8 窄屏适配铁律** + 转换流程第 4 步
  窄屏复查：自定义主题从生成源头就按 288px 核算。
- **`SKILL.md` / `theme-index.md` 全局窄屏铁律**：眉题 nowrap 与字数上限、
  禁 flex-wrap 挤压改确定性两行、代码块横滑结构、固定宽度上限、交付前
  288px 自查——六套内置主题与未来主题全部适用。

### Verified

- `narrow_fixture.html`（票据封面 / 橄榄头图卡 / 三列看点卡 / 禅意目录 / 横滑
  代码块）与 `article.html` 各 10 档宽度全部 PASS：页面零横向溢出，代码块
  在 288px 可视 285px 内正常横滑（内容 625px / 568px）。
- `article.html` 跑增强后校验器 0 ERROR 0 WARNING；`component_lint.py` 0 ERROR。

## [0.7.0] - 2026-09-17

用户反馈"代码块的渲染方案还是不行"，要三件事：**色彩更丰富**、**横滑而不是折行**、
**所有预设与自定义预设都适用**。查下来是三个各自独立的毛病，第三个（缩进与对齐）
是这轮才暴露的：它一直被"配色不够"盖着，没人注意到代码块其实早就不缩进了。

### Fixed

- **代码块的缩进与列对齐会被 HTML 折叠掉**（`highlight_code.py`）。行首源码空格在
  渲染时整层消失 —— `def` 里的 4 空格缩进没了，读者看不出嵌套；连续源码空格被压成
  一个 —— 作者对齐到某一列的行尾注释全挤到代码后面。两处都改成写 `&nbsp;`：宽度与
  空格完全相同、且不被折叠。**没有改用 `white-space:pre`**：那会让 HTML 源码里 span
  前的缩进与行间换行被原样渲染成大左缩进 + 空行。也没用全角空格 `　`——它能缩进但
  对不齐列，因为它宽约 1.67 个半角字符，不是整 2 倍。
- **代码块在手机上折行**（`highlight_code.py`）。折行会把行尾注释甩到下一行开头，
  读者分不清它属于哪一句，同一段代码在不同机型折在不同位置。改成外层
  `overflow-x:auto` + 每行 `<p>` 内联 `white-space:nowrap`；内联是必需的 ——
  微信会往页面注入 `white-space:normal`，只有内联样式压得住它。超宽时顶栏右侧出
  「👉 左右滑动」提示（手机上滚动条是隐藏的），提示语与主题库横滑卡组一致。
  要折行仍可用 `--wrap`。
- **`theme_vars.MOBILE_CONTENT_W`：正文宽度基准从 677 改为 328**（新增）。677 是
  **桌面网页**的 max-width，手机上正文只有 328（360dp 机型 360 − 两侧留白 16×2）。
  这个数同时被插图与代码块用来判断"手机上放不放得下 / 字多小"，因此两边的结论都
  被高估了近一倍：插图那边此前报"正文里 7.8px / 25.7px"，实际是 3.8px / 12.4px；
  代码块那边会得出"75 列也放得下"（实际手机上要折两行）。常量收进 `theme_vars.py`
  一处，避免两个脚本各写一个数再漂开。
- **`validate_gzh_html.py` 新增代码空白体检**：抓"代码行以源码空格开头"与"代码行里
  有连续 2 个以上源码空格"，两种情况都给 WARNING 并说明改用 `&nbsp;`。判据反转义后
  比对，`&nbsp;`（U+00A0）不会误报（已用阴性对照验证：干净文件 0 警告，注入源码
  空格后两条都命中）。

### Changed

- **配色从"单一色相"改为"以主色色相为起点的色环"**（`highlight_code.py`）。关键词
  留在主色相本身（`+0°`，保住主题身份），函数 / 数字 / 字符串 / 内置 / 类型依次
  `+35° / +70° / +140° / +195° / +262°`；六个色相同处一个明度带（深色底
  `L≈0.68~0.78`）与一个饱和度带（`S≈0.45~0.62`）。**丰富来自色相，秩序来自明度与
  饱和度** —— 抽掉色相只看灰度，整块是平的。早期版本把全部 token 压在主色相 ±24°、
  饱和度 0.30~0.42 内，整块糊成一个色，这是本轮改掉的核心问题。
  要回那一版：`--scheme calm`。
- 关键词与类型名 **加粗**，结构在彩色里立得住；运算符与标点仍然不着色。
- **token 分类更细**：新增 `builtin`（小写内置函数/常量）与 `type`（大写类名/构造器）
  两类，并拆开此前混在一起的概念（Python 的 `print` 与 `MyClass`、bash 的 `$VAR`、
  SQL 的 `COUNT(` 归 `func`）。加粗 token 由 `BOLD` 常量统一声明。
- 深色 1a 顶栏底色**不再固定 `#0F172A`**，改为往主题色相偏的低饱和深色；代码块左侧
  加 3px 主题色竖条，让"这块是哪个主题的代码"一眼可辨。
- `highlight_code.py` 新增 `--check-widths`（只报哪几行会横滑）、`--scheme`、
  `--wrap`、`--no-hint`、`--content-width`、`--code-font-size`。

### Added

- **`tools/make_code_preview.py` 改为按手机正文宽度 328px 排版**，并新增
  `--scheme` 直通。此前用 760px 排版，会得出"75 列也放得下、不用滑"的错误结论 ——
  这个工具本身就是用来判"手机上长什么样"的，宽度必须跟手机一致。
- `references/common-components.md` 的 1a / 1b 示例改为**横滑版**，要点从 5 条扩到 7 条
  （新增 `&nbsp;`、横滑、主题竖条）；1a+/1b+ 节把"三条不突兀的约束"重写为
  "丰富来自色相、秩序来自明度与饱和度"，并补 `--scheme calm` / `--wrap` 的用法与
  "抽掉色相看灰度是否平"的判据。

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
- **`tools/make_code_preview.py`（新）**：出一页「同一段代码 × 多套主题」的着色对照页
  （零依赖）。`--show-palette` 打印的是色值，而色值看不出"扎不扎眼"——`#A1D9C7` 和
  `#D9B8A1` 谁刺眼只能眼睛看。主题列表取自 `theme-index.md`，所以自定义主题登记后
  会自动出现在页面里，顺带成为"新主题是否自动适配着色"的验收口。
  `--code-file` / `--lang` / `--style light` 可换代码与样式。

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
