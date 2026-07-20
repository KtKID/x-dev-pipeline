---
name: x-req
description: |
  已废弃：保留旧版 x-req 的任务包规划规则与模板，供历史 task 和迁移核对使用。新需求使用 x-req2。
---

# x-req — 风险路由规划

## 产物

新 task 需要 `README.md` 与 `dev-checklist.md`；涉及至少三个模块或用户要求图时加入 `diagram.md`。README 的 `risk: Q0|Q1|Q2|Q3` 是风险唯一真源，`验收` Requirement/Scenario 是 DoD 真源，dev-report 保存 verify 证据。

## 定级

| 等级 | 判据 | 流程 |
|---|---|---|
| Q0 | 单文件且没有行为分支变化 | lite task → x-dev → verify → 交付 |
| Q1 | 局部功能或修复，没有跨模块契约变化 | lite task → x-dev → verify → 交付 |
| Q2 | 新功能、多文件、契约或状态变化 | 一次确认 → x-dev → verify → RC |
| Q3 | 鉴权、权限、加密、不可逆写入或迁移、公开 API/协议/schema、并发、状态机、缓存一致性 | 一次确认 → x-dev → verify → R1→R2→R3 |

用户显式定级优先。Q0/Q1 直接编写 task 并在完成汇报中说明定级依据；用户可随时指定“按 Q2 走”。架构归属、状态模型或跨模块边界未闭合时转 x-spec。

## 流程

1. 定位 task：新建使用 `dev-pipeline/tasks/<name>/`；更新先读现有 README、checklist 与 dev-report，保留无关内容并写 `updated: YYYY-MM-DD <summary>`。
2. 调查用户请求、关联 spec、模块文档和代码入口，确定需求、边界类、公开契约、数据流、失败路径、验收场景和 risk。
3. Q2/Q3 依据 `templates/confirmation.md` 一次展示确认；用户修改后更新并再次确认；取消则结束。
4. 确认或 Q0/Q1 直通后，运行 `python3 tools/xdev.py scaffold <task-dir>`；涉及图时加 `--with-diagram`。
5. 依次运行 `instructions readme`、`instructions dev-checklist`、按需 `instructions diagram`；填写模板，删除 HTML 注释。
6. README 写入 risk；每个验收 Scenario 有 WHEN、THEN、`验证: auto|manual`；自动场景由后续 dev-report verify 块回指。
7. 运行 `python3 tools/xdev.py validate <task-dir>`，修复 issue 直到零 issue；检查需求覆盖、验收可判定性、架构归属和 checklist 追溯。
8. 输出 task 路径、产物、risk 依据、validate 结论和下一步 `x-dev <task-name>`。

## 内容规则

- Q0/Q1 保留核心目标与验收；Q2/Q3 还写需求要点、涉及模块、架构拆分策略和技术设计。
- checklist 使用 `# | 任务 | 涉及文件 | 依赖 | 状态 | fix` 表头与 token+emoji 状态。
- diagram 是 README 模块与边界的投影，节点名称保持双向一致。
- 历史 task 保持原状；活跃 task 使用本契约。
