# 变更说明

<!-- 一句话说清这个 PR 做了什么 -->

## 类型

- [ ] feat：新能力（向后兼容）
- [ ] fix：修 bug
- [ ] docs：文档
- [ ] refactor：重构（不改变行为）
- [ ] chore：构建 / 版本 / 杂项

## 关联 Issue

<!-- 例：Closes #12 -->

## 自检清单

- [ ] `python scripts/validate_skill.py` 全绿
- [ ] 没有提交任何密钥、token、真实公众号 AppID（`config.example.json` 仍是占位值）
- [ ] 脚本仍是零第三方依赖（`make_assets.py` 的 `pillow` 除外）
- [ ] Windows 与 Linux 路径处理都没问题（未硬编码 `/` 或 `\`）
- [ ] 破坏性操作保留了二次确认
- [ ] `CHANGELOG.md` 已更新到 `[Unreleased]` 段
- [ ] 若改动了 `VERSION`，已按语义化版本判断过升位级别

## 验证方式

<!-- 说明是怎么验的。涉及真实接口的改动，请附脱敏后的命令输出。 -->

```
粘贴验证输出
```

## 是否有破坏性变更

<!-- 有的话说明影响面与迁移方式；没有写「无」 -->
