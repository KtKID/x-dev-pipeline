## 0. 前置门禁

- [x] 0.1 核对旧 task 退役决策与当前 req3/verify 引擎边界
- [x] 0.2 盘点 `xdev.py` 顶层所有者、测试直接引用、benchmark bundled runtime 和共享 dirty tree
- [x] 0.3 本 change 通过 `openspec validate xdev-orchestrator-slimdown --strict`

## 1. 引擎拆分

- [x] 1.1 新增 `tools/validator.py`，迁移 package 识别、V1-V7/V13-V20 与 spec 级覆盖
- [x] 1.2 新增 `tools/flag.py`，迁移 flag 输入、ledger、状态降级和可恢复双文件事务
- [x] 1.3 将当前 task `instructions` 委托给 task 引擎自身 ARTIFACTS

## 2. xdev 薄路由器

- [x] 2.1 重写 `tools/xdev.py`，仅保留 argparse、discover、task/package 分类和引擎分流
- [x] 2.2 删除 V8-V12、旧 README/Checklist 校验、旧 status/graph/scaffold/instructions 与无调用包装
- [x] 2.3 将 `tools/xdev.py` 控制在 400 行以内，并保持当前 CLI 命令、JSON 顶层字段和退出码

## 3. 测试与分发

- [x] 3.1 将 package/flag 测试改为直接验证单一引擎所有权
- [x] 3.2 删除旧 task 专属测试，新增历史路径拒绝和 req3 instructions 回归
- [x] 3.3 更新 benchmark executor tools 清单、manifest、哈希和 preflight

## 4. 验证与收口

- [x] 4.1 运行 spec3/req3/verify/flag 定向测试
- [x] 4.2 运行全量 unittest、benchmark 测试、`git diff --check`
- [x] 4.3 strict validate OpenSpec change，记录前后行数、模块所有权与验证证据

## 5. req3 单引擎收口

- [x] 5.1 将 req3 所需的通用 checklist、状态与依赖图能力内聚到 `tools/req3.py`
- [x] 5.2 删除 `tools/req.py`、spec2/req2 task 路由及其测试
- [x] 5.3 从 benchmark bundled runtime 和目标项目 tools 删除 `req.py`
- [x] 5.4 复跑 req3 定向测试、全量测试、bundle preflight 与 strict OpenSpec 校验
