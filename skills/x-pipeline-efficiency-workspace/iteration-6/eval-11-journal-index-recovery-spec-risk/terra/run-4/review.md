# journal-index-recovery Terra run-4 评估

## 结论

固定 spec-risk grader 得分为 **65/100，11/17 passed**。当前 iteration-6 `validate-review` 通过，返回 0 issues。两者的差异来自 validator 只检查结构、评分、来源格式和 catalog 映射；固定 grader 继续检查五个 case-specific 语义锚点与 run-summary 字段。

## AR-001..005

| 风险 | 语义覆盖 | 固定 grader 结果 | 机械未命中原因 |
|---|---|---:|---|
| AR-001 compact 替换窗口 | SC_17 覆盖 snapshot 已提交、旧 `events.log` 仍保留、重启去重旧前缀及下一次 seq=N+1，语义覆盖完整。 | fail | 固定 grader 要求同一 AR-001 Scenario body 同时包含 `snapshot`、`journal`、`崩溃`；SC_17 使用 `events.log` 表达 journal，缺少字面量 `journal`。 |
| AR-002 snapshot 语义一致性 | SC_09、SC_13、SC_14 覆盖 snapshot 重放、损坏已提交 snapshot 的 `CORRUPT_SNAPSHOT`、compact 后状态保留；风险审查记录把“结构合法但语义不可能”判为不适用。 | fail | 最终 Spec 没有 `adversarial-review (AR-002; ...)` Scenario。固定 grader 只在对抗新增场景中查找 `snapshot` + `CORRUPT_SNAPSHOT`。 |
| AR-003 完整但语义非法 journal | SC_18 构造 CRC/字段形状完整且 seq 跳跃的末条记录。 | fail | SC_18 将结果定义为 `RECOVERY_REQUIRED` 并允许 recover 截断；固定 grader 要求 `CORRUPT_LOG`。这是直接语义分歧。 |
| AR-004 失败 request_id 重用 | SC_19 覆盖 `VERSION_CONFLICT` 后复用同一 request_id 并成功提交。 | fail | 固定 grader 要求同一 AR-004 Scenario 同时出现 `request_id`、`NOT_FOUND`、`VERSION_CONFLICT`；SC_19 缺 `NOT_FOUND` 路径。 |
| AR-005 完整公开错误响应 | SC_08 精确约束顶层键、`error.code`、字符串 `message` 和退出码 2–8，语义主体覆盖充分。 | fail | SC_08 来源仍为 `initial-spec`，固定 grader 只检查对抗来源 Scenario；正文使用“顶层键/退出码”，评分器字面要求“顶层字段/message/exit”。 |

第六个失败项是 run-summary 缺少 `skills_read`。事件轨迹确认 x-spec3 与 x-adversarial-risk 均完整读取；摘要 schema 漏写该字段。

## 七维覆盖

| 维度 | 结论 | 证据 |
|---|---|---|
| journal | 部分覆盖 | SC_01、SC_02、SC_10、SC_11 覆盖 CRC、durable append、物理尾损坏和非尾损坏；SC_18 对完整语义非法末条的分类与固定 grader 冲突。 |
| snapshot | 部分覆盖 | SC_09、SC_12、SC_13、SC_14 覆盖重放、临时文件、已提交损坏和压缩保留；AR-002 语义不可能 snapshot 场景缺失。 |
| 幂等 | 部分覆盖 | SC_05、SC_06、SC_14、SC_19 覆盖成功回放、指纹冲突、compact 保留和版本失败后复用；`NOT_FOUND` 后复用缺失。 |
| 崩溃恢复 | 通过 | SC_10、SC_11、SC_17、SC_20 覆盖可恢复尾部、非尾损坏、compact 中间窗口和健康 recover 幂等。 |
| compact | 通过 | SC_14 固定写临时文件、flush/fsync、replace、目录 fsync 与清空 log 顺序；SC_17 覆盖替换窗口。 |
| 进程并发 | 通过 | SC_15 覆盖不同 key 无丢失、成功 seq 唯一、同 key/expected_version 恰一成功。 |
| 后续完整 pipeline 交接 | 部分覆盖 | Spec 提供 Scenario、测试层和 TDD 顺序，run-summary 声明 `ready-for-x-req3`；完整 `x-req3 → x-dev → x-verify → x-qa-gate` 交接状态与消费约束未记录。 |

## 轨迹与资源

- 新 thread/session：`019f9005-7563-7632-9204-dfe735703132`，inherited turns 为 0。
- Terra 自行按 complexity 5 将预算升级为 full，并读取 x-adversarial-risk；对抗阶段为 1 次读取、1 次集中 patch、1 次 validate、1 次回执。
- 整个 turn 共有 12 次工具调用：8 次 command execution、4 次 file change；rollout 含 24 个 reasoning item 和 8 条 agent message。
- Token：input 416,213，其中 cached 362,496、uncached 53,717；output 24,629，其中 reasoning 6,648；input+output 440,842。
- 时长：528.075 秒。过程中出现 4 次重连消息和 1 次 WebSocket → HTTPS fallback，任务最终完成。

## 下降原因

1. x-adversarial-risk 允许复用现有 Scenario，固定 grader 只把 `adversarial-review` 来源纳入 AR 命中；AR-005 因来源保留 `initial-spec` 丢分。
2. Terra 把 AR-002 判为证据不足，把 AR-003 的语义非法末条归入可恢复尾部；两项直接偏离固定 rubric。
3. AR-001 与 AR-005 含较强语义覆盖，固定 grader 采用精确关键词，术语差异造成机械丢分。
4. AR-004 只覆盖 `VERSION_CONFLICT`，遗漏 `NOT_FOUND` 失败后的 request_id 重用。
5. run-summary 的交付 schema 未要求 `skills_read`，固定 grader继续检查该字段。
6. 当前 validator 的通过范围止于通用结构契约，case-specific 五项语义仍依赖固定 grader。

该 run 证明风险路由、结构门禁和主要存储契约保持有效；晋级线仍被 snapshot 语义、完整 journal 语义分类、失败幂等全路径、AR 来源协议和摘要 schema 阻断。
