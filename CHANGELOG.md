# Changelog

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
