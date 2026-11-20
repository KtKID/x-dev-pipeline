# Spec 索引

每份 spec 一行。"拥有什么 / 不管什么"是判断新需求归属的唯一依据，规则见 [spec 范围](../../skills/x-explore-for-spec/references/spec-scope.md)。新建 spec 时同时加一行，随 spec 一起给用户确认。

| Spec | 状态 | 拥有什么 | 不管什么 |
|------|------|------|------|
| [path-link-smoke](./path-link-smoke/README.md) | 验证中 | spec 包内 `./...` 相对链接能否跳转 | spec 正文内容与格式校验 |
| [codex-session-metrics](./codex-session-metrics/spec.md) | 在用 | 从 Codex session JSONL 提取子 agent 的 Token 与耗时 | Claude session 的提取；评测打分 |
| [deepseek-acp-session-new](./deepseek-acp-session-new/spec.md) | 在用 | 编辑器经 ACP 创建 DeepSeek 空会话 | 已保存会话的恢复与后续对话 |
| [pipeline-self-evolution](./pipeline-self-evolution/spec.md) | 在用 | 运行证据、候选版本的评测、晋级与回滚 | 单次任务的开发与验收流程 |
| engineering（工程） | 待建 | 构建、依赖、CI、部署脚本 | 任何使用者能看到的行为 |
