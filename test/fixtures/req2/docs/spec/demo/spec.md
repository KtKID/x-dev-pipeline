# demo

固化测试夹具：一份最小但合法的 v2 spec 包，供 `test/test_req_engine.py` 直接读取。
不要改动结构（`## 验收` 下的 Requirement 名被测试断言引用）。

## 需求说明

### 系统不变量

- 同一时刻只有一个持有者可写入演示状态。

## 验收

### Requirement: 功能A

系统 SHALL 实现功能A。

#### Scenario: 功能A生效

- **WHEN** 触发功能A
- **THEN** 功能A生效
- 验证: auto
