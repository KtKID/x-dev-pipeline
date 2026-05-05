---
name: x-audit-style
description: |
  独立代码规范巡检 skill。不在 x-dev → x-verify → x-qua-gate 主流程内，由用户手动触发或周期性调用。
  调 opus 子 agent 做全项目视角的规范审查：命名一致性、复用机会、magic number、函数长度、文件大小、注释合理性、死代码。
  触发：用户说"规范巡检"、"audit style"、"代码规范检查"、"style review"。
---

# x-audit-style · 代码规范巡检

x-audit-style 是独立巡检 skill，不在主流程内。做全项目视角的代码规范审查。

## 为什么独立

规范问题需要**全局视角**才有意义——单文件命名好但和邻居命名风格不一致，单看局部最优；单任务级别揪命名是过度审查。剥离出来周期巡检更合适。

## 流程

1. 用户触发（手动调用 / 周期性）。
2. dispatch opus 子 agent。
3. 输出 audit-style 报告到 `reports/audit/audit-style-YYYYMMDD-HHmmss.md`。
4. 不自动触发 x-fix——由用户决定。

## 子 agent dispatch

```
Agent({
  description: "Style audit",
  subagent_type: "general-purpose",
  model: "opus",
  prompt: <本 SKILL.md 的"检查清单"段 + 项目代码 + 输出格式>
})
```

## 检查清单

### 1. 命名一致性
- 函数 / 变量命名风格是否项目内统一？（snake_case / camelCase）
- 同概念是否多个名字（比如 user / account / member 混用）？
- 缩写是否一致（id / ID / Id）？

### 2. 复用机会
- 同样的代码在多处出现？提取函数。
- 类似但不完全一样的代码？考虑参数化。
- 多处用同一组 magic number？提取常量。

### 3. magic number / magic string
- 数字 / 字符串字面量没有名字？
- 配置值硬编码在代码里？

### 4. 函数 / 文件大小
- 函数超过 50 行？
- 文件超过 500 行？
- 一个类承担超过 3 件事？

### 5. 注释合理性
- 注释解释 WHAT（应该删，由代码说话）？
- 注释解释 WHY（保留，特别是非显而易见的设计决策）？
- 注释引用过期信息（"used by X"，但 X 已不存在）？

### 6. 死代码
- 未被引用的函数 / 变量 / import？
- 注释掉的代码（应删除，git 已记历史）？
- 永远走不到的分支（unreachable code）？

## 输出

写入 `reports/audit/audit-style-YYYYMMDD-HHmmss.md`，模板见 `templates/audit-style-template.md`。

## 不在范围

- 单任务级别的 style 审查（小范围 lint 工具搞定）
- 自动可修复的（lint 工具 --fix 即可）
- 主观偏好争议（用 lint config 决定，不靠 AI 评审）
