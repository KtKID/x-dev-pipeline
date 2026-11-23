# 实操：x-fix

你是执行管线的 agent。工作目录是调用方给你的项目副本，里面 `reports/cr/` 下有一份 CR 报告。

1. 完整阅读 `<管线仓库>/skills/x-fix/SKILL.md` 及它点名的文件，严格照做。校验脚本是 `<管线仓库>/skills/x-cr/scripts/validate_report.py`。测试命令：在项目副本根目录运行 `python3 -m pytest -q`。
2. 用户的请求是：“按 CR 报告修复。”
3. 不读管线仓库的 `evals/answers/` 和 `evals/runs/`。

最后一条消息给出回执。
