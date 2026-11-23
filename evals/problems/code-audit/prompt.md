# 实操题：x-code-audit

调用方给你：skill 目录、项目副本路径（你的工作目录）、请求文件路径。

1. 读请求文件，里面是用户的原话。
2. 完整阅读 `<skill 目录>/SKILL.md` 和它点名的文件，严格照做。`audit.py` 在 `<skill 目录>/scripts/audit.py`，在项目副本根目录运行。
3. 派子 agent 时用 haiku 模型；派不了子 agent，就自己按单位逐个做。
4. 所有产出都在项目副本里。不读管线仓库的 `evals/`，不读项目副本旁边的 `.orig` 目录。

最后一条消息按 skill 的「交付」要求回复。
