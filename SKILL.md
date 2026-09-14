---
name: wechat-mp-publisher
description: 微信公众号图文发布技能。当用户要求「发公众号」「发一篇公众号文章/推文」「推到公众号草稿箱」「公众号排版发布」「把这篇发到微信公众号」时使用。通过微信官方 API 完成 access_token 获取、正文图片上传换链、封面永久素材上传、图文草稿创建，并可选正式发布。内置错误码中文翻译、IP 白名单诊断与白名单生效轮询。
agent_created: true
---

# 微信公众号图文发布

用微信官方 API 把一篇带图带排版的图文推进公众号草稿箱，可选继续正式发布。

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

## 三、工作流程

### Step 1：准备工作目录

在用户的工作目录下建发布目录，从技能模板复制骨架：

```bash
mkdir -p wechat-publish/assets
cp <skill>/assets/templates/article.html        wechat-publish/article.html
cp <skill>/assets/templates/config.example.json wechat-publish/config.json
# 编辑 config.json 填 appid / appsecret / title / digest
```

可选：用 `scripts/make_assets.py` 生成封面和插图（需 pillow），默认封面 900×383。

### Step 2：写正文

- **全部使用内联样式**，`<style>` 与 `class` 会被公众号编辑器剥离。
- 正文图片写成本地相对路径（如 `assets/diagram.png`），脚本会先上传到微信图床再替换 `src`。
- **不要用外部图片链接**，微信会静默过滤外链图。
- 从 `assets/templates/article.html` 起步，它已包含段落、要点卡片、表格、图片、页脚分隔线的内联样式写法。
- 详细标签约束见 `references/wechat-api-reference.md` 第五节。

### Step 3：自检

```bash
python <skill>/scripts/publish.py check
```

只验证凭证与白名单，不产生任何内容。失败时按错误码处理。

### Step 4：建草稿

```bash
python <skill>/scripts/publish.py draft
```

按顺序执行：取 token → 正文图上传换链 → 封面传永久素材 → 建草稿 → 回查确认。
成功标志：输出 `draft media_id = ...`，并可用 `list` 在草稿箱查到。

### Step 5：发布

**先判断账号类型**（见第一节）：

- 认证账号：
  ```bash
  python <skill>/scripts/publish.py publish --media-id <草稿id> -y
  ```
  或直接 `publish`（会新建草稿再发，产生重复草稿，除非确有此意）。
  `-y` 跳过交互确认，仅在用户已明确授权发布时使用；发布不可撤回，会真实推送给粉丝。
- 个人账号：**不要尝试**。告知用户到 mp 后台「内容与互动 → 草稿箱」手动点「发表」，并提醒个人订阅号每天有群发次数限制。

## 四、命令速查

| 命令 | 作用 |
|---|---|
| `publish.py check` | 验凭证 + 白名单，不发内容 |
| `publish.py draft` | 建草稿（安全档，推荐默认） |
| `publish.py publish` | 建草稿并立即发布 |
| `publish.py publish --media-id XXX -y` | 发布草稿箱里已有的一篇 |
| `publish.py list` | 列草稿箱 |
| `publish.py delete --media-id XXX -y` | 删除指定草稿（破坏性，需显式给 id） |
| `publish.py token -f` | 强制刷新 access_token（遇 40001 时用） |
| `watch_ip.py --draft` | 轮询等白名单生效，通了自动建草稿 |
| `watch_ip.py -i 60 -m 3` | 改间隔 / 限次数（测试用） |
| `make_assets.py` | 生成封面与插图（需 pillow） |

通用参数：`-c 路径` 指定配置文件（默认按「当前目录/config.json → 脚本目录/config.json」查找）、`-f` 强制刷新 token、`-y` 跳过发布确认。

凭证也可用环境变量提供，无需配置文件：`WECHAT_MP_APPID` / `WECHAT_MP_APPSECRET`。

## 五、排障要点

- 报 **40164**：白名单没配或没生效。先拿 `errmsg` 里的 IP，核对后台是否保存 + 管理员是否扫码。用 `watch_ip.py` 挂着等，不要反复手点。
- 报 **48001**：账号类型限制，尤其 `freepublish`。转向手动发布路径，别重试。
- 报 **40001**：token 被别处刷新导致缓存失效，`token -f` 重取。
- 正文图片不显示：用了外链图。改成 `<img src="assets/xxx.png">` 的本地相对路径写法。
- 发布提交成功但后台看不到：`errcode=0` 只代表任务提交成功，发布有延迟，最终结果走事件推送。
- 完整错误码表见 `references/wechat-api-reference.md` 第三节。

## 六、安全约束

- `config.json` 与 `.token_cache.json` 含密钥，**不要写入 git**，不要回显完整 AppSecret。
- 正式发布不可撤回。执行前必须让用户明确知情，默认只建草稿。
- 提醒用户：AppSecret 若在对话或日志中明文出现过，正式使用前到开发者平台重置。

## 七、仓库与迭代

本技能同时是开源仓库 `SkyBiuBiu/wechat-mp-publisher`（MIT），仓库根目录即技能根目录。

| 想找什么 | 去哪 |
|---|---|
| 面向人的完整手册（后台菜单路径、白名单排查清单、报错对照） | `docs/manual.md` |
| 给使用者的项目说明与安装方式 | `README.md` |
| 版本变更记录 | `CHANGELOG.md` |
| 开发约定与发版流程 | `CONTRIBUTING.md` |

**改动本技能前**：先读 `CONTRIBUTING.md` 的三条硬规则（零第三方依赖、跨平台、绝不提交密钥），改完执行 `python scripts/validate_skill.py` 自检，必须全绿。

改动涉及接口权限、字段约束时，必须附真实环境验证记录，不能只改文字结论 —— `references/wechat-api-reference.md` 里的权限矩阵是实测结果。
