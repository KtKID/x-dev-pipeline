## 1. 前置门禁

- [x] 1.1 将 iteration-6 的全部 28 个 skill 文件原样复制到 iteration-7
- [x] 1.2 使用目录 diff 验证 iteration-7 初始 skills 副本与 iteration-6 完全一致
- [x] 1.3 核对 iteration-7 目标文件和工作区未提交改动，确认实现只修改指定 iteration-7 slice
- [x] 1.4 完成 proposal、design、capability spec，并通过 `openspec validate adversarial-risk-vector-retrieval-mvp --strict`
- [x] 1.5 记录实现提交边界：代码与测试、skill 与错题集、OpenSpec 文档分别提交

## 2. 错题最小格式

- [x] 2.1 将 iteration-7 的五条风险卡压缩为 `AR-001` 起始的 ID、关键词和 Risk
- [x] 2.2 更新 `risk_contract.py` 的错题 parser 与校验规则，要求唯一 `AR-NNN`、非空关键词和非空 Risk
- [x] 2.3 删除 v1/v2 与 namespace 兼容分支，Scenario 来源统一为 `rag:AR-NNN`
- [x] 2.4 增加 parser 回归测试，覆盖合法记录、重复 ID、缺关键词、缺 Risk 和稳定顺序

## 3. 向量召回 CLI

- [x] 3.1 新增 `scripts/risk_retrieve.py`，实现 `query --catalog --keywords --risk --top-n --json`
- [x] 3.2 接入延迟加载的 `sentence-transformers` 与默认模型 `Qwen/Qwen3-Embedding-0.6B`，使用 `local_files_only=True`、查询侧 `query` 提示模板和两侧归一化 Embedding
- [x] 3.3 实现内部相似度排序与 ID 平局排序，公开输出只保留 `matches[].id` 和 `matches[].text`
- [x] 3.4 实现退出码 0/1/2 与固定 JSON 错误结构
- [x] 3.5 为单元测试提供可注入的假 Embedding 后端，覆盖默认 Top1、TopN、TopN 超过语料数、排序和最小字段

## 4. Skill 接入

- [x] 4.1 更新 iteration-7 的 `x-adversarial-risk/SKILL.md`，在对抗分析前生成“功能关键词 + Risk”查询并调用召回 CLI
- [x] 4.2 删除整份错题集逐卡检查、LLM 精排、经验改写和二次读取相关指令
- [x] 4.3 更新对抗审查记录与回执，记录召回 ID、复用或新增 Scenario 和 CLI 结果
- [x] 4.4 更新 iteration-7 的 skill README 或依赖说明，记录安装命令、模型名、本地文件模式和缓存边界
- [x] 4.5 更新 iteration-7 的 `x-spec3` 交接说明，进入向量召回链路

## 5. 验证

- [x] 5.1 运行离线 parser、CLI 和风险契约单元测试
- [x] 5.2 下载并校验本地 `Qwen/Qwen3-Embedding-0.6B` 后执行已知日志恢复查询，确认 Top1 为 `AR-003`
- [x] 5.3 在 iteration-7 运行 `test_adversarial_risk.py`，确认 v3 与 `AR-NNN` 单一契约
- [x] 5.4 运行 skill quick validation、`openspec validate adversarial-risk-vector-retrieval-mvp --strict` 和 `git diff --check`
- [x] 5.5 审计最终 diff，确认 iteration-6 保持冻结，功能变更只包含目标 iteration-7 slice、测试、依赖说明和本 OpenSpec change
