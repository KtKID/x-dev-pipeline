# 风险错题集

本文件只供 `x-adversarial-risk` 在 deep/full 对抗性检查或录入已确认缺口时读取。每项保存可迁移的事故模式与最小反例。

## AR-001: 多文件 compact 替换窗口丢失已提交 mutation

- 确认状态：confirmed
- 类型：implementation-defect
- 动作维度：先原子替换 snapshot，再清空或替换 journal，把一次提交拆成两个文件动作
- 数据维度：snapshot 状态、journal mutation、全局 seq 与幂等请求历史
- 场景维度：compact 已替换新 snapshot、尚未替换旧 journal 时进程崩溃，随后重启并追加 mutation
- 被破坏不变量：任何已确认 mutation 在 compact 任一崩溃点后仍可恢复，seq 和 request history 保持单调一致
- 最小反例：构造含 seq 1..N 的旧 journal，写入覆盖至 N 的新 snapshot 后保留旧 journal 并重启，再提交 seq N+1
- 应补 Scenario：系统识别与 snapshot 重叠的旧 journal 前缀，只重放合法后缀，重启后不丢失新 mutation
- 来源证据：`skills/x-pipeline-efficiency-workspace/iteration-4/eval-11-journal-index-recovery/baseline/run-1/workspace/docs/spec/journal-index-recovery/tasks/implementation/reports/qa-gate/qa-gate-report-20260723-165135.md`

## AR-002: 只校验 snapshot 结构而接受语义不可能状态

- 确认状态：confirmed
- 类型：implementation-defect
- 动作维度：信任 JSON 与字段类型合法的 snapshot，省略 request history 和状态机重放校验
- 数据维度：keys、tombstone、version、request fingerprint、首次结果与 last_seq
- 场景维度：服务启动或 recover 读取已提交 snapshot
- 被破坏不变量：snapshot 的 key 状态、版本和请求历史必须能由合法 mutation 序列重放得到
- 最小反例：提供结构合法的 snapshot，其中空状态包含一次成功 delete 的 request result，或 request seq 与 key version 冲突
- 应补 Scenario：启动逐项重放并比对 snapshot 语义；无法由合法历史生成的状态返回 `CORRUPT_SNAPSHOT` 且文件保持只读
- 来源证据：`skills/x-pipeline-efficiency-workspace/iteration-4/eval-11-journal-index-recovery/baseline/run-1/workspace/docs/spec/journal-index-recovery/tasks/implementation/reports/qa-gate/qa-gate-report-20260723-170018.md`

## AR-003: 把物理完整但逻辑非法的末条记录当作可恢复尾部

- 确认状态：confirmed
- 类型：implementation-defect
- 动作维度：只按 UTF-8、JSON、字段和 CRC 判断尾记录完整性，把状态机失败归入可截断尾部
- 数据维度：journal record、seq、key version、operation 和状态转换
- 场景维度：服务启动或 recover 处理 journal 最后一条记录
- 被破坏不变量：物理完整的已提交记录只能按语义接受或判定日志损坏，recover 不得删除完整记录
- 最小反例：在健康 journal 末尾追加 CRC 正确、字段完整但 seq 跳跃或状态转换非法的记录
- 应补 Scenario：最后一条物理完整但语义非法的记录返回 `CORRUPT_LOG`，全部命令保持 journal 字节不变
- 来源证据：`skills/x-pipeline-efficiency-workspace/iteration-4/eval-11-journal-index-recovery/baseline/run-1/workspace/docs/spec/journal-index-recovery/tasks/implementation/reports/qa-gate/qa-gate-report-20260723-170018.md`

## AR-004: 失败请求未证明不会污染幂等历史

- 确认状态：confirmed
- 类型：evidence-gap
- 动作维度：mutation 失败后只检查数据和 journal 未变化，省略复用同一 request_id 的独立断言
- 数据维度：request_id、输入 fingerprint、首次结果、key version 与 journal
- 场景维度：missing delete 或 stale expected_version 失败后，调用方修正输入并重试
- 被破坏不变量：未提交请求不得进入幂等历史，失败 request_id 能用于后续合法提交
- 最小反例：先以 request_id R 执行 missing delete 或 stale put，再以同一 R 和合法 expected_version 提交 mutation
- 应补 Scenario：第一次失败保持 request history 未占用，第二次合法请求成功并生成唯一新 seq
- 来源证据：`skills/x-pipeline-efficiency-workspace/iteration-4/eval-11-journal-index-recovery/baseline/run-1/workspace/docs/spec/journal-index-recovery/tasks/implementation/reports/fix-blocked-report.md`

## AR-005: 错误响应只检查 code 而遗漏完整对外契约

- 确认状态：confirmed
- 类型：evidence-gap
- 动作维度：测试只断言退出码或 error.code，省略 `ok:false`、字段集合和 message 类型
- 数据维度：CLI JSON 错误对象、错误码、message 与退出状态
- 场景维度：参数错误、缺失数据、版本冲突和持久化损坏的命令响应
- 被破坏不变量：每个失败响应保持稳定 JSON schema、规定 code、字符串 message 和对应退出码
- 最小反例：实现返回正确 code 与退出码，同时省略 `ok:false`、增加泄漏字段或把 message 返回为非字符串
- 应补 Scenario：对每类错误精确断言顶层字段、error 字段、code、message 类型和退出码
- 来源证据：`skills/x-pipeline-efficiency-workspace/iteration-4/eval-11-journal-index-recovery/baseline/run-1/workspace/docs/spec/journal-index-recovery/tasks/implementation/reports/fix-blocked-report.md`
