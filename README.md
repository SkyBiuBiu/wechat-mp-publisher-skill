<div align="center">

# wechat-mp-publisher-skill

**微信公众号图文发布工具**

把一篇带图带排版的 HTML 正文推进公众号草稿箱。排版、配图、上传、成稿一条龙，剩下最后点一下「发表」的功夫给你。六种风格预设可选，发布前自动过一遍平台约束体检，该拦的坑提前帮你拦掉。

[![CI](https://github.com/SkyBiuBiu/wechat-mp-publisher-skill/actions/workflows/ci.yml/badge.svg)](https://github.com/SkyBiuBiu/wechat-mp-publisher-skill/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Version](https://img.shields.io/github/v/tag/SkyBiuBiu/wechat-mp-publisher-skill)](CHANGELOG.md)

</div>

---

## 能做什么、不能做什么

微信接口权限由账号类型和认证状态决定，这不是配置能绕过的：

| 能力 | 可用范围 |
|---|---|
| 取凭证 / 传正文图 / 传封面素材 / **建草稿** | ✅ 绝大多数账号可用，个人未认证订阅号实测通过 |
| **API 正式发布**（`freepublish/submit`） | ❌ 仅认证账号。个人主体做不了微信认证，这个口子永久关闭 |

所以个人号的实际流程是：脚本把图文做好、图配好、素材传好、丢进草稿箱，你去后台点一下「发表」。排版和上传省掉了，剩下那一下点击。

认证服务号则可以一条命令直接推送给粉丝。

权限矩阵、实测记录和官方文档口径的差异见 [`references/wechat-api-reference.md`](references/wechat-api-reference.md)。

## 特点

- **六种视觉预设**：工程橙 / 极简纸感 / 终端绿 / 杂志暖调 / 商务蓝 / 清单问答。预设只定义视觉（配色、字号、卡片样式、代码高亮），17 个 token 可以单独覆盖，也可以导出整份自己改 —— 文章写什么、分几节、怎么收尾，预设不管。详见 [`references/style-presets.md`](references/style-presets.md)。
- **发布前体检**：`preflight.py` 在本地把会翻车的地方拦掉——标题 32 字、作者 16 字、摘要 120 字、正文 2 万字符 / 1MB、图片体积格式、外链图、会被编辑器剥掉的 HTML 写法、排版问题、广告法和导流风险词。分 P0 阻断 / P1 警告 / P2 建议三级，每条都给处理办法。
- **图片清晰度把关**：发布前自动查——封面宽小于 1200px、正文图宽小于 750px 会直接提示会糊；`make_assets.py` 生成的封面和配图本身就是 2x 高清（1800×766）。
- **mermaid 高清渲染**：正文里写 ```mermaid 围栏，发布前渲染成 PNG（本地 mmdc 优先，mermaid.ink 兜底）。默认 `scale=3`，输出约 3600px 宽，手机上看不糊。
- **代码块可复制**：代码围栏重建为内联样式高亮卡片，不转图片，手机长按即可复制。卡片结构做了抗清洗处理，在公众号后台编辑器里保存也不会丢样式。
- **零第三方依赖**：全部脚本只用 Python 标准库，Windows / Linux 通用，clone 下来就能跑。
- **正文图片自动换链**：正文写 `<img src="assets/xx.png">` 本地相对路径，脚本先传微信图床再替换 `src`。外链图会被微信静默过滤，别用。
- **错误码翻成人话**：微信的 `errcode` 直接翻译成处置建议，`40164` 还会自动从报错里抠出被拒的 IP。
- **白名单等待器**：`watch_ip.py` 挂着轮询，白名单一生效自动接着建草稿，不用反复手点。
- **默认只建草稿**：正式发布需要显式确认；删除草稿必须给 `media_id`，防手滑。

## 安装

### 作为技能

仓库本身就是技能，clone 到技能目录即可：

```bash
# Linux / macOS
git clone https://github.com/SkyBiuBiu/wechat-mp-publisher-skill.git \
          ~/.workbuddy/skills/wechat-mp-publisher-skill
```

```powershell
# Windows PowerShell
git clone https://github.com/SkyBiuBiu/wechat-mp-publisher-skill.git `
          "$env:USERPROFILE\.workbuddy\skills\wechat-mp-publisher-skill"
```

装好后开一个新会话（技能列表在会话启动时加载），说「帮我把这篇文章发到公众号」就会触发。

更新：`cd ~/.workbuddy/skills/wechat-mp-publisher-skill && git pull`

### 作为命令行工具

不需要技能宿主，clone 到任意位置直接用：

```bash
git clone https://github.com/SkyBiuBiu/wechat-mp-publisher-skill.git
cd wechat-mp-publisher-skill
python scripts/publish.py --help
```

也可以从 [Releases](https://github.com/SkyBiuBiu/wechat-mp-publisher-skill/releases) 下载 zip 解压。

## 快速开始

```bash
cd wechat-mp-publisher-skill

# 1. 准备配置（必填的只有 appid 和 appsecret）
mkdir -p work/assets
cp assets/templates/config.example.json work/config.json
#    编辑 work/config.json：填 appid、appsecret、title、digest，选一个 style.preset

# 2. 定风格，渲染出正文骨架
python scripts/apply_style.py --list                                    # 看六条路线
python scripts/apply_style.py --preset engineering-orange -o work/article.html
#    然后把 work/article.html 改成自己的内容（mermaid 写 ```mermaid 围栏、代码写 ``` 围栏即可）

# 3. 体检：不连微信、不需要凭证，先查一遍字数/图片/排版/合规
python scripts/preflight.py -c work/config.json

# 4. 自检：验证凭证与 IP 白名单，不发任何内容
python scripts/publish.py check -c work/config.json

# 5. 建草稿：图文进草稿箱，粉丝看不到（会先自动跑增强 + 体检）
python scripts/publish.py draft -c work/config.json

# 6. 去 mp.weixin.qq.com → 内容与互动 → 草稿箱，人工确认后点「发表」
```

凭证和 IP 白名单怎么弄（最容易卡的一步）→ [`docs/manual.md`](docs/manual.md)
风格怎么选、怎么自定义 → [`references/style-presets.md`](references/style-presets.md)

### 风格预设

| 预设 | 视觉观感 | 常配题材（参考） |
|---|---|---|
| `engineering-orange` 工程橙（默认） | 暖调橙 + 深色代码块，长文耐读 | 实战教程、架构拆解、踩坑复盘 |
| `minimal-paper` 极简纸感 | 无彩色块，留白与细横线分层 | 观点随笔、方法论、行业观察 |
| `terminal-green` 终端绿 | 深底绿 + 终端感代码块 | 源码分析、CLI 教程、报错定位 |
| `magazine-warm` 杂志暖调 | 暖色底、大引文、圆角卡片 | 项目复盘、访谈、团队故事 |
| `business-blue` 商务蓝 | 冷调蓝 + 细线分隔，信息密度高 | 方案说明、选型对比、阶段汇报 |
| `checklist-qa` 清单问答 | 浅底高对比，块状分隔清晰 | FAQ、SOP、避坑清单 |

自定义分三级：

```bash
# 微调几个 token（也可以写进 config.json 的 style.overrides）
python scripts/apply_style.py --set primary=#1f4e8c --set font_size=16px

# 导出一份自己的预设整份改
python scripts/apply_style.py --preset magazine-warm --dump my-style.json
python scripts/apply_style.py --style-file my-style.json -o work/article.html
```

### 体检输出长什么样

```bash
python scripts/preflight.py -c work/config.json
```

```
P0 · 阻断 · 1 项        ← 微信一定会报错或内容一定会坏，必须改
  [WX008] 正文超过 2 万字符
    现象：当前 20076 字符，超 76 字符（按 HTML 长度计，不是纯文本字数）
    处理：把代码块和图表改成 PNG 截图，或按章节拆成系列

P1 · 警告 · 2 项        ← 发得出去，但排版会塌 / 图会丢 / 合规有风险
P2 · 建议 · 3 项        ← 不影响发布，改了更好

统计：P0×1  P1×2  P2×3  ·  正文 19056/20000 字符  ·  图片 4 张  ·  封面 1800×766
结果：不可发布 —— 先修 P0。
```

有 P0 时退出码为 1，`draft` 会就地停下（此时还没发任何请求）。`--warn-only` 只报告不拦截，`--json` 给 CI 用，`--no-compliance` 跳过合规词扫描。

52 条检查项的判定依据（官方硬约束 / 实测行为 / 经验阈值三类）见 [`references/wechat-api-reference.md`](references/wechat-api-reference.md) 第六节。

## 命令参考

```bash
python scripts/publish.py <子命令> [参数]
```

| 子命令 | 作用 |
|---|---|
| `check` | 验凭证 + 白名单，不发内容。动手前先跑这个 |
| `preflight` | 只做发布前体检，不连微信、不需要凭证 |
| `enhance` | 内容增强：mermaid 渲染成 PNG、代码块重建为高亮卡片，不连微信 |
| `draft` | 建草稿（推荐默认档）：增强+体检 → 取 token → 正文图换链 → 传封面素材 → 建草稿 → 回查确认 |
| `publish` | 建草稿并立即正式发布。粉丝会收到推送，不可撤回 |
| `publish --media-id <id> -y` | 发布草稿箱里已有的一篇，不重复建稿 |
| `list` | 列出草稿箱 |
| `delete --media-id <id> -y` | 删除指定草稿（破坏性，必须显式给 id） |
| `token -f` | 强制刷新 access_token（遇到 `40001` 时用） |

通用参数：

| 参数 | 说明 |
|---|---|
| `-c, --config <路径>` | 配置文件。默认按「当前目录 → 技能目录」查找 `config.json` |
| `-f, --force` | 忽略本地 token 缓存，强制重新获取 |
| `-y, --yes` | 跳过交互确认（仅脚本化场景使用） |
| `--no-preflight` | `draft` 前不跑体检（不建议） |
| `--no-enhance` | `draft` 前不做内容增强 |
| `--no-compliance` | 体检时跳过广告法/导流/金融等合规词扫描 |
| `--warn-only` | 配合 `preflight`：有 P0 也返回 0 |
| `--json` | 配合 `preflight`：输出结构化 JSON |

辅助脚本：

| 脚本 | 作用 |
|---|---|
| `scripts/apply_style.py` | 风格渲染：`--list` / `--preset` / `--set` / `--style-file` / `--dump` |
| `scripts/preflight.py` | 发布前体检：P0/P1/P2 三级清单，`--json` / `--warn-only` / `--no-compliance` |
| `scripts/enhance_content.py` | 内容增强：mermaid → PNG（mmdc / mermaid.ink），代码块 → 高亮卡片，`mermaid`/`code` 子命令、`--dry-run` |
| `scripts/watch_ip.py` | 轮询等白名单生效，通了自动建草稿。`-i 秒` 调间隔，`-m 次数` 限次，`--no-preflight` 透传 |
| `scripts/make_assets.py` | 生成 2x 高清封面（1800×766）和正文插图，需 `pillow`，`--title/--subtitle/--date` 可配 |
| `scripts/validate_skill.py` | 仓库自检：结构 / frontmatter / 版本 / 语法 / 密钥 / 引用 / 预设一致性 |
| `scripts/build_zip.py` | 打分发 zip 到 `dist/`，自动排除密钥与本机状态 |

## 配置项

`config.json` 由 `assets/templates/config.example.json` 复制而来：

| 字段 | 必填 | 说明 |
|---|---|---|
| `appid` | ✅ | 微信开发者平台 → 公众号 → 基础信息 → 开发密钥 |
| `appsecret` | ✅ | 同上，只显示一次，当场存好 |
| `author` | | 作者，上限 16 字 |
| `style.preset` | | 视觉风格 id，不填用 `engineering-orange` |
| `style.overrides` | | 只写要改的 token，如 `{"primary": "#1f4e8c"}`，其余继承预设 |
| `mermaid.remote` | | mermaid 渲染走 mermaid.ink 在线服务（默认 `true`）；涉密图表装 mmdc 后设 `false` |
| `mermaid.scale` | | 渲染倍率，默认 `3`（与 width 共同决定输出像素，越高越清晰） |
| `mermaid.width` | | 渲染基准宽度，默认 `1200`（输出宽 ≈ scale × width） |
| `mermaid.dir` | | 渲染产物目录，默认 `assets` |
| `article.title` | ✅ | 标题，上限 32 字 |
| `article.digest` | | 摘要，上限 120 字；留空自动抓正文前 54 字 |
| `article.content_file` | ✅ | 正文 HTML，路径相对配置文件所在目录 |
| `article.cover_file` | ✅ | 封面图，走永久素材接口，建议 1800×766（2.35:1） |
| `article.content_source_url` | | 文末「阅读原文」跳转地址，留空不显示 |
| `need_open_comment` | | `1` 开评论 |
| `only_fans_can_comment` | | `1` 仅粉丝可评 |

凭证也可以不写配置文件，用环境变量：`WECHAT_MP_APPID` / `WECHAT_MP_APPSECRET`。

## 目录结构

```
wechat-mp-publisher-skill/
├── SKILL.md                        # 技能入口（触发条件、风格、工作流、排障）
├── README.md                       # 本文件
├── docs/manual.md                  # 完整操作手册：后台路径、白名单排查、报错表
├── CHANGELOG.md                    # 版本变更记录
├── CONTRIBUTING.md                 # 开发约定与发版流程
├── LICENSE                         # MIT
├── VERSION                         # 当前版本号
├── scripts/
│   ├── publish.py                  # 主脚本（零依赖）
│   ├── preflight.py                # 发布前体检：约束 / 排版 / 合规 / 图片清晰度
│   ├── enhance_content.py          # 内容增强：mermaid 高清渲染 + 代码块重建
│   ├── apply_style.py              # 风格渲染：预设 token → 正文骨架
│   ├── watch_ip.py                 # 白名单生效轮询
│   ├── make_assets.py              # 2x 高清封面 / 配图生成（需 pillow）
│   ├── validate_skill.py           # 仓库自检
│   └── build_zip.py                # 分发包打包
├── references/
│   ├── wechat-api-reference.md     # 接口字段约束、权限矩阵、错误码全表、预检口径
│   └── style-presets.md            # 视觉风格、token 字典、自定义方式
├── assets/
│   ├── styles/                     # 六条风格预设（JSON）
│   └── templates/
│       ├── article.template.html   # 带 {{token}} 占位符的正文积木库（渲染用）
│       ├── article.html            # 全内联样式的正文样板（手工改）
│       └── config.example.json     # 配置模板
└── .github/                        # CI、Release 工作流、Issue / PR 模板
```

## 常见问题

**`40164` 不在白名单** —— 加调用方公网 IPv4 出口地址。`curl ifconfig.me` 可能返回 IPv6，微信不认，用 `curl -4 ipv4.icanhazip.com`。改完通常要管理员扫码确认，且有生效延迟。挂着 `watch_ip.py` 等，别反复手点。

**`48001` 接口未授权** —— 账号类型限制，重试无意义。个人号 `freepublish` 永久不可用，转后台手动发布。

**`40001` 之前是好的** —— token 被别处刷新导致本地缓存失效，`python scripts/publish.py token -f`。

**正文图片不显示** —— 用了外链图。改成 `<img src="assets/xx.png">` 本地相对路径，脚本会自动换链。

**图片在手机上发糊** —— 图本身分辨率不足。正文图建议至少 1354px 宽（正文区约 677px ×2 屏），封面建议 1800×766。体检会用 WX116 / WX218 拦掉低于门槛的图；mermaid 默认 `scale=3`，一般不会糊。

**提示正文超过 2 万字符** —— 注意是按 HTML 长度算，不是纯文本字数。代码块多、标签多的文章，纯文本 4000 字也可能撞上限。最有效的压降手段是让 `enhance_content.py` 把代码块重建为高亮卡片、mermaid 渲染成 PNG，或者按章节拆成系列。详见 `SKILL.md` 第十节。

**体检报 WX012 说图片不存在** —— 模板引用了示例图 `assets/diagram.png`。放上自己的图，或把那一块整段删掉。

**体检的合规词提示是不是判我违规** —— 不是。`WX114` 是风险提示，只说明这句话需要人工过一眼（「唯一标识」这类技术术语会被误报）。它不替代人工审核，用 `--no-compliance` 可以整体跳过。

**发布提交成功但后台看不到** —— `errcode=0` 只代表任务提交成功，发布有延迟，最终结果走微信服务端事件推送。

完整排查清单和错误码表 → [`docs/manual.md`](docs/manual.md) 与 [`references/wechat-api-reference.md`](references/wechat-api-reference.md)

## 安全

- `config.json` 和 `.token_cache.json` 含密钥，已在 `.gitignore` 里，CI 还有 gitleaks 兜底。
- AppSecret 在微信平台不存储、不显示，忘了只能重置，重置会让旧密钥立即失效。
- 如果 AppSecret 曾在对话、日志或截图里明文出现过，正式使用前到开发者平台重置。
- 脚本默认只建草稿。正式发布不可撤回，执行前需明确知情。

## 发版

遵循[语义化版本](https://semver.org/lang/zh-CN/)，变更记录在 [`CHANGELOG.md`](CHANGELOG.md)。

```bash
# 改完先自检
python scripts/validate_skill.py

# 本地验证打包链路
python scripts/build_zip.py

# 发版：改 VERSION 与 CHANGELOG → 打 tag → 推
git commit -am "chore(release): v0.3.x"
git tag -a v0.3.x -m "v0.3.x"
git push origin main --tags
```

推 tag 会触发 `release.yml`：跑自检、校验 tag 与 `VERSION` 一致、打包 zip、挂到 Release。`ci.yml` 在每次 push / PR 时跑自检 + gitleaks + 打包验证。

开发约定见 [`CONTRIBUTING.md`](CONTRIBUTING.md)。

## License

[MIT](LICENSE) © 2026 Sky (SkyBiuBiu)
