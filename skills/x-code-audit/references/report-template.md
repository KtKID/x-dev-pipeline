# 报告格式

一次巡检只产出一份报告：`reports/audit/audit-<检查 ID>.md`。检查 ID 是 8 位随机十六进制数，由 `audit.py start` 生成，报告骨架也由它写好。子 agent 的回执先写在 `reports/audit/audit-<检查 ID>.parts/` 里，`audit.py merge` 合进报告后删掉这个目录，最后只剩一份报告。

报告从上到下：

```markdown
# 代码巡检报告 · 3f9a0c1e

> 检查 ID：3f9a0c1e
> 开始时间：2026-11-23 22:00
> 状态：完成
> 代码版本：a1b2c3d（另有未提交改动）
> 上次巡检：7d2e4b90 @ 9f8e7d6
> 范围：增量（上次巡检以来变了的）
> 层：L1、L2、L3、L4、L5、L6

## 范围

- 模块（3 个）：src/library/loan、src/library/fine、src/library/api
- 文件：12 个，清单在「检查进度」下面

## 结论

| 层 | 结果 | 问题数 |
|---|---|---|
| L1 机器检查 | 有问题 | 2 |
| L2 死代码 | 有问题 | 1 |
| ... | | |

最严重的问题：A1，……（一句话）

## 问题

### A1 · P0 · L4 · 查借阅可以看到别人的记录

- 是什么：……
- 影响：……
- 位置：`src/library/loan.py` 的 `list_loans()`，第 53 行
- 证据：……
- 怎么改：……
- 来源：U5

### A2 · P1 · L5 · ……

## 检查进度

| 单位 | 层 | 范围 | 谁查 | 状态 |
|---|---|---|---|---|
| U1 | L1 | 范围内全部文件 | 脚本 | 完成 |
| U5 | L4 | src/library/loan | 子 agent | 完成 |

范围内的文件：……

## 检查记录

### U1 · L1 机器检查

（脚本写的：找到的工具、缺的规则、跑过的命令和退出码）

### U5 · L4 · src/library/loan

（子 agent 回执里的检查项表）
```

- 「问题」由 `audit.py merge` 按 P0 → P1 → P2 排好序、重新编号 A1、A2…，主 agent 不手动排。
- 「结论」由主 agent 在 merge 和 verify 之后写。
- 「检查记录」是证明查过的依据，`audit.py verify` 靠它核对。
