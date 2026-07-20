# xdev-verification-engine Delta

## MODIFIED Requirements

### Requirement: Scenario coverage reconciliation

verify SHALL 从 task `dev-checklist.md` 头部 `spec:` 指针定位归属 `spec.md`，解析其 `## 验收` 中标记 `验证: auto` 的 `#### Scenario:` 名称。每个自动场景 SHALL 至少有一个 auto verify 块以 `scenario:` 回指同名场景；strip 后仍不匹配的名称 SHALL 出现在 `uncovered`。manual 场景 SHALL 不要求 verify 块。SHALL NOT 再从 task README 读取验收场景。

#### Scenario: 自动场景已有证据回指

- **GIVEN** 归属 spec.md 的 auto Scenario 与 dev-report auto verify 块的 scenario 值匹配
- **WHEN** 调用方运行 `verify --json`
- **THEN** 该场景不出现在 `uncovered`

#### Scenario: 自动场景缺少证据回指

- **GIVEN** 归属 spec.md 的 auto Scenario 没有匹配的 auto verify 块
- **WHEN** 调用方运行 `verify --json`
- **THEN** 命令以退出码 1 结束，且该场景出现在 `uncovered`
