# verify-gap

夹具：spec 包与任务表均合法，但 `dev-report.md` 里**没有回指「功能V生效」的 verify 块**，
用于验证 verify 把该自动场景列入 `uncovered` 并以退出码 1 结束。

## 验收

### Requirement: 功能V

系统 SHALL 实现功能V。

#### Scenario: 功能V生效

- **WHEN** 触发功能V
- **THEN** 功能V生效
- 验证: auto
