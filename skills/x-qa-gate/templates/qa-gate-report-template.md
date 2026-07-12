# QA Gate Report — <task-name> — YYYYMMDD-HHmmss

**Status:** pass / fail
**路线:** 默认线（RC 综合评审）/ 高危线（R1→R2→R3）
**risk 判定依据:** dev-report `risk:` 字段 / 主 agent 现场判定（写明理由）
**fix-attempts:** N / 3
**verify-report:** reports/verify/verify-report-*.md

## 总览

| Reviewer | 轮次 | 状态 | Completed by model |
|----------|------|-----|--------------------|
| RC unified | 1 | ❌ fail | <actual model id> |
| RC unified（复审） | 2 | ✅ pass | <actual model id> |

（高危线按段列出 R1 / R2 / R3 及各自复审轮）

## 发现台账（累计）

| # | 严重度 | 维度 | 问题 | 处置 | 轮次 |
|---|--------|------|------|------|------|
| F1 | P0 | RC-Q3 | 一句话问题 | ✅ 已修 | 1→2 |
| F2 | P1 | RC-Q4 | 一句话问题 | ➖ 豁免（理由） | 1 |
| F3 | P2 | RC-Q1 | 一句话问题 | 📝 登记 | 1 |

漏检计数：N（复审轮出现的、初审同文件同维度应见未见问题）

## 各轮 mini-report

### 第 1 轮 · RC unified

[mini-report 内容粘贴在此]

### 第 2 轮 · RC unified 复审

[mini-report 内容粘贴在此]

## fix 历史

| 时间 | 触发 reviewer | 轮次 | 处置表路径 |
|------|--------------|------|-----------|
| 2026-07-12 14:23 | RC | 1 | reports/fix/fix-gate-r1-*.md |

## 通关回执快照

（任务通过时，把对话中输出的门禁回执台账原样存档在此）
