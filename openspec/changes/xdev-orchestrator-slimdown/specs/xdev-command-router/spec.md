## ADDED Requirements

### Requirement: 薄 CLI 模块边界

`tools/xdev.py` SHALL 只拥有命令参数解析、包发现、目标分类和引擎分流。包校验 SHALL 由 `tools/validator.py` 单一实现，QA issue 事务 SHALL 由 `tools/flag.py` 单一实现，spec3 SHALL 由 `tools/spec.py` 实现，req3 task SHALL 由 `tools/req3.py` 实现，verify SHALL 由 `tools/verify.py` 实现。`tools/xdev.py` 的物理行数 SHALL 不超过 400 行。

#### Scenario: xdev 保持薄入口

- **GIVEN** 当前仓库已完成引擎模块拆分
- **WHEN** 统计 `tools/xdev.py` 并检查其顶层函数
- **THEN** 文件不超过 400 行，且不含 V 规则实现、checklist parser、拓扑算法或 flag 事务函数

#### Scenario: 每类实现只有一个模块所有者

- **GIVEN** validator、flag、spec、req3 和 verify 引擎均可导入
- **WHEN** 测试检查 validator、flag、spec、req3、verify 的公开实现
- **THEN** 对应函数存在于所属引擎，且 `xdev.py` 只持有引擎模块引用和路由函数

### Requirement: 当前 CLI 分流保持

统一入口 SHALL 保留 `validate`、`instructions`、`scaffold`、`status`、`graph`、`verify`、`flag` 命令。spec3 包 SHALL 进入 spec 引擎；其他当前包 SHALL 进入 validator；spec3 task SHALL 进入 req3 引擎；verify 和 flag SHALL 进入各自引擎。成功、校验失败、用法或 IO 失败 SHALL 继续使用退出码 0、1、2。

#### Scenario: package validate 分流

- **GIVEN** 一个合法 spec3 包和一个合法 change 包
- **WHEN** 分别校验合法 spec3 和 change 包
- **THEN** 返回对应包类型，规则输出与拆分前一致

#### Scenario: task 命令分流

- **GIVEN** 一个合法 req3 task
- **WHEN** 对合法 req3 task 调用 instructions、scaffold、validate、status、graph 或 verify
- **THEN** 命令进入 req3 引擎，并保持既有 JSON 顶层字段和退出码

#### Scenario: spec2 task 被拒绝

- **GIVEN** 一个父 spec 未声明 `spec_version: 3` 的 task
- **WHEN** 对父 spec 未声明 `spec_version: 3` 的 task 调用当前 task 命令
- **THEN** 命令以用法错误退出，并说明只支持 spec3 task

#### Scenario: flag 分流

- **GIVEN** 一个包含当前 checklist 和 issue ledger 的合法 task
- **WHEN** 对合法当前 task 调用 flag
- **THEN** `flag.py` 完成 issue ledger 与状态降级事务，输出字段与拆分前一致

### Requirement: 隔离运行时依赖完整

所有分发 `xdev.py` 的 bundled runtime SHALL 同时分发其直接 import 的本地引擎。manifest SHALL 记录每个文件的哈希，workspace preflight SHALL 在执行任务前验证清单和 import 完整性。

#### Scenario: bundled workspace 可加载

- **GIVEN** executor-tools manifest 与源工具哈希一致
- **WHEN** benchmark 将 executor tools 复制到隔离 workspace 并执行 preflight
- **THEN** `xdev.py`、`validator.py`、`flag.py`、`spec.py`、`req3.py`、`verify.py` 均存在、哈希匹配且可 import

#### Scenario: 缺少拆分模块时提前失败

- **GIVEN** bundled runtime 清单声明全部必需引擎
- **WHEN** bundled runtime 缺少 validator.py 或 flag.py
- **THEN** preflight 在调用 xdev 命令前以可操作错误终止
