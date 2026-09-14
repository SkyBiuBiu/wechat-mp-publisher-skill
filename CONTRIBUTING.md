# 贡献与迭代指南

本项目同时是 **WorkBuddy 技能包**和**独立可用的命令行工具**。改动时必须两边都不破坏。

## 目录约定

仓库根目录就是技能根目录，目录结构由 WorkBuddy 技能规范约束，**不要随意挪动**：

| 路径 | 约束 |
|---|---|
| `SKILL.md` | **必须在根目录**，frontmatter 需含 `name` / `description`，`name` 与目录名一致 |
| `scripts/` | 可执行脚本。技能被调用时，AI 从这里找工具 |
| `references/` | 供 AI 参考的文档，按需加载，不进主上下文 |
| `assets/` | 模板与静态资源 |
| `docs/` | 面向人的文档，GitHub 展示用，AI 不读 |
| `.github/` | CI 与协作模板 |

## 硬性规则

1. **绝不提交密钥**。`config.json`、`.token_cache.json`、`.env` 已在 `.gitignore` 中。
   `config.example.json` 只允许占位值（`wx0000...` / 全 0）。
   提 PR 前跑 `python scripts/validate_skill.py`，它会扫一遍。
2. **脚本保持零第三方依赖**（`publish.py` / `watch_ip.py` / `validate_skill.py` / `build_zip.py`）。
   只有 `make_assets.py` 允许依赖 `pillow`，且必须能优雅降级/给出安装提示。
   理由：技能会被直接投放到用户机器上跑，装依赖是最大的摩擦来源。
3. **跨平台**。Windows 与 Linux 都要能跑：
   - 路径统一用 `os.path.join` / `pathlib`，别硬编码 `/` 或 `\`
   - 控制台输出避免 ANSI 颜色（Windows 老终端不认）
   - 文件读写显式 `encoding="utf-8"`
4. **不破坏能力边界声明**。`SKILL.md` 第一节与 `references` 的权限矩阵是实测结论，
   修改必须附上真实环境验证记录，不能只改文字。
5. **破坏性操作必须二次确认**。`publish` / `delete` 保留交互确认与 `-y` 逃生口。

## 开发流程

```bash
git clone https://github.com/SkyBiuBiu/wechat-mp-publisher.git
cd wechat-mp-publisher

# 改完之后自检（结构 + 语法 + 密钥扫描 + 引用路径）
python scripts/validate_skill.py

# 打包一份分发 zip，验证打包链路
python scripts/build_zip.py
```

本地验证需要真实公众号凭证。**请在仓库外的目录做**：

```bash
mkdir -p /tmp/wx-e2e/assets && cd /tmp/wx-e2e
cp /path/to/repo/assets/templates/article.html .
cp /path/to/repo/assets/templates/config.example.json config.json
# 填入自己的 appid / appsecret，然后
python /path/to/repo/scripts/publish.py check
python /path/to/repo/scripts/publish.py draft
python /path/to/repo/scripts/publish.py delete --media-id <验证稿id> -y   # 用完删掉，别污染草稿箱
```

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
