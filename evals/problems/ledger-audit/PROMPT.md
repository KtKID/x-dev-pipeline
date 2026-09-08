# 任务：实现一个 CSV 资金流水审计器

使用 Python 3.12 标准库实现命令行工具，读取一份资金流水 CSV，校验每条记录，计算余额，并输出可审计的 JSON 报告。

## 一、任务描述

### 运行方式

```bash
python ledger_audit.py input.csv report.json
```

### 需要提交

- `ledger_audit.py`
- `test_ledger_audit.py`
- `README.md`

依赖范围仅限 Python 3.12 标准库。

### 输入格式

CSV 编码为 UTF-8，表头必须严格为：

```csv
transaction_id,type,amount,status,created_at
```

| 字段 | 规则 |
|---|---|
| `transaction_id` | 非空，同一文件内唯一 |
| `type` | 取值为 `credit` 或 `debit` |
| `amount` | 大于 0，最多两位小数 |
| `status` | 取值为 `posted` 或 `reversed` |
| `created_at` | 格式为 `YYYY-MM-DDTHH:MM:SSZ` |

### 计算规则

- `posted + credit`：余额增加。
- `posted + debit`：余额减少。
- `reversed`：记录有效，对余额和每日汇总的贡献为 0。
- 所有金额解析、计算和汇总路径均使用 `decimal.Decimal`，`float` 不参与金额处理。
- 同一个 `transaction_id` 第一次出现时按正常规则处理，后续记录判定为无效。
- 无效记录对余额和每日汇总的贡献为 0。
- 输出采用确定性排序，在不同运行环境中保持一致。

### 校验优先级

一条记录同时存在多个问题时，只记录第一个错误，顺序如下：

1. `transaction_id` 为空
2. `transaction_id` 重复
3. `type` 非法
4. `amount` 不是合法数字
5. `amount` 小于等于 0
6. `amount` 超过两位小数
7. `status` 非法
8. `created_at` 格式非法

### 输出格式

```json
{
  "summary": {
    "total_rows": 0,
    "valid_rows": 0,
    "invalid_rows": 0,
    "duplicate_rows": 0,
    "posted_rows": 0,
    "reversed_rows": 0,
    "balance": "0.00"
  },
  "daily_summary": {
    "2026-01-01": {
      "credit": "0.00",
      "debit": "0.00",
      "net": "0.00"
    }
  },
  "invalid_records": [
    {
      "line": 2,
      "transaction_id": "EXAMPLE-001",
      "reason": "invalid_type"
    }
  ]
}
```

输出约束：

- `line` 是 CSV 文件中的真实行号，表头为第 1 行。
- 金额统一输出为两位小数字符串。
- `daily_summary` 按日期升序排列。
- `invalid_records` 按行号升序排列。
- JSON 使用 UTF-8，缩进为 2 个空格。

## 二、自包含验收数据

题目目录中的 [`input.csv`](input.csv) 包含以下数据：

```csv
transaction_id,type,amount,status,created_at
T001,credit,100.00,posted,2026-07-01T09:00:00Z
T002,debit,25.50,posted,2026-07-01T10:00:00Z
T003,credit,10.00,reversed,2026-07-01T11:00:00Z
T002,debit,5.00,posted,2026-07-01T12:00:00Z
T004,debit,-3.00,posted,2026-07-01T13:00:00Z
T005,credit,12.345,posted,2026-07-01T14:00:00Z
T006,credit,abc,posted,2026-07-01T15:00:00Z
T007,refund,8.00,posted,2026-07-01T16:00:00Z
T008,credit,20.00,pending,2026-07-01T17:00:00Z
T009,credit,30.00,posted,bad-date
T010,debit,4.50,posted,2026-07-02T09:00:00Z
```

## 三、实现边界

### 必须实现

- CSV 解析
- 完整字段校验
- 重复 ID 检测
- `Decimal` 金额计算
- 每日汇总
- JSON 报告
- 明确退出码
- 自动化测试

### 范围外

- 数据库
- 网络请求
- 并发处理
- 图形界面
- 超大文件流式优化
- 多币种
- 时区转换
- CSV 自动修复
- 配置文件
- 日志框架

### 退出码

| 退出码 | 含义 |
|---:|---|
| 0 | 文件处理成功，且所有记录有效 |
| 1 | 文件处理成功，且存在无效记录 |
| 2 | 参数、文件读取、CSV 表头等致命错误 |

退出码为 2 时：

- `stderr` 输出明确错误信息。
- 不生成不完整的报告文件。
- 进程以受控错误结束，不输出 Python traceback。

## 四、建议完成步骤

1. 建立 CLI 参数和退出码。
2. 校验文件及 CSV 表头。
3. 逐行解析 CSV。
4. 实现确定性字段校验。
5. 检测重复 ID。
6. 使用 `Decimal` 计算余额和每日汇总。
7. 生成固定结构 JSON。
8. 使用 `unittest` 编写测试。
