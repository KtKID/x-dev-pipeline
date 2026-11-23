# 实操：x-cr

你是执行管线的 agent。工作目录是调用方给你的项目副本（里面有 `docs/spec/loan/`、`src/`、`tests/`）。

1. 完整阅读 `<管线仓库>/skills/x-cr/SKILL.md` 及它点名的 references，严格照做。校验脚本是 `<管线仓库>/skills/x-cr/scripts/validate_report.py`。
2. 用户的请求是：“x-cr 检查一下 src/library/loan.py 的续借和查借阅，先别改代码。”
3. 报告写到项目副本的 `reports/cr/` 下，跑校验脚本直到通过。
4. 不读管线仓库的 `evals/answers/` 和 `evals/runs/`。

最后一条消息给出报告路径和 P0/P1/P2 各几条。
