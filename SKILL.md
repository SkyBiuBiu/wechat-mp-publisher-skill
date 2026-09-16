---
name: wechat-mp-publisher-skill
description: 微信公众号图文发布技能。当用户要求「发公众号」「发一篇公众号文章/推文」「推到公众号草稿箱」「公众号排版发布」「把这篇发到微信公众号」时使用。支持六种可选的图文风格路线（工程橙/极简纸感/终端绿/杂志暖调/商务蓝/清单问答）与自定义 token；mermaid 图渲染成 PNG、代码围栏重建为可长按复制的内联高亮卡片（不转图片），发布前自动做平台约束体检（标题 32 字、作者 16 字、摘要 120 字、正文 2 万字符、图片体积与格式、外链图、排版与合规风险词），再通过微信官方 API 完成 access_token 获取、正文图片上传换链、封面永久素材上传、图文草稿创建，并可选正式发布。内置错误码中文翻译、IP 白名单诊断与白名单生效轮询。
agent_created: true
---

# 微信公众号图文发布

用微信官方 API 把一篇带图带排版的图文推进公众号草稿箱，可选继续正式发布。
风格可预设、可自定义；发布前先过一遍平台约束体检。

## 一、能力边界（先判断可行性，再动手）

微信接口权限由**账号类型 + 认证状态**决定，这是硬约束：

| 能力 | 可用范围 |
|---|---|
| 拿凭证 / 上传正文图片 / 上传封面素材 / 建草稿 | ✅ 绝大多数账号，**已实测个人未认证订阅号可用** |
| API 正式发布（freepublish） | ❌ 仅认证账号。**个人主体无法微信认证 → 永久不可用** |

**行动规则**：

- 个人主体账号 → 只做到建草稿，最后一步引导用户到 mp 后台草稿箱手动点「发表」。**不要反复重试发布**，`48001` 是账号类型限制，重试无意义。
- 企业/组织主体已认证账号 → 全链路可用，可执行发布。
- 无法判断账号类型时，先跑 `check`，再跑 `draft`，用实际报错决定。

详细权限矩阵、实测记录与接口字段约束见 `references/wechat-api-reference.md`。

## 二、前置条件（缺一项就会失败，按顺序确认）

1. **AppID / AppSecret**：在**微信开发者平台** `developers.weixin.qq.com/platform` 获取，不在 mp 后台。
   扫码登录 → 我的业务与服务 → 我的业务 → 公众号 → 基础信息 → 开发密钥。
   AppSecret 默认隐藏，点「启用」后**只显示一次**。
   → 向用户索要凭证时，说明这条路径，并提醒启用可能需要实名/认证。
2. **IP 白名单**：必须包含调用方的**公网 IPv4 出口 IP**。
   - 取 IPv4：`curl -4 ipv4.icanhazip.com`（注意 `curl ifconfig.me` 可能返回 IPv6，微信不认）。
   - 配置入口：微信开发者平台 → 公众号详情页 → API IP白名单。
   - 改完通常要**管理员扫码确认**，且**有生效延迟**。
   - 报 40164 时，直接读 `errmsg` 里的 IP，脚本也会自动提取提示。
3. **文章素材**：正文 HTML 文件 + 封面图。正文里的图片写本地相对路径，脚本自动上传换链。

## 三、风格路线（先定调，再写正文）

正文风格分**视觉**和**写作**两层，由 `assets/styles/*.json` 的六条路线预设定义。**写正文之前先把风格选定**，否则写完再改要比对重写便宜得多。

| 预设 id | 名字 | 适合 | 语气 |
|---|---|---|---|
| `engineering-orange` | 工程橙（默认） | 实战教程、架构拆解、踩坑复盘 | 结论先行，像交接文档 |
| `minimal-paper` | 极简纸感 | 观点随笔、方法论、行业观察 | 平静有判断，有观点但不咄咄逼人 |
| `terminal-green` | 终端绿 | 源码分析、CLI 教程、报错定位 | 直给可执行，结论后面跟命令 |
| `magazine-warm` | 杂志暖调 | 项目复盘、访谈、团队故事 | 有温度不说教，第一人称 |
| `business-blue` | 商务蓝 | 方案说明、选型对比、阶段汇报 | 客观有依据，判断后面跟数据 |
| `checklist-qa` | 清单问答 | FAQ、SOP、避坑清单、排错速查 | 干脆，一问一答 |

**选风格的做法**：

- 用户没指定 → 按题材从表里选一条，**在回复里说明选的是哪条、为什么**，不要默默用默认。
- 用户指定了 → 直接用；指定的是风格描述（如「专业一点」「轻松点」）→ 从上表挑最接近的，说明理由。
- 用户不满意 → 换一条重渲染即可，视觉是 token 驱动的，不需要重写内容。

**自定义**（三级粒度，详见 `references/style-presets.md`）：

```bash
# 1. 微调几个 token：颜色用 #rgb/#rrggbb，尺寸用数字+单位
python <skill>/scripts/apply_style.py --preset engineering-orange --set primary=#1f4e8c
#    或写进 config.json 长期生效： "style": {"preset": "...", "overrides": {"primary": "#1f4e8c"}}

# 2. 导出一份自己的预设，整份改
python <skill>/scripts/apply_style.py --preset magazine-warm --dump my-style.json
python <skill>/scripts/apply_style.py --style-file my-style.json -o article.html

# 3. 只改写作约束不动视觉：在指令里说清语气要求，视觉仍由预设渲染
```

**写正文时的执行要求**（这两层必须匹配，只做一层会拧）：

1. 读 `assets/styles/<预设>.json` 的 `writing` 段，按 `tone` / `opening` / `paragraph` / `emoji` / `closing` / `avoid` 六个字段组织文字。
2. 用 `apply_style.py` 渲染出骨架，再把内容填进去 —— 骨架里的块（要点卡片、表格、代码块、问答块、步骤条）按 `best_for` 的题材挑用，不用的整段删掉。
3. 预设里禁用 emoji 的路线，正文里一个都不要出现（`preflight.py` 会报 `WX215`）。

## 四、平台约束（体检脚本会自动查，这里给全貌）

写内容时最容易翻车的是这几条，数值都是官方原文口径（完整表见 `references/wechat-api-reference.md`）：

| 约束项 | 上限 | 超了会怎样 |
|---|---|---|
| 标题 | 32 字 | 微信直接报错 |
| 作者 | 16 字 | 直接报错 |
| 摘要 | 120 字（留空自动抓正文前 54 字） | 直接报错 |
| 正文 | **少于 2 万字符**（按 HTML 长度算）、小于 1MB | 直接报错 |
| 原文链接 | 1KB | 直接报错 |
| 正文图片 | 仅 jpg/png，单张 < 1MB | 报 40005 / 40009 |
| 封面 | 必填，bmp/png/jpg/gif，< 10MB | 报 40007 |
| 外链图 | **不允许**，会被静默过滤 | 不报错，图直接没了 |
| `<style>` / `class` / JS | 会被剥离 | 不报错，样式全丢 |

> **图片清晰度体检**（发布前自动查）：封面宽度 <1200px 报 P1（会糊）、
> <1800px 报 P2（未达 2x 高清，建议 1800×766）；正文图片宽度 <750px 报 P1（会糊，
> 正文区约 677px 宽、2x 屏需约 1354px）。`make_assets.py` 生成的就是 2x 高清版，
> mermaid 渲染默认 scale=3 保证手机上锐利。

> **正文字符数按 HTML 长度算，不是纯文本字数**。这是最容易误判的一条：代码块多、标签多的文章，纯文本才 4000 字也可能撞上 2 万字符上限。突破手段：mermaid 渲染成 PNG、代码块交给 enhance_content.py 重建（见第四步），仍超就拆篇（见第十节）。

## 五、工作流程

### Step 1：准备工作目录

在用户的工作目录下建发布目录，从技能模板复制骨架：

```bash
mkdir -p wechat-publish/assets
cp <skill>/assets/templates/config.example.json wechat-publish/config.json
# 编辑 config.json 填 appid / appsecret / title / digest / style.preset
```

可选：用 `scripts/make_assets.py` 生成封面和插图（需 pillow），默认封面 900×383。

### Step 2：定风格、渲染正文骨架

```bash
python <skill>/scripts/apply_style.py --list                       # 看六条路线
python <skill>/scripts/apply_style.py -o wechat-publish/article.html
#   不带 --preset 时会自动读 config.json 的 style 段；也可显式 --preset terminal-green
```

渲染顺带把封面配色建议定下来：封面主色跟 `primary` 保持一致，成套感最强。

### Step 3：写正文

- **全部使用内联样式**，`<style>` 与 `class` 会被公众号编辑器剥离。
- 正文图片写成本地相对路径（如 `assets/diagram.png`），脚本会先上传到微信图床再替换 `src`。
- **不要用外部图片链接**，微信会静默过滤外链图。
- 不要用 `h1`~`h6`（样式被平台覆盖），小标题用加粗 `<p>`。
- 按第三节的写作约束组织文字，对照所选预设的 `writing` 段自查一遍。
- **mermaid 直接写 ```mermaid 围栏**：发布前 `enhance_content.py` 渲染成 PNG 替换（公众号剥 JS 与 SVG 文字，PNG 是唯一稳妥形态）。
- **代码直接写 ```python 等围栏**或 `<pre><code>`：会被重建为内联样式高亮卡片，手机长按可复制——不要把代码转成图片。
- 详细标签约束见 `references/wechat-api-reference.md` 第五节。

### Step 4：内容增强 + 发布前体检

```bash
# mermaid 围栏渲染成 PNG、代码围栏/<pre><code> 重建为内联高亮卡片（就地更新，自动留 .bak）
python <skill>/scripts/enhance_content.py -c wechat-publish/config.json

# 体检（draft 也会自动执行这两步）
python <skill>/scripts/preflight.py -c wechat-publish/config.json
```

增强说明：本地装了 mmdc（`npm i -g @mermaid-js/mermaid-cli`）就走本地渲染；
没装且 config 未关 `mermaid.remote` 时走 mermaid.ink 远程渲染（图表内容会发给
第三方服务，涉密图表别开）。两者都不可用时 mermaid 源码原样保留，体检报 WX216。

不连微信、不需要凭证，纯本地检查，输出 **P0 阻断 / P1 警告 / P2 建议** 三级清单，每项带「现象 + 处理」。

- 有 P0 → 退出码 1，**先修掉再往下走**。P0 项是「微信一定会报错或内容一定会坏」的。
- P1/P2 → 退出码 0，逐条判断。`--warn-only` 可强制返回 0，`--json` 给 CI 用，`--no-compliance` 跳过合规词扫描。
- 体检同时会校验 `style.preset` 是否存在、`style.overrides` 的 token 名是否合法。

### Step 5：建草稿

```bash
python <skill>/scripts/publish.py draft -c wechat-publish/config.json
```

按顺序执行：**跑体检 → 取 token → 正文图上传换链 → 封面传永久素材 → 建草稿 → 回查确认**。
成功标志：输出 `draft media_id = ...`，并可用 `list` 在草稿箱查到。

体检是自动执行的，P0 不过就会在这里停下（此时还不会发任何请求）。逃生口：`--no-preflight`（不建议）、`--no-compliance`。

### Step 6：发布

**先判断账号类型**（见第一节）：

- 认证账号：
  ```bash
  python <skill>/scripts/publish.py publish --media-id <草稿id> -y
  ```
  或直接 `publish`（会新建草稿再发，产生重复草稿，除非确有此意）。
  `-y` 跳过交互确认，仅在用户已明确授权发布时使用；发布不可撤回，会真实推送给粉丝。
- 个人账号：**不要尝试**。告知用户到 mp 后台「内容与互动 → 草稿箱」手动点「发表」，并提醒个人订阅号每天有群发次数限制。

## 六、命令速查

| 命令 | 作用 |
|---|---|
| `publish.py check` | 验凭证 + 白名单，不发内容 |
| `publish.py preflight` | 只做发布前体检，不连微信、不需要凭证 |
| `publish.py enhance` | 内容增强：mermaid 渲染成 PNG、代码块重建为高亮卡片，不连微信 |
| `publish.py draft` | 建草稿（安全档，推荐默认）。发请求前自动跑体检 |
| `publish.py publish` | 建草稿并立即发布 |
| `publish.py publish --media-id XXX -y` | 发布草稿箱里已有的一篇 |
| `publish.py list` | 列草稿箱 |
| `publish.py delete --media-id XXX -y` | 删除指定草稿（破坏性，需显式给 id） |
| `publish.py token -f` | 强制刷新 access_token（遇 40001 时用） |
| `preflight.py -c 配置` | 体检单独跑：`--json` / `--warn-only` / `--no-compliance` |
| `enhance_content.py -c 配置` | 单独跑内容增强：`mermaid` / `code` 子命令、`--dry-run`、`-o 写到别处` |
| `apply_style.py --list` | 列出风格预设 |
| `apply_style.py --preset X -o 文件` | 按预设渲染正文骨架 |
| `apply_style.py --preset X --dump 文件` | 导出成可编辑的自定义预设 |
| `watch_ip.py --draft` | 轮询等白名单生效，通了自动建草稿 |
| `make_assets.py` | 生成封面与插图（需 pillow） |

通用参数：`-c 路径` 指定配置文件（默认按「当前目录/config.json → 脚本目录/config.json」查找）、`-f` 强制刷新 token、`-y` 跳过发布确认。
`draft` 的两个逃生口：`--no-preflight` 跳过体检、`--no-compliance` 体检时跳过合规词扫描。

凭证也可用环境变量提供，无需配置文件：`WECHAT_MP_APPID` / `WECHAT_MP_APPSECRET`。

## 七、排障要点

- 报 **40164**：白名单没配或没生效。先拿 `errmsg` 里的 IP，核对后台是否保存 + 管理员是否扫码。用 `watch_ip.py` 挂着等，不要反复手点。
- 报 **48001**：账号类型限制，尤其 `freepublish`。转向手动发布路径，别重试。
- 报 **40001**：token 被别处刷新导致缓存失效，`token -f` 重取。
- 报 **40007**：封面素材缺失。`cover_file` 没配或文件路径错了，体检的 `WX016/WX017` 会提前拦。
- 报 **40005 / 40009**：正文图格式或体积不对，体检的 `WX014/WX015` 会提前拦。
- 正文图片不显示：用了外链图。改成 `<img src="assets/xxx.png">` 的本地相对路径写法。
- 正文超 2 万字符：先确认是**HTML 长度**不是纯文本字数。mermaid 渲染成 PNG、代码块交给 `enhance_content.py` 重建是最有效的压降手段，仍超就拆篇（第十节）。
- 发布提交成功但后台看不到：`errcode=0` 只代表任务提交成功，发布有延迟，最终结果走事件推送。
- 完整错误码表见 `references/wechat-api-reference.md` 第三节。

## 八、安全约束

- `config.json` 与 `.token_cache.json` 含密钥，**不要写入 git**，不要回显完整 AppSecret。
- 正式发布不可撤回。执行前必须让用户明确知情，默认只建草稿。
- 提醒用户：AppSecret 若在对话或日志中明文出现过，正式使用前到开发者平台重置。
- 合规词检查是**风险提示，不是违规判定**，不能替代人工审核。判定边界见 `references/wechat-api-reference.md` 第六、七节。

## 九、仓库与迭代

本技能同时是开源仓库 `SkyBiuBiu/wechat-mp-publisher-skill`（MIT），仓库根目录即技能根目录。

| 想找什么 | 去哪 |
|---|---|
| 面向人的完整手册（后台菜单路径、白名单排查清单、报错对照） | `docs/manual.md` |
| 给使用者的项目说明与安装方式 | `README.md` |
| 风格路线、token 字典、自定义方式 | `references/style-presets.md` |
| 接口约束、权限矩阵、体检判定依据 | `references/wechat-api-reference.md` |
| 版本变更记录 | `CHANGELOG.md` |
| 开发约定与发版流程 | `CONTRIBUTING.md` |

**改动本技能前**：先读 `CONTRIBUTING.md` 的三条硬规则（零第三方依赖、跨平台、绝不提交密钥），改完执行 `python scripts/validate_skill.py` 自检，必须全绿。

改动涉及接口权限、字段约束时，必须附真实环境验证记录，不能只改文字结论 —— `references/wechat-api-reference.md` 里的权限矩阵是实测结果。
新增体检规则时，在 `references/wechat-api-reference.md` 第六节同步登记，并标明依据属于**官方硬约束 / 实测行为 / 经验阈值**哪一类。


## 十、长文拆篇与「图文化」管线（正文超 2 万字符时）

把现成 HTML 文档（深色设计系统、Mermaid 图、高亮代码块）转成公众号图文时，三个硬约束：正文 ≤2 万字符；`<script>`/`<style>`/class 全被剥掉；外链图被静默过滤。实测可行的管线：

1. **mermaid 图 → `enhance_content.py` 渲染成 PNG**。脚本自动把 ```mermaid 围栏替换成 `<img src="assets/mermaid-N.png">`（本地 mmdc 优先，mermaid.ink 远程兜底），走脚本自动上传换链，不再需要手动 playwright 截图。
2. **代码块不要转图片**：`enhance_content.py code` 把 ``` 围栏与 `<pre><code>` 重建为内联样式高亮卡片（缩进 `&nbsp;`、换行 `<br>` 双保险），文字可选中、手机长按即复制——公众号剥 `<script>`，JS 一键复制按钮活不下来，「长按复制」是唯一可靠路径。代码卡片同时比裸 HTML 省大量字符，是压降 2 万字符上限的主力。
3. **深色设计系统 → 浅色内联样式**：正文转白底配色（文字 #333/#4a5460、卡片 #f7f8fa、强调色加深到可读档），代码块保留深色底；`display:grid`/CSS 变量（`var(--c)`）公众号不可靠，须在转换时解析成具体颜色，多栏布局改纵向堆叠。
4. **拆篇**：按章节组成每篇 ≤1.9 万字符的系列（通常 2-5 篇），标题用「主题①/②/③」编号，每篇独立 config（独立封面）逐篇跑 `draft`；篇尾加系列导航。
5. **推送前用 playwright 以 414px 视口截图抽查**排版（表格换行、图片宽度、锚点残留——站内锚点 `<a href="#...">` 要降级成 `<span>`）。
6. **每篇改完先跑 `preflight.py`**：拆篇后最容易出的是图片路径断裂（`WX012`）、代码块截图漏传（`WX012` 同类）、和上一篇残留的合规词。体检比人眼翻得快。
