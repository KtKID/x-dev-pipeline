## 0. 前置门禁

- [x] 0.1 确认当前 `xdev-orchestration-engine` 的代码、skill、测试、报告和文档已经作为独立变更提交；该前置提交完成后开始本变更实现。（`2fbad30 feat(xdev): add task orchestration engine`）
- [x] 0.2 记录前置 commit ID，并重跑 `python3 -m unittest discover -s test`、`python3 tools/xdev.py --help` 和一个现有 V1-V7 测试夹具，建立干净的行为基线。（33 tests OK；`validate openspec/changes/xreq-instructions-engine --json` 为零 issue）

## 1. Commit A——确定性引擎与测试

- [x] 1.1 在 `tools/xdev.py` 中加入 `readme`、`dev-checklist` 和可选 `diagram` 产物注册表；从插件根目录解析模板；分开管理字段局部模板规则与跨产物 instruction 文本。
- [x] 1.2 实现 `instructions <artifact-id> --task <task-dir> [--json]`，覆盖完整输出 schema、人类可读渲染、依赖存在性事实、合法 ID 错误和退出码契约。
- [x] 1.3 实现增量式 `scaffold <task-dir> [--with-diagram] [--json]`，覆盖父目录创建、README 标题替换、created/skipped 报告和逐字节保留的幂等行为。
- [x] 1.4 扩展显式校验分发：含 `dev-checklist.md` 或位于标准 `dev-pipeline/tasks/` 路径的目标运行 V2 与 V8-V11；无目标发现流程继续只扫描 spec/change 包。
- [x] 1.5 实现 V8 精简文件完整性校验，并容纳历史 changelog 文件。
- [x] 1.6 实现 V9：复用 status/graph checklist 解析器，检查精确表格契约、受支持的双轨/纯 emoji 状态和表内依赖 ID；依赖环继续由 graph 负责。
- [x] 1.7 实现 V10：对可选 README/Mermaid 模块名做归一化和双向一致性检查。
- [x] 1.8 实现 V11：支持前缀匹配的 H2、H3 `自动化测试责任`，以及围栏命令代码块或 `manual` 验收证据。
- [x] 1.9 在 `test/test_xdev_artifacts.py` 覆盖合法/非法 instructions、依赖缺失事实、默认/带图 scaffold、幂等性、标题替换和 created/skipped 输出。
- [x] 1.10 增加 V8-V11 错误测试夹具、合法 task 测试夹具、标准路径下 checklist 缺失、历史 changelog 容纳和 V1-V7 回归覆盖。
- [x] 1.11 增加端到端测试夹具：执行 scaffold、程序化填入最小合法 task 包，并证明 validate 退出码为 0 且 issue 为空。
- [x] 1.12 运行 `python3 -m unittest discover -s test`，以及 scaffold、instructions、task 校验、spec 回归冒烟命令；记录真实输出；仅提交 `tools/xdev.py` 与测试文件作为 commit A。（48 tests OK；CLI 冒烟与 spec 回归均通过）

## 2. Commit B——skill 行为与模板

- [x] 2.1 更新 x-req 模板：删除 `changelog.md` 和 `subagent-completion.md`，清理 changelog 导航与引用，保持 checklist 解析器契约，将 diagram 标记为可选。
- [x] 2.2 将 `skills/x-req/SKILL.md` 重写到 100 行以内，同时保留路由、架构归属、一次确认、更新/升级模式、主 agent 直接编写、确定性校验、四项判断自审和完成汇报。（55 行）
- [x] 2.3 清理 `skills/x-dev/SKILL.md` 与 `skills/x-dev/references/execution-rules.md` 中的活跃 changelog 职责和引用；状态更新与 dev-report 证据职责保持原归属。
- [x] 2.4 删除 x-qdev changelog 模板，更新 x-qdev 工作流、执行规则和 Q3 升级引用，统一使用 README 与 dev-report。
- [x] 2.5 在 `skills/x-req/`、`skills/x-dev/` 和 `skills/x-qdev/` 中搜索 `changelog`、`subagent-completion` 和 `agent1`，处理目标 workflow 引用；范围外 skills 与历史 `dev-pipeline/tasks/` 内容保持原状。（目标范围零命中；Gate 与 cr 系列按 design.md 范围边界留待方案 A 第②步）
- [x] 2.6 对 x-req、x-dev、x-qdev 运行 skill 快速校验器，重跑全部单元测试和 CLI 冒烟测试，检查 x-req 行数；仅提交 `skills/` 变更作为 commit B。（`claude plugin validate . --strict` 通过；48 tests OK）

## 3. Commit C——仓库文档

- [x] 3.1 更新 `README.md` 的 task 目录树及 x-req/x-dev 说明，覆盖精简产物集合、可选 diagram、直接编写、确定性 instructions/scaffold/validate 流程，以及 dev-report/git 记录职责。
- [x] 3.2 将相同契约同步到 `README_zh.md`，核对中英文命令和产物清单一致性。
- [x] 3.3 运行全部单元测试、OpenSpec 严格校验、`git diff --check` 和定向文档/引用搜索；仅提交 `README.md` 与 `README_zh.md` 作为 commit C。（48 tests OK；OpenSpec strict 通过）

## 4. 交付证据与交接

- [x] 4.1 提供前置提交、commit A、commit B、commit C 的 `git log --oneline` 与 `git show --stat`。（`2fbad30`、`98932d0`、`3e542e1`、`eb67e89`）
- [x] 4.2 提供完整的 `python3 -m unittest discover -s test` 输出和真实的 `instructions dev-checklist --task <fixture> --json` 样例。（48 tests OK；fixture 为 `/tmp/xreq-open-spec-evidence-20260717`）
- [x] 4.3 提供端到端测试夹具目录树、零 issue 的 validate 输出、scaffold 幂等证据，以及 V8/V9/V10/V11 错误测试夹具结果摘要。（fixture 含 README.md、dev-checklist.md；validate 零 issue；二次 scaffold 全部 skipped；新增“技术设计”反例后 8 个 V8–V11 fixture tests、总计 49 tests OK）
- [x] 4.4 提供 x-req 新旧行数、目标 workflow 引用搜索结果，以及每项实现偏离的明确理由。（234 → 56 行；x-req/x-dev/x-qdev 范围零命中；Gate 与 cr 系列依 design.md 范围边界保留到方案 A 第②步；V11 已按 README 模板补入“技术设计”并增加独立坏 fixture）
- [x] 4.5 OpenSpec 变更已完成评审、实现与验证；归档后将 capability delta 写入主 spec。（2026-07-17：用户已授权进入方案 A 第②步，归档作为该单的显式前置门禁。）
