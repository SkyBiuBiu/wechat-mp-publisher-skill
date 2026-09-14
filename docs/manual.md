# 操作手册

从零到「草稿进箱」的完整路径，含后台菜单的实际位置和踩坑清单。

> 只想看命令的话，回 [README](../README.md)。这里讲的是**为什么**和**卡住了怎么办**。

## 目录

- [〇、先确认账号有资格](#〇先确认账号有资格)
- [一、拿 AppID / AppSecret](#一拿-appid--appsecret)
- [二、配 IP 白名单](#二配-ip-白名单)
- [三、填配置](#三填配置)
- [四、跑链路](#四跑链路)
- [五、选风格路线](#五选风格路线)
- [六、读体检报告](#六读体检报告)
- [七、报错对照](#七报错对照)
- [八、安全边界](#八安全边界)

---

## 〇、先确认账号有资格

微信接口权限跟**账号类型 + 认证状态**强绑定。先看这张表，能省掉后面很多来回：

| 接口 | 用途 | 文档口径 | 实测（2026-09-14） |
|---|---|---|---|
| `/cgi-bin/token` | 拿凭证 | 所有公众号 | ✅ 个人未认证订阅号可用 |
| `/cgi-bin/media/uploadimg` | 正文图片换链 | 所有公众号 | ✅ 可用 |
| `/cgi-bin/material/add_material` | 封面永久素材 | 服务号 | ✅ 个人未认证订阅号**可用** |
| `/cgi-bin/draft/add` | 新增草稿 | 服务号 | ✅ 个人未认证订阅号**可用**，无 48001 |
| `/cgi-bin/freepublish/submit` | **正式发布** | 认证账号 | ❌ 个人未认证订阅号报 `48001` |

**结论**：

- **认证服务号** —— 整条链路全通，含 API 直接发布。
- **未认证订阅号** —— 文档口径说草稿接口仅服务号可用，但实测全通。**别被文档吓退，跑 `check` 试一下就有答案。**
- **`freepublish` 对个人号是死的** —— 个人主体**无法申请微信认证**，所以这不是配置问题，改什么都没用。别重试。
  - 替代路径：用 `draft` 把图文做好推进草稿箱，最后到 mp 后台草稿箱**手动点「发表」**。效果与纯手写发布一致，只是少了最后一下自动化。

拿不准就以公众平台「设置与开发 → 接口权限」页的实际列表为准。

---

## 一、拿 AppID / AppSecret

> ⚠️ **路径已经变了。** 公众号 / 服务号的开发密钥现在在**微信开发者平台**，不在 mp.weixin.qq.com 的老「基本配置」页。

1. 打开 <https://developers.weixin.qq.com/platform>，用**公众号管理员本人的微信**扫码登录。
   - 用错微信会看不到业务 —— 平台按绑定关系展示。
2. 顶部 **我的业务与服务 → 我的业务** → 点 **公众号**（或「服务号」）。
3. 进详情页 → **基础信息 → 开发密钥**：

   | 字段 | 状态 |
   |---|---|
   | **AppID** | 明文直接可见，复制即可 |
   | **AppSecret** | 默认隐藏。首次点 **启用** → 弹出明文 → **只显示这一次**，立刻存好 |

4. 同页往下有 **API IP白名单** 区块（需先启用 AppSecret 才能配置），见下一节。

### 忘了 AppSecret 怎么办

微信平台**不存储、不显示**已生成的 AppSecret，忘了只能点 **重置** 生成新的。

- ⚠️ 重置会让旧 AppSecret **立即失效**。如果还有别的系统在用同一个公众号的密钥，先梳理清楚再点。
- 如果之前已经生成过、现在还能在别处找到，直接用，别重置。

### 点「启用」被挡住

报这两种提示之一：

| 提示 | 原因 | 解决 |
|---|---|---|
| 该账号尚未完成**实名** | 个人主体，管理员没实名 | mp 后台 →「设置与开发 → 人员设置 → 管理员信息」补实名 |
| 该账号尚未完成**主体认证** | 非个人主体，没做微信认证 | mp 后台 →「账号详情 → 认证情况」→ 申请微信认证（300/年） |

自查：mp 后台「账号详情 → 主体信息」能看到管理员姓名 = 已实名；「账号详情 → 认证情况」看认证状态。

### 还没有公众号

先去 mp.weixin.qq.com 注册。个人可免费注册**订阅号**，能走到草稿那一步（见第〇节），但 API 发布用不了。

---

## 二、配 IP 白名单

微信强制校验**调用方的公网出口 IP**，不在白名单一律 `40164`。这是最高频的卡点。

### 取正确的 IP

```bash
# Linux / macOS —— 注意必须带 -4
curl -4 ipv4.icanhazip.com
```

```powershell
# Windows PowerShell
(Invoke-RestMethod https://ipv4.icanhazip.com)
```

- ⚠️ **要的是公网 IPv4 出口地址**，不是 `192.168.x.x` 这种内网地址。
- ⚠️ `curl ifconfig.me` 可能返回 **IPv6**，微信白名单**不认 IPv6**，一定用 `-4` 或用 `ipv4.icanhazip.com`。
- 如果打算在远程 Linux 服务器上跑，就登到那台机器上查 —— 出口 IP 跟本地不一样。

### 配置入口

微信开发者平台 → 公众号详情页 → **API IP白名单** → 点 **启用 / 修改** → 填入 IP → 保存。

> 老入口 mp 后台「设置与开发 → 基本配置 → IP白名单」如果还在，填那里效果一样，是同一份数据。

### 加了白名单还是 40164？按顺序查

| # | 检查项 | 说明 |
|---|---|---|
| 1 | **管理员扫码确认做了吗** | 改白名单是敏感操作，点保存后要管理员微信扫码。**漏这步最常见** |
| 2 | **保存按钮真点了吗** | 部分后台是「修改 → 编辑框 → 保存」两段式，输完没保存等于没改 |
| 3 | **加对公众号了吗** | 一个微信号可能绑多个业务，确认改的是 AppID 匹配的那一个 |
| 4 | **两个入口都试** | 开发者平台的「API IP白名单」和 mp 后台的老入口，遇到不同步就两边都填 |
| 5 | **等几分钟** | 有生效延迟，不是秒级。别反复手点 |
| 6 | **IP 没搞错** | 必须公网 IPv4。见上面的取 IP 方法 |

> `40164` 的报错信息里**自带被拒的 IP**（`invalid ip 36.112.191.145 ...`），脚本会自动抠出来提示你，不用自己猜。

### 别手点，挂着等

白名单生效前不用反复手动重试：

```bash
python scripts/watch_ip.py --draft     # 每 30 秒探一次，通了自动建草稿
python scripts/watch_ip.py -i 60       # 改间隔为 60 秒
python scripts/watch_ip.py -m 3        # 只探 3 次就退出（测试用）
```

你在这边改后台，它在那边等，谁先好都不知道也没关系。

---

## 三、填配置

```bash
mkdir -p work/assets
cp assets/templates/config.example.json work/config.json
```

正文不再需要手工复制模板 —— 用风格渲染器生成（见第五节）：

```bash
python scripts/apply_style.py --preset engineering-orange -o work/article.html
```

编辑 `work/config.json`，**只有两个字段是必填**：

| 字段 | 填什么 |
|---|---|
| `appid` | 第一步记下的 AppID，`wx` 开头 18 位 |
| `appsecret` | 第一步保存的 AppSecret |

其余字段按需改：`article.title`（标题）、`article.digest`（摘要）、`article.content_file`（正文文件）、`article.cover_file`（封面路径）、`style.preset`（风格路线）。

> ⚠️ `config.json` 含密钥，**不要提交到 git、不要发给别人**。本仓库的 `.gitignore` 已经排除了它。

---

## 四、跑链路

四档，从安全到危险：

```bash
# 档位 0：体检。不连微信、不需要凭证，只查内容和排版
python scripts/preflight.py -c work/config.json

# 档位 1：自检。只验证凭证 + 白名单，不发任何内容
python scripts/publish.py check -c work/config.json

# 档位 2：建草稿（推荐默认）。图文只进草稿箱，粉丝看不到
python scripts/publish.py draft -c work/config.json

# 档位 3：建草稿并立即正式发布。粉丝会真的收到推送，不可撤回
python scripts/publish.py publish -c work/config.json
```

`draft` 的执行顺序：**体检 → 取 token → 正文图上传换链 → 封面传永久素材 → 建草稿 → 回查确认**。
体检没过（有 P0）会在这条链的第一环就停下，此时还没有任何网络请求，改完重跑即可。

**成功标志**：输出里有 `draft media_id = ...`，并且 mp 后台 **内容与互动 → 草稿箱** 里能看到那篇。

> 确认草稿没问题后，你也可以**不跑 `publish`，直接在后台网页上点「发表」** —— 效果一样，还多一道人工核对。个人号只能走这条路。

### 正文 HTML 怎么准备

```bash
python scripts/apply_style.py --list                    # 先看六条风格路线
python scripts/apply_style.py --preset terminal-green -o work/article.html
```

渲染出来的文件就是正文源文件，把它改成自己的内容即可。三条硬规则：

1. **全部用内联样式**。`<style>` 块和 `class` 会被公众号编辑器剥离，写了也白写。
2. **不要用外链图**。写成本地相对路径（如 `<img src="assets/diagram.png">`），脚本会先上传到微信图床再替换 `src`。外链会被静默过滤 —— 不报错，但图没了。
3. 不要 JS、不要 iframe、不要表单元素。

图片限制：正文图仅 `jpg/png` 且单张 **< 1MB**。

> 模板第 8 块引用了示例图 `assets/diagram.png`。没有这张图体检会报 `WX012`，放上自己的图或把那一块整段删掉。

更细的标签与样式约束见 [`references/wechat-api-reference.md`](../references/wechat-api-reference.md) 第五节。

### 想批量生成封面和配图

```bash
python scripts/make_assets.py --title "标题" --subtitle "副标题" --date "2026-09-14"
```

需 `pillow`：`pip install pillow`。默认输出 900×383 封面（2.35:1）与一张正文插图。
封面主色跟所选预设的 `primary` 保持一致，成套感最强。

---

## 五、选风格路线

正文风格分**视觉**和**写作**两层，由 `assets/styles/*.json` 的六条路线定义。完整说明（含 16 个 token 字典）见
[`references/style-presets.md`](../references/style-presets.md)，这里是速查：

| 预设 | 适合 | 语气 |
|---|---|---|
| `engineering-orange` 工程橙（默认） | 实战教程、架构拆解、踩坑复盘 | 结论先行，像交接文档 |
| `minimal-paper` 极简纸感 | 观点随笔、方法论、行业观察 | 平静有判断 |
| `terminal-green` 终端绿 | 源码分析、CLI 教程、报错定位 | 直给可执行 |
| `magazine-warm` 杂志暖调 | 项目复盘、访谈、团队故事 | 有温度不说教 |
| `business-blue` 商务蓝 | 方案说明、选型对比、阶段汇报 | 客观有依据 |
| `checklist-qa` 清单问答 | FAQ、SOP、避坑清单 | 干脆，一问一答 |

选不准就看题材：**教人做事** → 工程橙 / 终端绿；**讲一个判断** → 极简纸感 / 商务蓝；**讲一件事** → 杂志暖调；**回答问题** → 清单问答。

### 换风格

```bash
# 换一条预设，重渲染即可。内容不用动，视觉是 token 驱动的
python scripts/apply_style.py --preset minimal-paper -o work/article.html

# 微调单个 token
python scripts/apply_style.py --preset business-blue --set primary=#1f4e8c

# 长期生效：写进 config.json
# "style": { "preset": "business-blue", "overrides": { "primary": "#1f4e8c" } }
```

带 `--preset` 时以命令行为准；不带时读 `config.json` 的 `style.preset`；都没有就用 `engineering-orange`。

### 想要自己的风格

```bash
python scripts/apply_style.py --preset magazine-warm --dump my-style.json
# 编辑 my-style.json：改 tokens（颜色/字号）与 writing（语气/开篇/段落/emoji/收尾）
python scripts/apply_style.py --style-file my-style.json -o work/article.html
```

token 写错会被直接拦下：颜色必须是 `#rgb` / `#rrggbb`（不支持 `red`、`rgb()`、`var(--x)`），尺寸必须带单位。
`config.json` 里写错的 token 名，体检时会报 `WX214`。

**两层要匹配**：视觉改了，写作约束也要跟着改，否则会出现「极简的皮 + 营销的骨」。
渲染出的骨架里的块（要点卡片、表格、代码块、问答块、步骤条）按题材挑用，不用的整段删掉。

---

## 六、读体检报告

```bash
python scripts/preflight.py -c work/config.json
```

三级含义与处理方式：

| 级别 | 含义 | 怎么办 |
|---|---|---|
| **P0 阻断** | 微信一定会报错，或内容一定会坏（字数超限、图片超 1MB、外链图等） | 必须改，退出码 1 |
| **P1 警告** | 发得出去，但排版会塌、图会丢、或有合规风险 | 逐条判断，多数建议改 |
| **P2 建议** | 不影响发布，改了更好 | 有空再说 |

常用参数：

```bash
python scripts/preflight.py -c work/config.json --json         # 结构化输出，给 CI
python scripts/preflight.py -c work/config.json --warn-only    # 有 P0 也返回 0，只报告
python scripts/preflight.py -c work/config.json --no-compliance # 跳过合规词扫描
python scripts/publish.py preflight -c work/config.json        # 等价写法
```

几个容易误读的点：

- **正文字符数按 HTML 长度算，不是纯文本字数。** 报告里两个数都给：`正文 19056 字符 | 纯文本 4210 字`。
  标签多、代码块多的文章，纯文本字数不高也可能撞上限。
- **合规词（`WX114`）是风险提示，不是违规判定。** 只说明这句话值得人工过一眼，
  「唯一标识」这类技术术语会被误报。它不替代人工审核。
- **判定依据分三类**：官方硬约束（必须改）、实测行为（改了更稳）、经验阈值（自行判断）。
  全部 49 条检查项依据的标注见 [`references/wechat-api-reference.md`](../references/wechat-api-reference.md) 第六节。

---

## 七、报错对照

| 现象 | 原因 | 处理 |
|---|---|---|
| 体检报 P0 | 字数/图片/封面/链接有硬伤 | 按报告里的「处理」一栏改，或 `--warn-only` 只看不拦 |
| 体检报 `WX012` | 正文里的图片路径不存在 | 模板自带的 `assets/diagram.png` 是示例，换成自己的图或删掉那块 |
| 体检报 `WX114` | 命中合规风险词 | 人工判断，技术术语可忽略，`--no-compliance` 可整体跳过 |
| `40164` | 出口 IP 不在白名单 | [第二节](#二配-ip-白名单)，加当前公网 IPv4 |
| `40013` / `40125` | AppID / AppSecret 错 | 检查有没有复制到空格、大小写 |
| `40243` | AppSecret 被冻结 | 后台解冻 |
| `48001` | 账号没有该接口权限 | 账号类型问题，见[第〇节](#〇先确认账号有资格)。重试无意义 |
| `40005` | 正文图格式不对 | `uploadimg` 只收 jpg/png（体检 `WX014` 会提前拦） |
| `40009` | 图片体积超限 | 压到 1MB 以下（体检 `WX015` 会提前拦） |
| `40007` | media_id 无效 | 封面素材缺失，检查 `cover_file`（体检 `WX016/WX017` 会提前拦） |
| `40001`（之前是好的） | token 被别处刷新，本地缓存失效 | `python scripts/publish.py token -f` |
| 正文里图片不显示 | 用了外链图片 | 改成本地相对路径写法 |
| 正文超 2 万字符 | 按 HTML 长度算超了 | 代码块/图表截图成 PNG，或按章节拆篇 |
| 草稿建了但发布失败 `53503/53504/53505` | 草稿未通过发布检查 / 需官网手动发布 | 转 mp 后台手动点「发表」 |

完整错误码表（含 `-1`、`45009`、`50004` 等）见 [`references/wechat-api-reference.md`](../references/wechat-api-reference.md) 第三节。

---

## 八、安全边界

- 脚本**默认只建草稿**，不会推送粉丝。`publish` 有二次确认，需显式输入 `yes` 或加 `-y`。
- `config.json` 与 `.token_cache.json` 含敏感信息，已在 `.gitignore` 中。CI 挂了 gitleaks 兜底。
- 正式发布（`freepublish`）**提交成功 ≠ 发布成功**。最终结果走微信服务端事件推送（`PUBLISHJOBFINISH`），审核失败会在推送里报 `53503` 等。
- 体检的合规词检查是**风险提示，不是违规判定**，不替代平台审核，也不替代人工判断。
- AppSecret 若在对话、日志或截图中明文出现过，正式使用前到开发者平台**重置**一次。
