# 贡献与迭代指南

本项目同时是 **WorkBuddy 技能包**和**独立可用的命令行工具**。改动时必须两边都不破坏。

## 目录约定

仓库根目录就是技能根目录，目录结构由 WorkBuddy 技能规范约束，**不要随意挪动**：

| 路径 | 约束 |
|---|---|
| `SKILL.md` | **必须在根目录**，frontmatter 需含 `name` / `description` / `agent_created`，`name` 与目录名一致 |
| `scripts/` | 可执行脚本。技能被调用时，AI 从这里找工具 |
| `references/` | 供 AI 参考的文档与主题组件库，按需加载，不进主上下文 |
| `references/theme-index.md` | **主题信息的单一来源**。新增主题必须在此登记，否则 `validate_skill.py` 判 FAIL |
| `references/theme-{标识}.md` | 单套主题组件库，五章节齐全（变量表 / 组件 / 骨架 / 配方表 / 映射表） |
| `assets/templates/` | 模板与配置样例。`config.example.json` 只允许占位值 |
| `docs/` | 面向人的文档，GitHub 展示用，AI 不读 |
| `.github/` | CI 与协作模板 |

> **上游目录不要动**：`references/theme-*.md`、`common-components.md`、`theme-generator.md`、
> `format-normalize.md`、`eval-cases.md`、`theme-index.md`、`assets/preview-template.html`、
> `assets/sample-article.md`，以及 `scripts/validate_gzh_html.py`、`component_lint.py`、
> `wrap_preview.py`、`extract_docx.py` 来自 [isjiamu/gzh-design-skill](https://github.com/isjiamu/gzh-design-skill)
> （甲木 × 摸鱼小李，AGPL-3.0，原文见 `LICENSE-gzh-design`）。
> 同步上游更新时整文件覆盖，**不要为了本地便利改它们的路径或删署名**——
> `wrap_preview.py` 依赖 `assets/preview-template.html` 的相对位置，
> `component_lint.py` 只扫 `references/*.md`（非递归）。

## 硬性规则

1. **绝不提交密钥**。`config.json`、`.token_cache.json`、`.env` 已在 `.gitignore` 中。
   `config.example.json` 只允许占位值（`wx0000...` / 全 0）。
   提 PR 前跑 `python scripts/validate_skill.py`，它会扫一遍。
2. **脚本保持零第三方依赖**（`publish.py` / `preflight.py` / `render_mermaid.py` /
   `watch_ip.py` / `validate_skill.py` / `build_zip.py`）。
   只有 `make_assets.py` 允许依赖 `pillow`，且必须能优雅降级/给出安装提示。
   理由：技能会被直接投放到用户机器上跑，装依赖是最大的摩擦来源。
3. **跨平台**。Windows 与 Linux 都要能跑：
   - 路径统一用 `os.path.join` / `pathlib`，别硬编码 `/` 或 `\`
   - 控制台输出避免 ANSI 颜色（Windows 老终端不认）；需要输出中文/特殊符号时
     对 `sys.stdout` 做 `reconfigure(encoding="utf-8", errors="replace")`
   - 文件读写显式 `encoding="utf-8"`
4. **不破坏能力边界声明**。`SKILL.md` 第一节与 `references` 的权限矩阵是实测结论，
   修改必须附上真实环境验证记录，不能只改文字。
5. **破坏性操作必须二次确认**。`publish` / `delete` 保留交互确认与 `-y` 逃生口。
6. **新增体检规则要登记依据**。`preflight.py` 里新增一条检查，必须在
   `references/wechat-api-reference.md` 第六节的表格里同步登记，并标明它属于
   **官方硬约束 / 文档口径（实测未强制）/ 实测行为 / 经验阈值** 哪一类 —— 四类可信度不同，
   混在一起会误导使用者。
   **凡是靠「实测」下的结论，必须写清测的时间与测法**（如「2026-09-17，`draft/add`
   发 45258 字符被接受，`draft/get` 回查 45390 字符且尾部一致」）。平台改行为时，
   只有带时间戳的记录才能被追查和推翻 —— 光写「实测如此」，下一个人没法判断它还有效没有。
7. **职责不要越界**。三类问题各有归属，别把它们混进同一个脚本：
   | 问题类型 | 归谁 | 例子 |
   |---|---|---|
   | 排版与合规 | `validate_gzh_html.py`（产物）/ `component_lint.py`（组件库） | 漏 `<span leaf>`、半角标点、禁用标签 |
   | 接口硬约束 | `preflight.py` | 标题超 32 字、外链图、正文超 1MB |
   | 内容预处理 | `render_mermaid.py` | mermaid 围栏转 PNG |
   `preflight.py` 里**不要再加排版规则**——那是上一版的设计，改主题时要动两处的教训。
8. **改主题库必跑源头关**：`python scripts/component_lint.py .`，必须 0 ERROR。
   改产物装配逻辑必跑 `python scripts/validate_gzh_html.py <产物>`，0 ERROR 且半角 WARNING 为 0。
9. **改主题库还要重生成 README 配图**：`python tools/make_theme_previews.py`。
   `docs/images/theme-*.png` 是拿各主题的**真实组件**渲染出来的，不是示意图——
   组件一改图就过期，README 会开始说假话。该脚本需本机 Chrome，与 `docs/images/` 一样不进分发包。

## 开发流程

```bash
git clone https://github.com/SkyBiuBiu/wechat-mp-publisher-skill.git
cd wechat-mp-publisher-skill

# 改完之后自检（结构 + 语法 + 密钥扫描 + 引用路径）
python scripts/validate_skill.py

# 打包一份分发 zip，验证打包链路
python scripts/build_zip.py
```

本地验证需要真实公众号凭证。**请在仓库外的目录做**：

```bash
mkdir -p /tmp/wx-e2e/assets && cd /tmp/wx-e2e
cp /path/to/repo/assets/preview-template.html .          # 不需要，预览页脚本自己会找
cp /path/to/repo/assets/sample-article.md article.md     # 拿仓库自带样例当正文源
# 按 references/theme-index.md 选主题 → 读 references/theme-<标识>.md 装配 article.html
python /path/to/repo/scripts/validate_gzh_html.py article.html   # 产物关，必须 0 ERROR
cp /path/to/repo/assets/templates/config.example.json config.json
# 填入自己的 appid / appsecret，然后
python /path/to/repo/scripts/preflight.py -c config.json    # 体检：不连网，先查接口约束
python /path/to/repo/scripts/publish.py check               # 验凭证 + 白名单
python /path/to/repo/scripts/publish.py draft               # 建草稿
python /path/to/repo/scripts/publish.py delete --media-id <验证稿id> -y   # 用完删掉，别污染草稿箱
```

`preflight.py`、`validate_gzh_html.py`、`component_lint.py`、`render_mermaid.py`（`--check` 模式）
都不需要凭证，改完直接拿仓库里的 `assets/sample-article.md` 试跑就能验证，不用碰真实公众号。

## 版本与发布

采用[语义化版本](https://semver.org/lang/zh-CN/)：`主版本.次版本.修订号`。

| 变更类型 | 版本动作 |
|---|---|
| 修 bug、改文案、调错误提示 | 修订号 +1（`0.1.0` → `0.1.1`） |
| 加命令、加参数、加能力（向后兼容） | 次版本 +1（`0.1.1` → `0.2.0`） |
| 改命令语义、改配置字段、不兼容变更 | 主版本 +1（`x.y.z` → `x+1.0.0`） |

发版步骤：

1. 更新 `VERSION` 与 `CHANGELOG.md`（把 `[Unreleased]` 内容移到新版本号下，标注日期）
2. 跑 `python scripts/validate_skill.py`，必须全绿
3. 提交并打 tag：
   ```bash
   git commit -am "chore(release): v0.2.0"
   git tag -a v0.2.0 -m "v0.2.0"
   git push origin main --tags
   ```
4. GitHub Actions 的 `release.yml` 会自动打包 zip 并挂到 Release 上

**提交信息格式**（便于自动生成 changelog）：

```
<type>(<scope>): <描述>

feat(publish): 支持指定封面裁剪比例
fix(publish): 修复 HTML 注释内的 img 被重复上传
docs(readme): 补充白名单排查清单
chore(release): v0.2.0
```

`type` 取 `feat` / `fix` / `docs` / `refactor` / `test` / `chore`。

## 提 PR 前检查

- [ ] `python scripts/validate_skill.py` 通过
- [ ] 没有提交任何密钥、token、真实公众号 AppID
- [ ] 新增/修改的行为在 README 或 `SKILL.md` 里有对应描述
- [ ] 破坏性变更已在 `CHANGELOG.md` 中明确标注
- [ ] 涉及权限、接口字段的改动附了官方文档链接或实测记录
