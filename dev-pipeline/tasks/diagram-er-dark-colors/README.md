# diagram-er-dark-colors

> 创建时间：2026-06-15
> 类型：优化

## 说明

修正 spec 图集模板里的数据关系图表达方式。目标是让 `diagrams.md` 渲染数据关系图时，实体标题、字段、关系标签和连线在暗色预览里保持清晰对比。

## 涉及模块

- `skills/x-spec/templates/diagrams.md` — 增加 flowchart 数据关系图示例
- `skills/x-spec/SKILL.md` — 补充数据关系图生成规范

## 技术设计（可选，只在有新数据结构/选型时写）

无新数据结构。

## DoD（怎么算完成）

- [x] 数据关系图模板包含 Mermaid 局部主题配置
- [x] 数据关系图规范明确紧凑实体节点、标题分隔线和文字颜色
- [x] 总览模块节点明确要求中文说明模块作用和关键类/函数
- [x] 新增 E2E 测试链路图，描述测试数据、用户动作、系统处理和断言
- [x] 生成样例 `diagram.md` 验证总览、类关系和数据关系效果
- [x] `x-spec` 图模板 `#fff/#ffffff` 检索为空

## 开发清单

| 编号 | 优先级 | 质检 | 状态 | 任务 | 备注 |
|------|--------|------|------|------|------|
| #1 | P0 | 🔍 | ✅ 测试通过 | 调整数据关系图模板和规范配色 | Mermaid 11.15.0 解析通过 |
| #2 | P1 | 🔍 | ✅ 测试通过 | 强化总览节点中文模块作用和关键类/函数说明 | 文本检索通过 |
| #3 | P1 | 🔍 | ✅ 测试通过 | 生成样例 diagram.md | Mermaid 解析通过 |
| #4 | P1 | 🔍 | ✅ 测试通过 | 新增 E2E 测试链路图 | Mermaid 解析通过 |

## 涉及文件

- `skills/x-spec/templates/diagrams.md` — 增加 flowchart 数据关系图示例
- `skills/x-spec/SKILL.md` — 补充数据关系图生成规范
- `dev-pipeline/tasks/diagram-er-dark-colors/diagram.md` — 样例图集
- `dev-pipeline/tasks/diagram-er-dark-colors/verify-data-relation.mjs` — 数据关系图解析验证脚本
- `dev-pipeline/tasks/diagram-er-dark-colors/verify-diagram.mjs` — 样例图集解析验证脚本
- `dev-pipeline/tasks/diagram-er-dark-colors/changelog.md` — 记录变更
- `dev-pipeline/tasks/diagram-er-dark-colors/dev-report.md` — 记录验证命令
