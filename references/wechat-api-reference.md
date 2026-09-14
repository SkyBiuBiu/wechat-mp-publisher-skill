# 微信公众平台 API 参考（本技能相关部分）

核准时间：2026-09。接口参数取自微信官方文档原文，权限结论含实测验证。

## 一、核心接口清单

| 步骤 | 方法与路径 | 用途 |
|---|---|---|
| 凭证 | `GET /cgi-bin/token` | 拿 access_token，有效期 7200 秒 |
| 正文图 | `POST /cgi-bin/media/uploadimg` | 上传正文内图片，返回 mmbiz 域名 URL |
| 封面 | `POST /cgi-bin/material/add_material?type=image` | 上传永久素材，返回 media_id |
| 草稿 | `POST /cgi-bin/draft/add` | 新建图文草稿 |
| 发布 | `POST /cgi-bin/freepublish/submit` | 把草稿正式发布出去 |
| 查草稿 | `POST /cgi-bin/draft/batchget` | 列草稿箱 |
| 查详情 | `POST /cgi-bin/draft/get` | 按 media_id 回查草稿内容 |

域名统一 `https://api.weixin.qq.com`。

### 1. access_token

```
GET https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid=AppID&secret=AppSecret
```

返回 `{"access_token": "...", "expires_in": 7200}`。

- 全局唯一。**在别处刷新会让本地缓存的 token 失效**，报 40001，用 `-f` 强制刷新即可。
- 有调用频率限制，务必用缓存，别每次现取。

### 2. 上传正文图片

```
POST https://api.weixin.qq.com/cgi-bin/media/uploadimg?access_token=TOKEN
Content-Type: multipart/form-data   字段名：media
```

返回 `{"url": "http://mmbiz.qpic.cn/...", "errcode": 0}`。

- 限制：**仅 jpg/png，单张 < 1MB**。
- 不占用素材库 10 万张配额。
- 正文里的**外部图片链接会被微信过滤**，所以正文图必须先过这个接口换链，这是硬要求。

### 3. 上传封面永久素材

```
POST https://api.weixin.qq.com/cgi-bin/material/add_material?access_token=TOKEN&type=image
Content-Type: multipart/form-data   字段名：media
```

返回 `{"media_id": "...", "url": "..."}`。

- 图片上限 10MB，支持 bmp/png/jpeg/jpg/gif。
- 返回的 url 只在**腾讯系域名**内可用，别拿去做外部引用。
- 素材库上限：图文/图片各 10 万，其他类型 1000。

### 4. 新增草稿

```
POST https://api.weixin.qq.com/cgi-bin/draft/add?access_token=TOKEN
Content-Type: application/json
```

请求体：

```json
{
  "articles": [
    {
      "article_type": "news",
      "title": "标题",
      "author": "作者",
      "digest": "摘要",
      "content": "<HTML 正文>",
      "content_source_url": "https://...",
      "thumb_media_id": "封面 media_id",
      "need_open_comment": 0,
      "only_fans_can_comment": 0
    }
  ]
}
```

返回 `{"media_id": "..."}`。

字段约束（超了直接报错，本地先校验更省事）：

| 字段 | 必填 | 上限 |
|---|---|---|
| `title` | 是 | 32 字 |
| `author` | 否 | 16 字 |
| `digest` | 否 | 120 字；留空则抓正文前 54 字 |
| `content` | 是 | 少于 2 万字符、小于 1MB。**会剥离 JS** |
| `content_source_url` | 否 | 1KB，即文末「阅读原文」地址 |
| `thumb_media_id` | 图文消息必填 | 必须是**永久素材** media_id |

其他要点：

- 不要传 Unicode 转义（别写 `\u4f5c\u8005`），直接传字符串。
- 支持 `cover_info.crop_percent_list` 指定封面裁剪比例，图文消息仅支持 `2.35_1` 和 `1_1`。
- 多图文时只有单图文才有摘要，多图文 `digest` 传空。
- 草稿被群发或发布后，会从草稿箱移除。

### 5. 发布草稿

```
POST https://api.weixin.qq.com/cgi-bin/freepublish/submit?access_token=TOKEN
Content-Type: application/json        {"media_id": "要发布的草稿 id"}
```

返回 `{"errcode": 0, "errmsg": "ok", "publish_id": "..."}`。

- **`errcode=0` 只代表任务提交成功，不代表发布完成**。最终结果通过开发者服务器配置的事件推送（`PUBLISHJOBFINISH`）返回，`publish_status`：0 成功 / 1 发布中 / 2 原创失败 / 3 常规失败 / 4 平台失败。
- 发布时间可能滞后，提交成功后立刻去后台看可能还没出来。

## 二、权限矩阵与实测结论

微信的接口权限由**账号类型 + 认证状态**共同决定，文档标准口径与实际可用范围存在差异。

| 接口 | 文档口径 | 实测（2026-09-14） |
|---|---|---|
| `/cgi-bin/token` | 所有账号 | ✅ 个人未认证订阅号可用 |
| `/cgi-bin/media/uploadimg` | 所有账号 | ✅ 可用 |
| `/cgi-bin/material/add_material` | 服务号 | ✅ 个人未认证订阅号**可用** |
| `/cgi-bin/draft/add` | 服务号 | ✅ 个人未认证订阅号**可用**，无 48001 |
| `/cgi-bin/freepublish/submit` | 认证账号 | ❌ 个人未认证订阅号报 `48001` |

**关键结论**：

- 个人主体公众号**无法申请微信认证**，所以 API 正式发布对个人号永久不可用，这是账号类型限制而非配置问题。
- 个人号可行路径：**用 API 建草稿 → 后台草稿箱手动点「发表」**。自动化覆盖排版、配图、上传、成稿，只留最后一下人工。
- 非个人主体账号做完微信认证后全链路可用。
- 判断依据始终以公众平台「设置与开发 → 接口权限」页的实际列表为准。

## 三、错误码对照

| 错误码 | 含义 | 处理 |
|---|---|---|
| -1 | 系统繁忙 | 稍后重试 |
| 40001 | AppSecret 错误，或 access_token 失效 | 检查密钥；`token -f` 刷新 |
| 40005 | 文件格式不支持 | 正文图仅 jpg/png |
| 40007 | media_id 无效 | 封面素材可能被删 |
| 40009 | 图片体积/尺寸过大 | 正文图压到 1MB 以下 |
| 40013 | AppID 不合法 | 检查大小写与空格 |
| 40125 | AppSecret 不合法 | 检查大小写与空格 |
| **40164** | **调用 IP 不在白名单** | 见下节 |
| 40243 | AppSecret 已冻结 | 后台解冻 |
| 45009 | 超过每日调用限额 | 减少调用，用 token 缓存 |
| **48001** | **接口未授权** | 账号类型/认证问题，无法绕过 |
| 50004 | 禁止使用 token 接口 | 账号限制 |
| 50007 | 账号已冻结 | — |
| 53404 | 账号被限制带货能力 | 删掉商品参数 |
| 53503 | 草稿未通过发布检查 | 检查草稿内容 |
| 53504 | 请到官网使用该草稿 | 转后台手动发布 |
| 53505 | 请先到官网手动保存成功后再发布 | 转后台手动发布 |

## 四、IP 白名单

微信强制校验**调用方公网出口 IP**，不在白名单一律 40164。

- 白名单入口：**微信开发者平台** `developers.weixin.qq.com/platform` → 我的业务 → 公众号 → 详情页 → **API IP白名单**。
  - 老入口 mp 后台「设置与开发 → 基本配置 → IP白名单」是同一份数据。
  - 需先启用 AppSecret 才能配置白名单。
- 修改后大概率需要**管理员扫码确认**，这是最常被漏掉的一步。
- **只认 IPv4**。`curl ifconfig.me` 可能返回 IPv6，用 `curl -4 ipv4.icanhazip.com` 取 IPv4。
- 白名单有**生效延迟**，不是秒级。用 `scripts/watch_ip.py` 轮询等待，别反复手点。
- 40164 的 `errmsg` **自带被拒 IP**（`invalid ip 36.112.191.145 ...`），脚本会自动抠出来提示。

### 凭证获取路径（2026-09 口径）

AppID / AppSecret 在**微信开发者平台**，不在 mp 后台：

```
企业微信扫码登录 developers.weixin.qq.com/platform
  → 我的业务与服务 → 我的业务 → 公众号 / 服务号
  → 基础信息 → 开发密钥
```

- AppID 明文可见。
- AppSecret 默认隐藏，首次点「启用」→ 明文**只显示一次**，必须当场保存。
- 平台**不存储、不显示**已生成的 AppSecret，忘了只能重置；**重置会让旧密钥立即失效**。
- 启用被拦的两种情况：个人主体未实名（去 mp 后台「设置与开发 → 人员设置 → 管理员信息」补）、非个人主体未做微信认证（需申请微信认证）。

## 五、正文 HTML 的写法约束

公众号编辑器对 HTML 有强过滤，实践要点：

1. **全部用内联样式**。`<style>` 块和 `class` 会被剥离，写了也白写。
2. **不要外部图片**。所有 `<img>` 必须指向 mmbiz 域名（先过 uploadimg），外链会被静默过滤。
3. 不要 JS、不要 iframe、不要表单元素。
4. 支持的常用标签：`p`、`section`、`strong`、`em`、`span`、`br`、`img`、`a`、`table/thead/tbody/tr/td/th`、`ul/ol/li`、`blockquote`、`code`、`h1`~`h4`。
5. 表格要写 `border-collapse: collapse` 并给 `th/td` 内联 padding，否则在手机上会散。
6. 字号建议正文 15-16px、行高 1.75-1.8、正文色 `#3f3f3f`，公众号正文区宽度约 677px。
7. 正文里 `<img>` 用 `width:100%` 更稳，微信不会自动做响应式。

`assets/templates/article.html` 是一份可直接改用的样板，含段落、要点卡片、表格、图片、页脚分隔线的内联样式写法。
