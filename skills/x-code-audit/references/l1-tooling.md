# L1 机器检查

**不读业务代码。** 只回答三件事：工具配了没有、规则全不全、现在跑一遍过不过。lint 和类型检查能管的规范，交给它们管；它们没配，就报“该配”，不让 AI 去代替。

全部由 `audit.py l1` 做，主 agent 不派子 agent。

## 脚本做什么

1. 按配置文件找工具：
   - Python：`pyproject.toml` 的 `[tool.ruff]` / `ruff.toml` / `.flake8` / `setup.cfg`（lint），`[tool.mypy]` / `mypy.ini`（类型检查），`[tool.black]` 或 ruff format（格式化）
   - JS / TS：`eslint.config.*` / `.eslintrc*`（lint），`tsconfig.json`（类型检查），`.prettierrc*` 或 `package.json` 里的 prettier（格式化）
   - Go：`.golangci.yml` / `.golangci.yaml`；`go vet` 总是可用
2. 对照下面的基础规则清单，看配置里缺哪几条。
3. 看 CI（`.github/workflows/*.yml`、`.gitlab-ci.yml`）里有没有跑这些工具。
4. 真跑一遍：只跑范围内的文件，记下命令、退出码、报错条数和前几条位置。
5. 机器上没装的工具：记“没装”，写怎么装，这一项算未完成，不算通过。

## 基础规则清单

项目缺了这些，就报一条 P2“该加哪条规则”。

| 语言 | 必须有 | 对应配置 |
|---|---|---|
| Python | 未使用的导入和变量、未定义的名字 | ruff 的 `F`（或 flake8 默认） |
| Python | 命名规范 | ruff 的 `N` |
| Python | 函数太复杂 | ruff 的 `C90`，并设 `max-complexity` |
| Python | 类型检查 | mypy 有配置 |
| TS | 严格类型 | `tsconfig.json` 的 `strict: true` |
| TS | 未使用的变量和参数 | `noUnusedLocals`、`noUnusedParameters`，或 eslint `no-unused-vars` |
| TS | 命名规范 | eslint `@typescript-eslint/naming-convention` |
| TS | 函数太复杂 | eslint `complexity` |
| Go | 静态检查 | golangci-lint 启用 `staticcheck`、`unused` |
| 所有 | 格式化 | 有格式化工具配置 |
| 所有 | CI 里跑 lint 和类型检查 | CI 配置里能找到命令 |

## 怎么对到问题

- 工具没配、缺规则、CI 没跑：每个缺口一条 P2。
- 跑出报错：每个工具一条问题，写报错条数和前 3 个位置；类型错误和“会出错”的 lint 规则（未定义名字等）算 P1，纯风格算 P2。
