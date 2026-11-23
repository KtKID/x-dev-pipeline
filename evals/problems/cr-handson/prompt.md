# 实操题：x-cr / x-fix

调用方给你三样东西：管线仓库路径、项目副本路径（你的工作目录）、题目编号。

1. 读 `<管线仓库>/evals/problems/cr-handson/cases/<题目>/request.md`，里面写了这一阶段用哪个 skill，以及用户的原话。调用方说这一阶段是 x-fix 时，读同目录的 `request-fix.md`。
2. 阶段是 x-cr：完整阅读 `<管线仓库>/skills/x-cr/SKILL.md` 和它点名的 references，严格照做。
   阶段是 x-fix：完整阅读 `<管线仓库>/skills/x-fix/SKILL.md` 和它点名的文件，严格照做。
3. 校验脚本是 `<管线仓库>/skills/x-cr/scripts/validate_report.py`；测试命令是在项目副本根目录运行 `python3 -m pytest -q`。
4. 所有改动都在项目副本里做。不读管线仓库的 `evals/answers/`、`evals/runs/`，不读 `cases/<题目>/` 下除 request.md、request-fix.md 以外的文件，不读项目副本旁边的 `.orig` 目录。

最后一条消息给出 skill 要求的交付内容（x-cr：报告路径和 P0/P1/P2 数量；x-fix：回执）。
