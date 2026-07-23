# Journal Index Recovery 端到端开发任务

当前目录是一份完整、隔离的开发工作区。任务输入位于：

- `task/00-overview.md`
- `task/01-record-and-state.md`
- `task/02-recovery-and-compaction.md`
- `task/03-cli-and-concurrency.md`
- `task/specs/`
- `fixture/`

完成本地 journal/index 的全链路实现，并用当前工作区提供的 x-dev-pipeline 完成规格、任务拆解、开发和事实验证。

执行约束：

1. 依次使用 `skills/x-spec3`、`skills/x-req3`、`skills/x-dev`、`skills/x-verify`；风险路由需要时继续使用工作区内的 `skills/x-qa-gate` 与 `skills/x-fix`。
2. 只读取当前工作区内的 skill、题面、规范、fixture 与代码。基础文件和 shell 工具可用于读取、编辑、运行和验证。
3. 实现范围位于 `fixture/backend/`；`task/` 与 `fixture/README.md` 作为只读输入。
4. 运行过程只使用 Python 标准库、本地文件和本地进程；保持环境完全自包含。
5. 规范留白采用最小安全假设，并在 spec 的判断依据中显式记录。题面已授权在文档中记录假设，因此持续完成交付。
6. 将 pipeline 文档写入 `docs/spec/journal-index-recovery/`，将实现与测试留在工作区，完成可复跑验证。
7. 最终回复列出产物路径、测试命令、结果和仍需人工确认的风险。

