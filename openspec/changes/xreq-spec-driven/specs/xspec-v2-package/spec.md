# xspec-v2-package Delta

## MODIFIED Requirements

### Requirement: v2 spec 包结构与检测

v2 spec 包 SHALL 由 `spec.md`（需求与验收）与 `modules.md`（模块设计）两个必需文件构成，`design.md`（动态模型）为按需文件；spec.md 头部 SHALL 含 `> spec_version: 2` 标记行。包根 SHALL NOT 包含 task 清单文件（如 `task.md`、`tasks.md`、`dev-checklist.md`）——task 拆解归 x-req。`tasks/` 子目录合法，MAY 存放 x-req 产出的 task 产物（`docs/spec/<name>/tasks/<task>/`）；`tasks/` 内的内容 SHALL 走 task 规则，SHALL NOT 走 v2 spec 规则，且 SHALL NOT 参与 v2 包的必需文件与建模校验。检测判据：`modules.md` 存在或 spec.md 含 spec_version: 2 标记，即按 v2 规则集校验，不落入 capability 单文件包分支。

#### Scenario: v2 包被正确检测并校验

- **GIVEN** 一个目录含带 spec_version: 2 标记的 spec.md 与 modules.md
- **WHEN** 运行 `python3 tools/xdev.py validate <目录>`
- **THEN** 包类型报告为 spec2 并按 v2 规则集校验

#### Scenario: 包根 task 清单文件被抓

- **GIVEN** v2 包根直接出现 `dev-checklist.md`
- **WHEN** 运行 validate
- **THEN** 报出包根不得含 task 产物 issue

#### Scenario: tasks 子目录合法且不参与 v2 校验

- **GIVEN** v2 包含 `tasks/bar/dev-checklist.md` 的子目录 task
- **WHEN** 对 v2 包运行 validate
- **THEN** v2 包零缺件 issue，`tasks/` 内容不被计入 v2 必需文件或建模校验

#### Scenario: 必需文件缺失被抓

- **GIVEN** spec.md 含 spec_version: 2 标记但目录缺 modules.md
- **WHEN** 运行 validate
- **THEN** 报出 v2 包缺件 issue
