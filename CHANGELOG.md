# Changelog

本项目的所有重要变更都记录在此文件。

格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

版本号同步保存在根目录 `VERSION` 文件，打 tag 时用 `v<版本号>`（例：`v0.1.0`）。

## [Unreleased]

### 计划中

- 多图文（一次草稿投多篇）支持
- 正文 HTML 本地预检：标题/摘要超长、外链图、`<style>` 残留提前报错
- `publish.py status --publish-id XXX` 查询发布任务最终状态
- 封面裁剪比例 `cover_info.crop_percent_list` 支持（`2.35_1` / `1_1`）

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
