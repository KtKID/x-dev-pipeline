# Changelog

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
