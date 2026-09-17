# 操作手册

从零到「草稿进箱」的完整路径，含后台菜单的实际位置和踩坑清单。

> 只想看命令的话，回 [README](../README.md)。这里讲的是**为什么**和**卡住了怎么办**。

## 目录

- [〇、先确认账号有资格](#〇先确认账号有资格)
- [一、拿 AppID / AppSecret](#一拿-appid--appsecret)
- [二、配 IP 白名单](#二配-ip-白名单)
- [三、填配置](#三填配置)
- [四、跑链路](#四跑链路)
- [五、选主题](#五选主题)
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

正文不靠脚本渲染骨架 —— 按所选主题的组件库装配（见第五节）：

```bash
python scripts/render_mermaid.py --list-themes          # 看六套主题标识
# 读 references/theme-index.md → 选定主题 → 读
#   references/theme-<标识>.md（主题专属组件）
#   references/common-components.md（代码块/图片/小标签，跨主题通用）
# 然后把组件拼成 work/article.html
```

编辑 `work/config.json`，**只有两个字段是必填**：

| 字段 | 填什么 |
|---|---|
| `appid` | 第一步记下的 AppID，`wx` 开头 18 位 |
| `appsecret` | 第一步保存的 AppSecret |

其余字段按需改：`article.title`（标题）、`article.digest`（摘要）、`article.content_file`（正文文件）、`article.cover_file`（封面路径）、`theme`（主题标识）。

> ⚠️ `config.json` 含密钥，**不要提交到 git、不要发给别人**。本仓库的 `.gitignore` 已经排除了它。

---

## 四、跑链路

四档，从安全到危险：

```bash
# 档位 -1：排版关。不连微信、不需要凭证，只查 HTML 合规
python scripts/validate_gzh_html.py work/article.html

# 档位 0：接口体检。不连微信、不需要凭证，只查标题字数/正文长度/图片约束
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

正文必须**按主题组件库装配**，不要凭记忆手写。步骤：

1. 读 [`references/theme-index.md`](../references/theme-index.md) 选定主题；
2. 读该主题组件库 `references/theme-<标识>.md`（含设计变量表、全部组件、**文章类型配方表**、
   完整文章骨架、Markdown 映射规则）；
3. 读 [`references/common-components.md`](../references/common-components.md) 拿代码块、图片、
   GIF、小标签标题这些跨主题通用组件（套当前主题色）；
4. 按主题库的「完整文章模板骨架」拼装，行内标记按语义找对应组件。

四条硬规则：

1. **全部用内联样式**。`<style>` 块和 `class` 会被公众号编辑器剥离，写了也白写。
2. **所有文字节点用 `<span leaf="">文字</span>` 包裹**。漏了这层包裹，粘到公众号后样式会整片丢失
   —— 这是最常见的致命错，靠 `validate_gzh_html.py` 兜底。
3. **不要用外链图**。写成本地相对路径（如 `<img src="assets/diagram.png">`），脚本会先上传到微信图床再替换 `src`。外链会被静默过滤 —— 不报错，但图没了。
4. 不要 JS、不要 iframe、不要表单元素。

图片限制：正文图仅 `jpg/png` 且单张 **< 1MB**。

装配完先跑产物关，**ERROR 清零、半角标点 WARNING 也修到 0**：

```bash
python scripts/validate_gzh_html.py work/article.html
python scripts/wrap_preview.py work/article.html      # 可选：生成带「复制」按钮的预览页
```

### mermaid 图和代码块

**mermaid 在排版之前就要渲染**（公众号剥 JS 与 SVG 文字，PNG 是唯一稳妥形态）：

```bash
python scripts/render_mermaid.py article.md --theme moyu-green
```

- 产出 `article.mermaid.md`（工作副本，围栏已换成 `![](assets/mermaid-N.png)`）和
  `assets/mermaid-N.png`（默认 `scale=3`，手机上看不糊）。
- 本地装了 mmdc（`npm i -g @mermaid-js/mermaid-cli`）走本地渲染，不联网；没装则走
  mermaid.ink 在线渲染（图表内容会发给该第三方服务，涉密图表加 `--no-remote` 并装 mmdc）。
- 图表的配色自动取所选主题「设计变量速查表」的主色。
- **渲染完一定要看一眼 PNG**：本地编辑器若往 HTML 注入 `data-page-node-id` 这类记账属性，
  会把 mermaid 源码里的 `<br/>` 污染成 `<br data-page-node-id="…">`，它认不出来就会当字面文本
  画在图上。这类污染**不报错、只画错**。
- 装配时把这些 PNG 当普通图片，用主题库/通用库的图片组件引用。

**"图看不清"要改方向，不要调大宽度。** mermaid.ink 按请求宽度缩放位图，而位图在正文里
又被缩放一次，请求宽度被抵消，最后正文里的字号只剩 `图内字号 × 正文宽度 ÷ 图形原始宽度`：

| 图 | 原始宽度 | 正文里字号 | 观感 |
|---|---|---|---|
| `flowchart LR` 七节点 | 1389px | 3.8px | 手机上一团灰 |
| 同图换 `flowchart TD` | 423px | 12.4px | 读得清 |

上表的"正文宽度"取**手机**值 328px（360dp 机型 360 − 两侧留白 16×2），不是桌面网页的
677px —— 按 677 算会把图像字号高估近一倍，早期版本的"17px、很清楚"就是这么来的。
常量在 `theme_vars.MOBILE_CONTENT_W`，插图与代码块共用一处。

脚本已自动处理：量出原始宽度后，字号低于 11px 且换方向能好 1.25 倍以上就**自动换方向**
并在输出里写明 `3.8px → 12.4px`；窄图反过来**收窄显示宽度**（让字号落在 17px 上下，
免得满宽拉出 40px 巨字 + 两张屏高的图）。出图**强制不透明底** —— mermaid.ink 默认给半透明
PNG，而微信点开大图是**黑底查看器**，深色文字压在黑底上等于没画。相关开关：`--font-size`、
`--target-size`、`--keep-direction`、`--no-size-check`。

**代码块不转图片**：用通用库 1a 深色 / 1b 浅色代码块组件，每行一个 `<p style="margin:0">`，
**绝不用 `white-space:pre`**。文字可选中，手机上长按代码即可复制（公众号剥 `<script>`，
JS 复制按钮活不下来，长按复制是唯一可靠路径）。

代码块里有两个"看着小事、坏了很难查"的点：

- **缩进与对齐用 `&nbsp;`**，不要用源码空格。HTML 会折叠空格：行首 4 空格整层消失
  （嵌套结构读不出来），作者对齐在某一列的行尾注释全挤到代码后面。全角空格 `　` 能缩进
  但对不齐列 —— 它宽约 1.67 个半角字符，不是整 2 倍；
- **长行横滑，不折行**：外层 `section` 给 `overflow-x:auto`，每行 `<p>` 再内联
  `white-space:nowrap`。微信会往页面注入 `white-space:normal`，内联样式优先级高于它的
  任何选择器，所以这一层必须内联。折行的坏处是行尾注释被甩到下一行开头，读者分不清它
  属于哪一句。手机上横向滚动条是隐藏的，所以脚本在预计超宽时会在顶栏右侧加
  「👉 左右滑动」提示（与主题库横滑卡组的说法一致）。

**代码要按语言着色**，否则超过十行就糊成一片灰。跑脚本，别手写色值：

```bash
python scripts/highlight_code.py article.md --theme moyu-green -o code.html
python scripts/highlight_code.py --check-widths                # 哪几行会横滑
python scripts/highlight_code.py --show-palette --all-themes   # 看各主题配色
```

配色从主题库的设计变量速查表推导，6 套内置主题与自定义主题都自动适配 —— 以主色色相为
起点铺一圈色环：关键词留在主色相本身（`+0°`，保住主题身份），函数 / 数字 / 字符串 / 内置 /
类型依次 `+35° / +70° / +140° / +195° / +262°`，六个色相同处一个明度带（深色底
`L≈0.68~0.78`）与一个饱和度带（`S≈0.45~0.62`）；关键词与类型加粗，**运算符与标点不着色**。
想要回早期的单色克制版：`--scheme calm`。着色后的 markup 是"外层带色、内层仍
`<span leaf="">`"，见 [`references/common-components.md`](../references/common-components.md) 的 1a+/1b+ 节。

更细的标签与样式约束见 [`references/wechat-api-reference.md`](../references/wechat-api-reference.md) 第五节。

### 想生成封面

```bash
python scripts/make_assets.py -c work/config.json -o work/assets \
    --title "标题" --subtitle "副标题" --date "2026.09"
```

需 `pillow`：`pip install pillow`。输出 900×383 封面（2.35:1）与一张正文插图占位（`--only cover` 可只出封面）。
**配色会自动跟着 `config.json` 的 `theme` 走**——从主题库的「设计变量速查表」里解析主色调、标题色、
正文色、辅助文字色、极浅底色，所以封面和正文天然成套。想手动指定用 `--theme moyu-green`，
想让封面回到内置的深色橙调版式用 `--dark`。

封面右侧那块极淡主色默认是空的。讲循环、流程、分步的文章可以让它点一个环形意象——
环上 N 个节点、顺时针箭头、圆心两行文字，节点数按文章里的环节数填：

```bash
python scripts/make_assets.py -c work/config.json -o work/assets \
    --title "一次循环的七个环节" --subtitle "Agent Loop 拆帧" --date "2026.09" \
    --motif ring --motif-nodes 7 --motif-caption "7 STEPS" --only cover
```

---

## 五、选主题

主题决定**整篇的排版气质与组件体系**：配色、组件形状、章节标题样式、正文关键词标记方式、
代码块与图片的容器样式。文章写什么题材、分几节、怎么收尾，由内容自己决定。

完整清单与下划线色值以 [`references/theme-index.md`](../references/theme-index.md) 为**单一来源**，
这里是速查：

| 主题 | 主色 | 适合 |
|---|---|---|
| **摸鱼绿**（默认） | `#059669` | 教程、测评、清单、工具盘点（卡片丰富、信息密度高） |
| **红白色系** | `#DC2626` | 深度分析、观点、力量感话题（经典编辑风） |
| **石墨极简风** | `#52525B` | 设计、科技评论、专业观点、高端品牌 |
| **留白禅意风** | `#4A5D52` | 禅意、极简生活、深度随笔（呼吸感最强） |
| **摸鱼票据风** | `#059669` | 工具对比、创意评测（票据视觉隐喻） |
| **橄榄手记** | `#1e1f23` | 内刊手记、深度评测、案例复盘（信息密度偏高） |

选不准就看题材：**教人做事** → 摸鱼绿 / 摸鱼票据；**讲一个判断** → 红白 / 石墨极简；
**讲一件事** → 橄榄手记；**什么都不想强调** → 留白禅意。

### 换主题

**换主题 = 换一份组件库重新装配一遍**。这是与旧版最大的区别：旧版换主题只是换 token、
重渲染即可；现在组件的 HTML 结构本身就是主题的一部分，所以要重新拼装。

```bash
# 1. 选定新主题，读它的组件库
python scripts/render_mermaid.py --list-themes
# 2. 重排 article.html
# 3. 重新校验
python scripts/validate_gzh_html.py article.html
# 4. 重新跑 render_mermaid.py（图表配色跟着主题走）
python scripts/render_mermaid.py article.md --theme graphite-minimal --in-place
# 5. 重新跑 highlight_code.py（代码块配色也跟着走）
python scripts/highlight_code.py article.md --theme graphite-minimal -o code.html
```

> 为什么不保留「一键换肤」？因为组件库的价值恰恰在于每套主题的组件是为它的气质专门打磨的
> （摸鱼绿的杂志快讯封面、石墨极简的超大水印编号、留白禅意的大留白衬线引用），
> 用统一 token 去驱动会把它们的差异抹平。

### 想要自己的主题

让 AI 走 [`references/theme-generator.md`](../references/theme-generator.md) 的生成器：

1. **收集偏好**（一次问全）：主题描述必填，或给一张参考图；名称 / 五色 / 字体 / 圆角 / 阴影可留空自动补全。
2. **生成区块库**：产出 45~75 个区块的完整 HTML，存到 `assets/theme-previews/{id}.html`，
   浏览器打开整页浏览确认风格。
3. **转标准主题库 + 登记**：确认后转成 `references/theme-{id}.md`（补 `<span leaf>`、补齐五章节），
   在 `theme-index.md` 登记一行，跑 `component_lint.py` 到 0 ERROR。
4. 之后它与内置 6 套完全同权，直接说「用 XX 主题排这篇」即可。

> ⚠️ 新增主题后必须跑 `python scripts/validate_skill.py` —— 组件库存在但没登记到
> `theme-index.md` 会被判 FAIL。

### 想一次看完「这篇文章在六套主题下长什么样」

选主题靠色值表想象不出来，尤其是流程图配色与代码块明暗。让工具用**一篇已排好的稿子**
当基准，一次产出六版可直接推送的成稿：

```bash
python scripts/build_theme_showcase.py --src work --out work/showcase      # 出六版成稿 + 对比页
python scripts/build_theme_showcase.py --src work --out work/showcase --push   # 顺带逐版推草稿箱
```

产出 `work/showcase/<主题标识>/{article.html, config.json, assets/}`，外加一份
`work/showcase/index.html`（六版并排、按 390px 手机宽渲染）。

它换掉的是**主题身份**、不换版式骨架：配色、圆角倍率、卡片描边与阴影气质
（票据=硬阴影黑描边 / 禅意·石墨·橄榄=细线无影 / 红白=淡红描边）、字体栈、
以及**按主题重渲的 mermaid 图与重新着色的代码块**。骨架沿用基准稿，所以每版
都继承基准稿的窄屏加固，不会出现"某个主题的样张在手机上炸了"。

验证：每版都会自动跑 `validate_gzh_html.py`；要再量一遍宽度用
`node tools/narrow_screen_check.js <成稿路径>`；想目视核对用
`node tools/shot_article.js <成稿路径> <输出目录> <前缀>`（截顶部区 / 流程图 / 代码块）。

---

## 六、读体检报告

```bash
python scripts/preflight.py -c work/config.json
```

三级含义与处理方式：

| 级别 | 含义 | 怎么办 |
|---|---|---|
| **P0 阻断** | 微信一定会报错，或内容一定会坏（字数超限、图片超 1MB、外链图、残留 mermaid 源码等） | 必须改，退出码 1 |
| **P1 警告** | 发得出去，但图会丢、封面会被裁糊 | 逐条判断，多数建议改 |
| **P2 建议** | 不影响发布，改了更好 | 有空再说 |

> **体检只管接口侧硬约束。** 排版问题（漏 `<span leaf>`、半角标点、禁用标签）
> 不在这里查 —— 那是 `validate_gzh_html.py` 的活，两道关都要过。

常用参数：

```bash
python scripts/preflight.py -c work/config.json --json         # 结构化输出，给 CI
python scripts/preflight.py -c work/config.json --warn-only    # 有 P0 也返回 0，只报告
python scripts/preflight.py -c work/config.json --quiet        # 只打印问题清单
python scripts/publish.py preflight -c work/config.json        # 等价写法
```

几个容易误读的点：

- **正文字符数按 HTML 长度算，不是纯文本字数。** 报告里两个数都给：`正文 19056 字符 | 纯文本 4210 字`。
  标签多、代码块多的文章，纯文本字数不高也可能撞上限。
- **别用 `wc -c` 数长度。** 它数的是 UTF-8 字节，中文按 3 字节计，会把 1.6 万字的文章显示成
  2.1 万，据此删内容纯属白删。以 `preflight.py` 的 Python `len(html)` 输出为准。
- **判定依据分三类**：官方硬约束（必须改）、实测行为（改了更稳）、经验阈值（自行判断）。
  检查项依据的标注见 [`references/wechat-api-reference.md`](../references/wechat-api-reference.md) 第六节。

---

## 七、报错对照

| 现象 | 原因 | 处理 |
|---|---|---|
| 体检报 P0 | 字数/图片/封面/链接有硬伤 | 按报告里的「处理」一栏改，或 `--warn-only` 只看不拦 |
| 粘贴到公众号后样式全丢 | 漏了 `<span leaf="">` 包裹 | 跑 `validate_gzh_html.py`，按报的位置补包裹 |
| 校验报半角标点 WARNING | 正文混了半角逗号句号或英文直引号 | 改全角（代码块内不用改） |
| 体检报 `WX029` | 正文里的图片路径不存在 | 换成自己的图，或删掉那块组件 |
| 体检报 `WX028` | 用了外链图，会被静默过滤 | 改成 `assets/xx.png` 本地相对路径 |
| 体检报 `WX026` | 正文残留 ```mermaid 源码 | 先跑 `render_mermaid.py` 转 PNG 再装配 |
| `40164` | 出口 IP 不在白名单 | [第二节](#二配-ip-白名单)，加当前公网 IPv4 |
| `40013` / `40125` | AppID / AppSecret 错 | 检查有没有复制到空格、大小写 |
| `40243` | AppSecret 被冻结 | 后台解冻 |
| `48001` | 账号没有该接口权限 | 账号类型问题，见[第〇节](#〇先确认账号有资格)。重试无意义 |
| `40005` | 正文图格式不对 | `uploadimg` 只收 jpg/png（体检 `WX030` 会提前拦） |
| `40009` | 图片体积超限 | 压到 1MB 以下（体检 `WX031` 会提前拦） |
| `40007` | media_id 无效 | 封面素材缺失，检查 `cover_file`（体检 `WX040/WX041` 会提前拦） |
| `40001`（之前是好的） | token 被别处刷新，本地缓存失效 | `python scripts/publish.py token -f` |
| 正文里图片不显示 | 用了外链图片 | 改成本地相对路径写法 |
| 正文超 2 万字符（WX022） | 文档口径，**实测未强制** | 4.5 万字符实测可发且不截断，照发即可；真被接口回字数错误再压 |
| mermaid 图里印出 `<br data-page-node-id="…">` | 编辑器注入的记账属性污染了源码 | 重跑 `render_mermaid.py`（会自动剥离），**渲染完看一眼 PNG** |
| 草稿建了但发布失败 `53503/53504/53505` | 草稿未通过发布检查 / 需官网手动发布 | 转 mp 后台手动点「发表」 |

完整错误码表（含 `-1`、`45009`、`50004` 等）见 [`references/wechat-api-reference.md`](../references/wechat-api-reference.md) 第三节。

---

## 八、安全边界

- 脚本**默认只建草稿**，不会推送粉丝。`publish` 有二次确认，需显式输入 `yes` 或加 `-y`。
- `config.json` 与 `.token_cache.json` 含敏感信息，已在 `.gitignore` 中。CI 挂了 gitleaks 兜底。
- 正式发布（`freepublish`）**提交成功 ≠ 发布成功**。最终结果走微信服务端事件推送（`PUBLISHJOBFINISH`），审核失败会在推送里报 `53503` 等。
- AppSecret 若在对话、日志或截图中明文出现过，正式使用前到开发者平台**重置**一次。
- 上游排版链路为 AGPL-3.0（详见 [`LICENSE-gzh-design`](../LICENSE-gzh-design)），署名与授权声明不得删除。
