# Changelog

## v1.0.0

首个大版本：开发流程 v6 全链路（x-spec → x-req → x-dev → x-verify）定稿，x-qdev 单文档闭环与 flag 单写者一并交付。

### 开发流程 v6：spec 链路直达 verify

- **x-spec v6**：废除 lite/full 路由与 `spec_version: 3` 契约，改为纯功能性 spec——标题 + 概述 + `featNN` 列表，每个 feat 配 Given/When/Then 场景（正常/边界/异常三类必备），不写技术词汇；未拍板的默认值记入待确认清单。
- **x-req**：按 feat 分组拆 task，checklist 任务行以 `featNN 场景M` 回指 spec 场景（不复制 GWT），合并后全覆盖；行序即实现顺序，不建依赖图；风险列 `高:` 行要求真实链路验证。
- **x-dev**：单个 task 逐行 TDD（先测试后实现），场景 THEN 即断言；dev-report 只记验证结论（全绿或 N 个 🔴），不贴测试输出。
- **x-verify（Gate ①）**：从"运行 verify 引擎"改为交付对账——以 spec 场景为事实源核对回指有效性、行状态闭合、高风险行声明与结论一致性，问题按来源分诊退回，全部一致只输出回执。
- **边界**：本次只更新到 verify；Gate ②（x-qa-gate flag 台账）、x-fix 及确定性引擎脚本保持现状，既有 dev-checklist 状态标记（⏳/▶️/🟢/🔴）与 flag 引擎兼容。
- **新增模板**：`x-spec/templates/spec.md`（v6 格式）、`x-req/templates/dev-checklist.md`（回指表）、`x-dev/templates/dev-report.md`（结论式）。

### x-qdev v2：四段式 task 文档

- **一份文档闭环**：废除五学科流程（Q0-Q3 风险分流、Q2 reviewer 协议、状态机），改为"找 spec → 写 task 文档"单文档流，需求、失败测试、实现、验证结果四段依次完成。
- **先测试后实现**：测试用例先写并确认失败，实现让测试变绿；需求段用功能性语言，验证段只粘贴真实运行输出，收尾强制自检回执。
- **文档自检 gate**：交付前对 task 文档自身做五项对账（结构、回指有效、覆盖闭合、结论一致、边界核对），不依赖 x-spec/x-req/x-verify 等其他 skill 收口。
- **模板精简**：移除 `references/execution-rules.md`、`templates/README.md`、`templates/dev-report.md`，只保留 `templates/task.md`。

### flag 单写者与唯一 checklist

- **固定临时路径**：废除 UUID 临时文件协议，`flag` 主脚本与 benchmark 镜像改用固定同目录临时路径；内容无变化的目标跳过 checklist 临时文件，提交与恢复后清理全部 scratch 文件。
- **唯一 checklist**：每个 task 长期只保留一份 `dev-checklist.md`；P2 只登记不改任务状态，P0/P1 降级 `[!] 🔴`。
- **反例扩充**：新增 P2、重复 blocked、固定路径与恢复零残留测试（120 tests OK）。
- **版本统一**：package、Claude manifest/marketplace、Codex manifest 与 README 升级到 `1.0.0`。

## v0.5.2

### Codex 发布与确定性脚本打包

- **skill 自包含脚本**：确定性引擎按职责迁入各阶段 skill 的 `scripts/`；`x-dev` CLI 从相邻 skill 加载引擎，外部安装只需插件的 `skills/` 目录。
- **基准执行包**：`pipeline-efficiency-benchmark` 从各 skill 刷新扁平执行包，并校验 bundle 与所属源脚本的 SHA 一致性。
- **兼容预检**：Python 3.9 通过标准库目录识别执行包依赖，保持隔离 workspace 的预检可用。
- **版本统一**：package、Claude manifest/marketplace、Codex manifest 与 README 升级到 `0.5.2`。

## v0.5.1

### 用户级风险 RAG

- **跨项目默认语料**：`x-adversarial-risk` 与 `x-bug2rag` 默认读取用户 Home 下的 `~/.x-dev-pipeline/rag/risk-catalog.md`
- **独立初始化与导入**：新增 `home_corpus.py`，分别执行 `init` 和 `import-existing`，通过 `Path.home()` 统一解析各平台用户目录
- **受控写入**：`triage_store.py` 作为 LLM 写入接口，负责分配 `AR-NNN`、查重、格式化、严格校验和失败回滚
- **Codex 发布扩展**：受控白名单加入 `x-bug2rag` 及其脚本、规则和种子 corpus；模型与 Embedding 缓存保持原配置
- **版本统一**：`package.json`、Claude Code manifest、Claude marketplace、Codex manifest 与 README 全部升级到 `0.5.1`

## v0.5.0

### 发布更新

- **规范链路定版**：公开开发主链统一为 `x-spec → x-adversarial-risk → x-req → x-dev → x-verify → x-qa-gate → x-fix`
- **正式名称归位**：最新版 `x-spec` 与 `x-req` 使用稳定名称，迭代版本与历史 workspace 进入废弃或评测目录
- **Codex 发布边界**：Codex 插件仅发布产品 skill、必要运行脚本与插件元数据；评测入口、workspace、历史 skill、评测指标脚本和运行缓存退出发布包
- **版本统一**：`package.json`、Claude Code manifest、Claude marketplace、Codex manifest 与 README 全部升级到 `0.5.0`

## v0.3.6

### 发布更新

- **版本统一**：`package.json`、Claude Code manifest（`plugin.json` / `marketplace.json`）、Codex manifest 全部升级到 `0.3.6`
- **文档同步**：README 与 README_zh 的当前版本号、gate 命令说明更新到 v0.3.6

### Gate 执行结构改造（一轮列全 + 批量修 + 增量复审）

- **Gate ② 风险路由**：默认线 dispatch 一个综合 reviewer RC（新增 `references/rc-unified.md`，一次回答 spec/边界/测试真实性/任务边界四问）；高危改动（鉴权/不可逆写入/公开 API/并发等）保留 R1→R2→R3 三段串行，路由依据为 dev-report 新增的 `risk: default/high` 字段
- **一轮列全**：所有 reviewer（RC/R1/R2/R3）必须穷尽列出全部发现（F1..Fn 编号）后才判定，mini-report 强制覆盖声明 + 发现清单 + 穷尽声明；严重度 P0/P1/P2 统一定义收敛到 x-qa-gate SKILL.md
- **批量修**：x-fix 一次修完一轮发现清单（P0 全修且各固化一条可复跑反例、P1 修或豁免、P2 登记），产出逐条处置表 `fix-gate-r<轮次>-*.md`；废除旧"回 R1"4 条回流规则
- **增量复审**：fix 后尽量由同一个 reviewer 续审，只验证 F# 处置 + fix 增量 diff，配三条熔断（超出文件集扩范围 / 公开 API 定点契约对照 / 连续 2 轮新 P0 升级全量或 blocked）
- **fix-counter 语义变更**：按批量修轮数计（原按问题条数），上限 6 → **3 轮**
- **Gate ① 扩权**：x-verify 必跑清单 = dev-report 命令表 + task README Smoke/E2E 用例（manual 用例列入待人工验收）；x-req 验收用例要求优先命令化
- **门禁回执**：x-verify / x-qa-gate / x-fix 每节点结束强制在对话输出分级发现回执（P0/P1/P2 计数 + 拦截来源维度 + 处置 + 漏检计数），零发现也要报；报告文件降为存档

### qdev 风险分流

- **默认轻量闭环**：Q0/Q1 由主 agent 根据用户原始请求、实际 diff 和定向验证完成 DoD 证据闭环
- **按风险升级**：Q2 使用一个综合 reviewer，Q3 升级到 x-req → x-dev 完整门禁
- **独立 qdev 报告**：新增风险、实际结果和 DoD 证据矩阵模板，完整 gate 继续使用 x-dev dev-report schema
- **事实源优先级**：完整 QA 以用户原始请求、确认 spec 和既有公开契约优先，task 派生文档保留派生身份

## v0.3.5

### 发布更新

- **版本统一**：`package.json`、Claude Code manifest（`plugin.json` / `marketplace.json`）、Codex manifest 全部升级到 `0.3.5`
- **文档同步**：README 与 README_zh 的当前版本号与插件元数据说明更新到 v0.3.5
- **部署刷新**：执行 `install-codex.ps1` 将新版插件同步到 `~/.codex/plugins/x-dev-pipeline` 并更新三个 marketplace.json

## v0.2.0

### 发布更新

- **版本统一**：`package.json`、Claude Code manifest、Claude marketplace、Codex manifest 全部升级到 `0.2.0`
- **双层 gate 文档对齐**：README 主链路更新为 `x-dev -> x-verify -> x-qa-gate -> x-fix`
- **Claude / Codex 插件说明**：README 与 README_zh 明确列出 `.claude-plugin/`、`.codex-plugin/`、`.agents/plugins/marketplace.json` 三个入口
- **安装输出更新**：`install.sh` 命令清单更新到 v0.2 主命令、独立 audit、legacy alias
- **Codex 同步清理**：`install-codex.ps1` 同步时排除 `.xcodeatlas` 与 `.serena` 本地索引目录

## v0.1.3

### 新功能

- **并行开发支持**：`x-dev` 可通过 Agent 工具并行处理同优先级的独立任务，自动分析依赖关系并汇总结果
- **QA 检查列**：`x-plan` 生成的 dev-checklist 新增 🔍 质检列，对复杂/关键任务标记强制代码审查
- **一键安装脚本**：新增 `install.sh`，支持 `curl -fsSL ... | bash` 一行完成安装
- **持续开发自动循环**：`x-dev → x-cr → x-fix → x-cr → 下一任务` 全流程无需人工确认；仅 P0/P1 问题触发自动修复，手动调用各 skill 行为不变
