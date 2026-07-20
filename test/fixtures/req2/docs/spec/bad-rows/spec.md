# bad-rows

夹具：配合 `tasks/bad-rows/` 的行级错样例。**「重名需求」故意出现两次**，用于触发 Requirement 重名判定。

## 验收

### Requirement: 功能A

系统 SHALL 实现功能A。

#### Scenario: 功能A生效

- **WHEN** 触发功能A
- **THEN** 功能A生效
- 验证: auto

### Requirement: 重名需求

系统 SHALL 实现重名需求（此名在本文件中故意出现两次）。

#### Scenario: 重名需求生效一

- **WHEN** 触发重名需求
- **THEN** 重名需求生效
- 验证: auto

### Requirement: 重名需求

系统 SHALL 实现重名需求（重复声明，故意保留）。

#### Scenario: 重名需求生效二

- **WHEN** 再次触发重名需求
- **THEN** 重名需求生效
- 验证: auto
