# uncovered

夹具：spec 包与任务表均合法，但**「无人认领的功能Z」故意没有任何 task 承接**，
用于验证 spec 级覆盖检查报 REQ6，同时单个 task 的 validate 不因此误报。

## 验收

### Requirement: 功能X

系统 SHALL 实现功能X。

#### Scenario: 功能X生效

- **WHEN** 触发功能X
- **THEN** 功能X生效
- 验证: auto

### Requirement: 功能Y

系统 SHALL 实现功能Y。

#### Scenario: 功能Y生效

- **WHEN** 触发功能Y
- **THEN** 功能Y生效
- 验证: auto

### Requirement: 无人认领的功能Z

系统 SHALL 实现功能Z（故意不给它派 task）。

#### Scenario: 功能Z生效

- **WHEN** 触发功能Z
- **THEN** 功能Z生效
- 验证: auto
