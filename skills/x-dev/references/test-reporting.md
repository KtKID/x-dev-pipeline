# 证据约定

x-dev、x-qdev、x-fix 共用。交付只看一份文件：常规 task 是 `dev-checklist.md` 末尾的「结果」节，qdev 是 task 的⑤。原始输出放证据目录，不另写测试报告或 dev-report。

| 对象 | 交付文档 | 证据目录 |
|---|---|---|
| 常规 task | `docs/spec/<spec>/tasks/<task>/dev-checklist.md` | `<task>/evidence/` |
| qdev | `docs/spec/<spec>/tasks/<task>.md` | `tasks/<task>-evidence/` |

## 「结果」里写什么

- **用例对应表**：`用例 | 测试位置 | 层级 | 结果`。一个用例一行，测试位置写到函数（`path::name`，多个用顿号分隔），层级写 unit / smoke / 集成 / e2e / 人工，结果写 通过 / 人工通过 / 失败。人工验证的测试位置指向证据目录里的记录文件（步骤、实际看到的结果、结论）。
- **覆盖率一行**：由 `xdev coverage` 写入，不手填。
- **问题与处置**：卡住的行、改过的测试及原因、加了覆盖率排除标记的 `文件路径:行` 及理由、QA issue 的处置（issue-N · 严重度 · 怎么修的 · 哪条反例测试），各一行。没有写“无”。
- 多 agent 协作时再加「派工记录」，见 [多 agent 协作开发](parallel-dev.md)。

不写过程叙述，不复制测试输出；要看原始输出就去证据目录。

## 覆盖率

`xdev coverage` 只管“本次改动的代码行”：和「代码基线」（`xdev start` 记下的 commit）相比，新增或改过的代码行，加上还没提交的新文件。测试文件、`docs/`、`evals/`、`reports/` 和非代码文件（md、json、yaml 等）不算。要求 100%，不到就补测试。

它做三件事：真的运行 `--cmd` 给的测试命令（日志存 `evidence/test-run-N.log`），读 `--report` 给的覆盖率报告，把结果写进 `evidence/coverage.json` 和「结果」的覆盖率一行。`xdev check` 只认用 `--cmd` 跑出来、测试通过、跑完之后代码没再改的记录。

覆盖率到 100% 只说明代码被跑到了，不说明测试真的在测。之后还要做 [测试真实性检查](test-integrity.md)，回执存为证据目录里的 `test-integrity.md`，`xdev check` 会读它。

常用命令（报告格式自动识别）：

| 语言 | `--cmd` | `--report` |
|---|---|---|
| Python | `python3 -m pytest --cov=<包> --cov-report=json:.cov/coverage.json` | `.cov/coverage.json` |
| JS / TS（Jest、Vitest） | `npx vitest run --coverage --coverage.reporter=lcov` | `coverage/lcov.info` |
| Go | `go test ./... -coverprofile=.cov/cover.out` | `.cov/cover.out` |
| Java（JaCoCo → Cobertura）、其他 | 能出 Cobertura XML 或 lcov 的命令 | 对应文件 |

多个语言时 `--cmd`、`--report` 各给多次。报告文件放进 `.gitignore`，别让它算成改动。`--cmd` 跑的必须是本 task 的全量测试加既有回归，不是只跑新测试。

排除标记（Python `# pragma: no cover`、JS `/* istanbul ignore */`、`c8 ignore` 等）只用于确实跑不到的防御代码。`xdev coverage` 会列出改动行里新加的排除标记，`xdev check` 要求「问题与处置」里有一行写着这个文件路径和理由，审查时再看理由是否成立。

计入覆盖率的语言按扩展名判断（Python、Go、JS/TS、Java、Kotlin、Rust、C/C++、Ruby、PHP、C#、Swift、Shell 等）。没有覆盖率工具的语言（比如 Shell 脚本）改动后会显示“报告里没有”：能用 kcov 之类的工具出 Cobertura 报告就加进 `--report`；实在没有，在「问题与处置」写 `文件路径 理由`，`xdev check` 认这一行，审查判断理由是否成立。

## Web 与界面验收

涉及 Web 的任务，agent 在实现后、交付前亲自用浏览器打开本次改动的版本，操作受影响的关键流程，按验收条件核对实际结果；后端改动影响页面时也验证页面操作；只有 Web API 的需求可以在浏览器里发请求核对响应。发现问题就修复，再用修复后的版本复验失败场景和受影响流程。

最终版本通过后截图，存为 `evidence/screenshot-<页面或操作>.png`。浏览器验收的页面地址、操作步骤、实际结果、复验情况写成 `evidence/browser-<用例>.md`，在用例对应表里作为该用例的测试位置，结果写“人工通过”。其他程序界面改动，打开最终版本截图，同样存证据目录。验收或截图受阻时，记为未完成并写明原因。
