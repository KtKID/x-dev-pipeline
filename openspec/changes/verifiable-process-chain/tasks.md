## 前置门禁

- [ ] 1.0 确认 `x-tech-design` 由「可选」升为 `x-req` 前置：无 `tech-design.contract.yaml` 时 x-req 拒绝拆任务（**BREAKING**，需用户裁决）
- [ ] 1.1 确认证据重跑的抽样比例（默认 auto 全跑 + 完整套件随机 20%）与超时上限
- [ ] 1.2 确认变异抽查的轮数与触发条件（建议：Q2/Q3 每轮 1 个 VC，Q0/Q1 不触发）

## Phase A · L1 技术设计契约化（堵架构违规）

- [ ] A1 `x-tech-design`：模板与 SKILL.md 增加 `tech-design.contract.yaml` 产出，定义 `DNN → modules / public_interface / allowed_deps / forbidden_deps` 与 `schema_authority`
- [ ] A2 `x-spec/scripts/validator.py`：contract schema 校验（编号唯一、路径存在、`forbidden_deps` 与 `allowed_deps` 无交集）
- [ ] A3 `x-req/scripts/req.py` + `xdev.py validate`：影响文件树 ⊆ `contract.modules`，越界退回 x-tech-design
- [ ] A4 `x-verify/scripts/verify.py`：Gate① 新增第 7 项设计一致性对账（文件树、公开接口登记、DNN 覆盖、forbidden_deps 静态 import 检查）
- [ ] A5 `xdev.py archcheck`：从 `x-audit-arch` 下沉循环依赖、单一事实源重复定义、越界 import 三项机械检查
- [ ] A6 `x-tech-design/SKILL.md`：删除「不向 x-req 添加自动门禁」的自我限制，改写交接契约
- [ ] A7 回归：跑 `cases/` 现有 e2e 五个用例，确认已有 task 目录缺 contract 时按 1.0 门禁行为一致

## Phase B · L2 验证契约（堵用例漏写）

- [ ] B1 `x-tech-design`：模板新增「验证契约」段（`invariants` + `boundary_cases`，编号 `VC-NN`），并写入 contract
- [ ] B2 `x-req`：`dev-checklist.md` 表头新增 `验证契约` 列，行 = 场景回指 + VC 回指
- [ ] B3 `x-dev`：`dev-report` 为每个 VC 写 `kill:`（破坏实现会让哪个测试失败）
- [ ] B4 `x-qa-gate/references/r3-test-integrity.md`：从主观判断改为变异抽查指令（随机挑 VC、改坏实现、测试必须失败）
- [ ] B5 `xdev.py`：`kill` 抽查入口与结果记录，失败即 P0

## Phase C · L3 证据可复算（堵伪造结论）

- [ ] C1 `x-dev`：`dev-report` verify 块改为 evidence 包（`cmd` / `exit_code` / `stdout_sha256` / `captured_at` / `raw_log`）
- [ ] C2 `x-verify`：重跑全部 auto verify 块；完整套件按 1.1 比例随机抽样；比对 exit_code 与 stdout_sha256
- [ ] C3 `x-verify`：重跑失败与哈希不一致的分类输出（证据伪造 / 环境漂移 / 测试不稳定），前者直接 P0
- [ ] C4 `.evidence/` 落盘与清理规则，raw_log 保留策略

## 收尾

- [ ] D1 文档：`README.md` 主流程图与命令表、`README_zh.md`、`CLAUDE.md` 核心管线与 skill 契约表同步
- [ ] D2 `x-audit-arch/SKILL.md`：标注已下沉至 Gate① 的三项，剩余语义检查边界不变
- [ ] D3 三段提交：代码与测试 / skills / 仓库文档
