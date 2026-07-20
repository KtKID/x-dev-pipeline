# 变更记录

| 时间 | 操作 | 内容 |
|------|------|------|
| 2026-07-20 | 开始开发 | 记录当前脏工作树基线，开始把新旧 verify 实现集中到 `tools/verify.py` |
| 2026-07-20 | 完成迁移 | xdev CLI 统一委托 `verify.py`；`req.py` 保留 checklist/spec 通用解析 |
| 2026-07-20 | Reviewer 首轮 fail | 发现 legacy 路径误用全角兼容正则，旧 task 的 exit 语义会变化 |
| 2026-07-20 | 修复 P1 | 增加 `LEGACY_VALIDATION_RE` 与旧路径全角标记回归测试 |
| 2026-07-20 | 验证通过 | 67 个定向测试、166 个全量测试、两个 OpenSpec strict 校验与 `git diff --check` 通过 |
| 2026-07-20 | Reviewer 通过 | 原 P1 resolved；最终 PASS，P0/P1 none |
| 2026-07-20 | 范围收敛 | 按用户后续要求删除 `verify.py` 的旧 `dev-pipeline/tasks/` 验证逻辑，公开入口仅接受 spec task |
| 2026-07-20 | 后续验证通过 | 67 个定向测试、166 个全量测试通过；旧路径回归确认 exit 2 |
