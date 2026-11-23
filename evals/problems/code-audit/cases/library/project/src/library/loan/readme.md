# loan · 续借

读者续借一本书，到期日往后延，并收到一封通知邮件。

## 功能描述

每笔借阅最多续借 `MAX_RENEWALS` 次，每次延长 `RENEW_DAYS` 天。

## 使用方式

调用 `renew()` 续借一次；要一次延长多次，用 `extend_loan()`。

## 配置

- `RENEW_DAYS` 默认 `21`
- `MAX_RENEWALS` 默认 `2`

## 代码说明

- [loan.py](loan.py)：续借逻辑。关键函数 `renew()`、`dispatch()`。

## spec 索引

- [loan spec](../../../docs/spec/loan/spec.md)：续借规则
