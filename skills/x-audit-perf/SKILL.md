---
name: x-audit-perf
description: |
  独立性能巡检 skill。不在 x-dev → x-verify → x-qua-gate 主流程内，由用户手动触发或在大里程碑后调用。
  调 opus 子 agent 做全项目视角的性能审查：N² 嵌套、不必要循环、大对象拷贝、同步阻塞、数据库 N+1、缓存失效、不必要的 await。
  触发：用户说"性能巡检"、"audit perf"、"看看有没有性能问题"、"perf review"，或大版本发布前。
---

# x-audit-perf · 性能巡检

x-audit-perf 是独立巡检 skill，**不在 x-dev → x-verify → x-qua-gate 主流程内**。它由用户手动触发或大里程碑后调用，做全项目视角的性能审查。

## 为什么独立

性能问题通常需要**全局视角**才有意义——单个任务级别揪 N² 是过度工程，得看整个调用链；缓存失效要看跨服务流。塞进每个任务的 gate 是噪音，所以剥离出来。

## 流程

1. 用户触发（手动调用 / 大里程碑）。
2. dispatch 一个 opus 子 agent，prompt 包含本 SKILL.md 的检查清单 + 项目代码。
3. 子 agent 输出 audit-perf 报告。
4. 写到 `reports/audit/audit-perf-YYYYMMDD-HHmmss.md`。
5. 不自动触发 x-fix——由用户决定哪些问题进入 backlog。

## 子 agent dispatch

```
Agent({
  description: "Performance audit",
  subagent_type: "general-purpose",
  model: "opus",
  prompt: <本 SKILL.md 的"检查清单"段 + 项目代码 + 输出格式>
})
```

## 检查清单

### 1. 算法复杂度
- 嵌套循环：O(n²) 以上是否必要？能否用 hash / index 降到 O(n)?
- 在循环内做 I/O / 重复扫描数据？
- 排序 / 查找算法选择是否合理？

### 2. 数据结构使用
- 用 list 做频繁查找（应该用 set / dict）？
- 大对象拷贝（应传引用 / 用 slice）？
- 频繁字符串拼接（应用 builder / join）？

### 3. I/O 模式
- 同步阻塞 I/O 在异步上下文中？
- 数据库 N+1（在循环里查数据库）？
- 文件 / 网络请求未批量化？

### 4. 缓存与状态
- 重复计算未缓存（纯函数 expensive call）？
- 缓存失效策略缺失或过激进？
- 内存泄漏（持有不必要的引用）？

### 5. 并发与并行
- 不必要的 await / lock 串行化？
- 临界区过大？
- 能并行的串行执行了？

## 输出

写入 `reports/audit/audit-perf-YYYYMMDD-HHmmss.md`，模板见 `templates/audit-perf-template.md`。

## 不在范围

- 单任务级别的 perf 审查（应在 x-qua-gate R2 boundary 里捎带 P1 即可）
- 微优化（编译器能搞定的事）
- 硬件相关（CPU 缓存、SIMD 等，不在 AI 评审范围）
