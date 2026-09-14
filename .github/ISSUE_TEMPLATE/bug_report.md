---
name: Bug 报告
about: 报告一个可复现的问题（接口报错、脚本异常、排版异常等）
title: "[Bug] "
labels: bug
---

<!--
提示：贴日志前请先把 AppID / AppSecret / access_token 打码。
它们形如 wx 开头的 18 位串、32 位十六进制串、以及一长串随机字符。
-->

## 环境

| 项 | 值 |
|---|---|
| 操作系统 | <!-- Windows 11 / Ubuntu 22.04 / macOS 14 ... --> |
| Python 版本 | <!-- python --version --> |
| 公众号类型 | <!-- 个人订阅号 / 认证服务号 / 未认证服务号 ... --> |
| 认证状态 | <!-- 已认证 / 未认证 / 不确定 --> |
| 执行的命令 | <!-- 例：python scripts/publish.py draft --> |

## 复现步骤

1.
2.
3.

## 期望结果

## 实际结果

<!-- 请附完整报错输出（脚本会把微信 errcode 翻译成中文提示）。已打码。 -->

```
粘贴输出
```

## 已做过的排查

- [ ] `python scripts/publish.py check` 能过
- [ ] IP 白名单已加入当前公网 IPv4 出口地址，且管理员已扫码确认
- [ ] 账号类型与认证状态已确认（见 `references/wechat-api-reference.md` 权限矩阵）
- [ ] 已 `python scripts/publish.py token -f` 刷新过凭证

## 补充信息

<!-- 相关截图、正文 HTML 片段（去掉敏感内容）等 -->
