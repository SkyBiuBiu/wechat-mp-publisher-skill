<div align="center">

# wechat-mp-publisher

**微信公众号图文发布工具 —— WorkBuddy 技能 / 独立 CLI**

用微信官方 API 把一篇带图带排版的图文推进草稿箱。<br>
排版、配图、上传、成稿全自动，你只剩最后点一下「发表」。<br>
风格有六条预设路线可选，发布前自动过一遍平台约束体检。

[![CI](https://github.com/SkyBiuBiu/wechat-mp-publisher/actions/workflows/ci.yml/badge.svg)](https://github.com/SkyBiuBiu/wechat-mp-publisher/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-0.2.0-orange.svg)](CHANGELOG.md)
[![Python](https://img.shields.io/badge/python-3.9%2B-3776AB.svg)](https://www.python.org/)

</div>

---

## 先说清楚能力边界

微信接口权限由**账号类型 + 认证状态**决定。这不是配置问题，是硬约束：

| 能力 | 可用范围 |
|---|---|
| 拿凭证 / 传正文图 / 传封面素材 / **建草稿** | ✅ 绝大多数账号可用。已在个人未认证订阅号上实测通过 |
| **API 正式发布**（`freepublish/submit`） | ❌ 仅认证账号。**个人主体无法做微信认证 → 永久不可用** |

**所以个人号的上限是**：脚本把图文做好、配好图、传好素材、丢进草稿箱，最后一步到后台手动点「发表」。省掉的是排版和上传，剩下的是那一下点击。

认证服务号则全链路可用，可以一条命令直接推送给粉丝。

> 详细权限矩阵、实测记录与官方文档口径的差异，见 [`references/wechat-api-reference.md`](references/wechat-api-reference.md)。

## 特性

- **六条风格路线** —— `工程橙 / 极简纸感 / 终端绿 / 杂志暖调 / 商务蓝 / 清单问答`，
  视觉（配色、字号、卡片样式）与写作（语气、开篇、段落、emoji）两层都由预设定义；
  16 个 token 可逐个覆盖，也能导出一份改。见 [`references/style-presets.md`](references/style-presets.md)
- **发布前约束体检** —— `preflight.py` 在本地把会翻车的地方拦掉：标题 32 字、作者 16 字、
  摘要 120 字、正文 2 万字符 / 1MB、图片体积与格式、外链图、会被剥离的 HTML 写法、
  排版问题、广告法与导流风险词。分 **P0 阻断 / P1 警告 / P2 建议** 三级，每项给处理办法
- **零第三方依赖** —— 所有脚本只用 Python 标准库，Windows / Linux 通用，拷过去就能跑
- **正文图片自动换链** —— 正文里写 `<img src="assets/xx.png">` 本地相对路径，脚本先传微信图床再替换 `src`（外链图会被微信静默过滤）
- **错误码中文翻译** —— 微信的 `errcode` 直接翻成人话和处置建议；`40164` 还会自动从 `errmsg` 里抠出被拒的 IP
- **白名单等待器** —— `watch_ip.py` 挂着轮询，白名单一生效自动接着建草稿，不用反复手点
- **安全默认值** —— 默认只建草稿，正式发布需显式二次确认；`delete` 必须给 `media_id` 才动手
- **仓库自检** —— `validate_skill.py` 一条命令查结构、语法、密钥泄露、文档引用、预设一致性

## 安装

### 作为 WorkBuddy 技能（推荐）

技能就是仓库本身，clone 到技能目录即完成安装：

```bash
# Linux / macOS
git clone https://github.com/SkyBiuBiu/wechat-mp-publisher.git \
          ~/.workbuddy/skills/wechat-mp-publisher
```

```powershell
# Windows PowerShell
git clone https://github.com/SkyBiuBiu/wechat-mp-publisher.git `
          "$env:USERPROFILE\.workbuddy\skills\wechat-mp-publisher"
```

装好后**开一个新会话**，技能列表在会话启动时加载。之后说「帮我把这篇文章发到公众号」就会自动触发。

更新技能：`cd ~/.workbuddy/skills/wechat-mp-publisher && git pull`

### 作为独立命令行工具

不需要 WorkBuddy，clone 到任意位置直接用：

```bash
git clone https://github.com/SkyBiuBiu/wechat-mp-publisher.git
cd wechat-mp-publisher
python scripts/publish.py --help
```

或从 [Releases](https://github.com/SkyBiuBiu/wechat-mp-publisher/releases) 下载 zip 解压。

## 快速开始

```bash
cd wechat-mp-publisher

# 1. 准备配置（只有 appid / appsecret 是必填）
mkdir -p work/assets
cp assets/templates/config.example.json work/config.json
#    编辑 work/config.json：填 appid、appsecret、title、digest，选一个 style.preset

# 2. 定风格，渲染出正文骨架
python scripts/apply_style.py --list                                    # 看六条路线
python scripts/apply_style.py --preset engineering-orange -o work/article.html
#    然后把 work/article.html 改成自己的内容

# 3. 体检：不连微信、不需要凭证，先查一遍字数/图片/排版/合规
python scripts/preflight.py -c work/config.json

# 4. 自检：验证凭证与 IP 白名单，不产生任何内容
python scripts/publish.py check -c work/config.json

# 5. 建草稿：图文进草稿箱，粉丝看不到（会先自动跑一次体检）
python scripts/publish.py draft -c work/config.json

# 6. 去 mp.weixin.qq.com → 内容与互动 → 草稿箱，人工确认后点「发表」
```

**凭证和 IP 白名单怎么弄**（这一步最容易卡） → 看 [`docs/manual.md`](docs/manual.md)
**风格怎么选、怎么自定义** → 看 [`references/style-presets.md`](references/style-presets.md)

### 风格路线

| 预设 | 适合 | 语气 |
|---|---|---|
| `engineering-orange` 工程橙（默认） | 实战教程、架构拆解、踩坑复盘 | 结论先行，像交接文档 |
| `minimal-paper` 极简纸感 | 观点随笔、方法论、行业观察 | 平静有判断 |
| `terminal-green` 终端绿 | 源码分析、CLI 教程、报错定位 | 直给可执行 |
| `magazine-warm` 杂志暖调 | 项目复盘、访谈、团队故事 | 有温度不说教 |
| `business-blue` 商务蓝 | 方案说明、选型对比、阶段汇报 | 客观有依据 |
| `checklist-qa` 清单问答 | FAQ、SOP、避坑清单 | 干脆，一问一答 |

自定义三级粒度：

```bash
# 微调几个 token（也可以写进 config.json 的 style.overrides）
python scripts/apply_style.py --set primary=#1f4e8c --set font_size=16px

# 导出一份自己的预设整份改
python scripts/apply_style.py --preset magazine-warm --dump my-style.json
python scripts/apply_style.py --style-file my-style.json -o work/article.html
```

### 体检怎么读

```bash
python scripts/preflight.py -c work/config.json
```

```
P0 · 阻断 · 1 项          ← 微信一定会报错或内容一定会坏，必须改
  [WX008] 正文超过 2 万字符
        现象：当前 20076 字符，超 76 字符（按 HTML 长度计，不是纯文本字数）
        处理：把代码块和图表改成 PNG 截图，或按章节拆成系列

P1 · 警告 · 2 项          ← 发得出去，但排版会塌 / 图会丢 / 合规有风险
P2 · 建议 · 3 项          ← 不影响发布，改了更好

统计：P0×1  P1×2  P2×3
      正文 19056 字符 [###########################-] 19056/20000 | 图片 4 张 | 封面 900x383
结果：不可发布 —— 先修 P0。
```

有 P0 时退出码为 1，`draft` 会就地停下（此时还没发任何请求）。
`--warn-only` 只报告不拦截，`--json` 给 CI 消费，`--no-compliance` 跳过合规词扫描。

49 条检查项的判定依据（**官方硬约束 / 实测行为 / 经验阈值**）见
[`references/wechat-api-reference.md`](references/wechat-api-reference.md) 第六节。

## 命令参考

```bash
python scripts/publish.py <子命令> [参数]
```

| 子命令 | 作用 |
|---|---|
| `check` | 验凭证 + 白名单，不发内容。**动手前先跑这个** |
| `preflight` | 只做发布前体检，不连微信、不需要凭证 |
| `draft` | 建草稿（推荐默认档）：体检 → 取 token → 正文图换链 → 传封面素材 → 建草稿 → 回查确认 |
| `publish` | 建草稿并立即正式发布。粉丝会收到推送，不可撤回 |
| `publish --media-id <id> -y` | 发布草稿箱里**已有**的一篇，不重复建稿 |
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
| `--no-compliance` | 体检时跳过广告法/导流/金融等合规词扫描 |
| `--warn-only` | 配合 `preflight`：有 P0 也返回 0 |
| `--json` | 配合 `preflight`：输出结构化 JSON |

辅助脚本：

| 脚本 | 作用 |
|---|---|
| `scripts/apply_style.py` | 风格渲染：`--list` / `--preset` / `--set` / `--style-file` / `--dump` |
| `scripts/preflight.py` | 发布前体检：P0/P1/P2 三级清单，`--json` / `--warn-only` / `--no-compliance` |
| `scripts/watch_ip.py` | 轮询等白名单生效，通了自动建草稿。`-i 秒` 调间隔，`-m 次数` 限次，`--no-preflight` 透传 |
| `scripts/make_assets.py` | 生成封面（900×383）和正文插图，需 `pillow`，`--title/--subtitle/--date` 可配 |
| `scripts/validate_skill.py` | 仓库自检：结构 / frontmatter / 版本 / 语法 / 密钥 / 引用 / 预设一致性 |
| `scripts/build_zip.py` | 打分发 zip 到 `dist/`，自动排除密钥与本机状态 |

## 配置项

`config.json`（由 `assets/templates/config.example.json` 复制而来）：

| 字段 | 必填 | 说明 |
|---|---|---|
| `appid` | ✅ | 微信开发者平台 → 公众号 → 基础信息 → 开发密钥 |
| `appsecret` | ✅ | 同上，**只显示一次**，当场存好 |
| `author` | | 作者，上限 16 字 |
| `style.preset` | | 风格路线 id，不填用 `engineering-orange` |
| `style.overrides` | | 只写要改的 token，如 `{"primary": "#1f4e8c"}`，其余继承预设 |
| `article.title` | ✅ | 标题，上限 32 字 |
| `article.digest` | | 摘要，上限 120 字；留空自动抓正文前 54 字 |
| `article.content_file` | ✅ | 正文 HTML，路径相对配置文件所在目录 |
| `article.cover_file` | ✅ | 封面图，走永久素材接口，建议 900×383 |
| `article.content_source_url` | | 文末「阅读原文」跳转地址，留空不显示 |
| `need_open_comment` | | `1` 开评论 |
| `only_fans_can_comment` | | `1` 仅粉丝可评 |

凭证也可以用环境变量提供，不写配置文件：`WECHAT_MP_APPID` / `WECHAT_MP_APPSECRET`。

## 目录结构

```
wechat-mp-publisher/
├── SKILL.md                        # WorkBuddy 技能入口（触发条件、风格、工作流、排障）
├── README.md                       # 本文件
├── docs/manual.md                  # 完整操作手册：后台路径、白名单排查、报错表
├── CHANGELOG.md                    # 版本变更记录
├── CONTRIBUTING.md                 # 开发约定与发版流程
├── LICENSE                         # MIT
├── VERSION                         # 当前版本号
├── scripts/
│   ├── publish.py                  # 主脚本（零依赖）
│   ├── preflight.py                # 发布前体检：约束 / 排版 / 合规
│   ├── apply_style.py              # 风格渲染：预设 token → 正文骨架
│   ├── watch_ip.py                 # 白名单生效轮询
│   ├── make_assets.py              # 封面 / 配图生成（需 pillow）
│   ├── validate_skill.py           # 仓库自检
│   └── build_zip.py                # 分发包打包
├── references/
│   ├── wechat-api-reference.md     # 接口字段约束、权限矩阵、错误码全表、预检口径
│   └── style-presets.md            # 风格路线、token 字典、自定义方式
├── assets/
│   ├── styles/                     # 六条风格预设（JSON）
│   │   ├── engineering-orange.json
│   │   ├── minimal-paper.json
│   │   ├── terminal-green.json
│   │   ├── magazine-warm.json
│   │   ├── business-blue.json
│   │   └── checklist-qa.json
│   └── templates/
│       ├── article.template.html   # 带 {{token}} 占位符的正文积木库（渲染用）
│       ├── article.html            # 全内联样式的正文样板（手工改）
│       └── config.example.json     # 配置模板
└── .github/                        # CI、Release 工作流、Issue / PR 模板
```

## 常见问题

**`40164` 不在白名单** —— 加调用方**公网 IPv4** 出口地址。`curl ifconfig.me` 可能返回 IPv6，微信不认，用 `curl -4 ipv4.icanhazip.com`。改完通常要**管理员扫码确认**，且有生效延迟。挂着 `watch_ip.py` 等，别反复手点。

**`48001` 接口未授权** —— 账号类型限制，重试无意义。个人号 `freepublish` 永久不可用，转后台手动发布。

**`40001` 之前是好的** —— token 被别处刷新导致本地缓存失效，`python scripts/publish.py token -f`。

**正文图片不显示** —— 用了外链图。改成 `<img src="assets/xx.png">` 的本地相对路径，脚本会自动换链。

**提示正文超过 2 万字符** —— 注意**按 HTML 长度算，不是纯文本字数**。代码块多、标签多的文章，纯文本 4000 字也可能撞上限。最有效的压降手段是把代码块和图表截图成 PNG（单块从数千字符压到百余字符），或按章节拆成系列。详见 `SKILL.md` 第十节。

**体检报 WX012 说图片不存在** —— 模板 `article.template.html` 第 8 块引用了示例图 `assets/diagram.png`。放上自己的图，或把那一块整段删掉。

**体检的合规词提示是不是判我违规** —— 不是。`WX114` 是风险提示，只说明这句话需要人工过一眼（「唯一标识」这类技术术语会被误报）。它不替代人工审核，用 `--no-compliance` 可以整体跳过。

**发布提交成功但后台看不到** —— `errcode=0` 只代表任务提交成功，发布有延迟，最终结果走微信服务端事件推送。

完整排查清单和错误码表 → [`docs/manual.md`](docs/manual.md) 与 [`references/wechat-api-reference.md`](references/wechat-api-reference.md)

## 安全

- `config.json` 和 `.token_cache.json` 含密钥，**已在 `.gitignore` 中**。CI 里还挂了 gitleaks 做二次兜底。
- AppSecret 在微信平台**不存储、不显示**，忘了只能重置；**重置会让旧密钥立即失效**。
- 若 AppSecret 曾在对话、日志或截图中明文出现过，正式使用前到开发者平台重置。
- 脚本默认只建草稿。正式发布不可撤回，执行前需明确知情。

## 迭代与发版

本项目遵循[语义化版本](https://semver.org/lang/zh-CN/)，变更记录见 [`CHANGELOG.md`](CHANGELOG.md)。

```bash
# 改完先自检
python scripts/validate_skill.py

# 本地验证打包链路
python scripts/build_zip.py

# 发版：改 VERSION 与 CHANGELOG → 打 tag → 推
git commit -am "chore(release): v0.2.0"
git tag -a v0.2.0 -m "v0.2.0"
git push origin main --tags
```

推 tag 会触发 `release.yml`：先跑自检、校验 tag 与 `VERSION` 一致、打包 zip、自动挂到 Release。`ci.yml` 在每次 push / PR 时跑自检 + gitleaks + 打包验证。

开发约定见 [`CONTRIBUTING.md`](CONTRIBUTING.md)。

## License

[MIT](LICENSE) © 2026 Sky (SkyBiuBiu)
