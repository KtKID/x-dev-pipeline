# Journal Index Recovery 完整流水线复核报告

## 结论

- 产品运行行为达到隐藏 rubric v2 的全部要求：21/21 行为断言通过，其中包含 5 项历史风险回归。
- 使用完整 workspace 内置 tools 布局复评分后，质量为 `100/100`，critical gate 通过。
- 当前归档目录直接复评分为 `88/100`；三个失败均由缺少 `workspace/tools/xdev.py` 引起，影响 spec、req、verify 三项可复现性断言。
- 新增对抗风险全部进入 Spec，部分测试只完成 Scenario ID 回指，语义断言仍有缺口。最终状态中的“37 个 Scenario 全部获得证据”属于结构覆盖结论。
- Agent tree 共消耗 `10,576,219` Token。该结果比 iteration-4 Terra 候选增加 `213.91%`，约为 `3.139` 倍；比 frozen baseline 减少 `48.71%`。

当前版本适合作为质量参考版本。Token 优化目标尚未达成，扩展风险的测试证据仍需补强。

## 完成质量

### 独立复跑

| 检查 | 结果 |
|---|---|
| `python3 -B -m unittest discover -s tests -v` | 20/20 通过 |
| `xdev.py validate docs/spec/journal-index-recovery --json` | 0 issues |
| `xdev.py validate .../tasks/implementation --json` | 0 issues |
| `xdev.py verify .../tasks/implementation --json` | 38/38 blocks 通过；37 Scenarios；manual 0；uncovered 0 |
| `xdev.py status` | T1–T5 全部 done |
| `xdev.py graph` | ready 0；blocked 0 |
| `risk_contract.py validate-spec` | valid |

### 隐藏评分 v2

rubric v2 将 AR-001～AR-005 写成独立行为断言，共 25 条、每条 4 分。

| 运行 | 分数 | Critical gate | 失败项 |
|---|---:|---|---|
| iteration-5 当前原始目录 | 88/100 | 失败 | 3 个 pipeline 断言缺少 `workspace/tools/xdev.py` |
| iteration-5 临时补齐 live `tools/` | 100/100 | 通过 | 无 |
| iteration-4 旧候选 | 88/100 | 失败 | dev-report 证据、AR-003、AR-005 |
| iteration-4 frozen baseline | 96/100 | 失败 | dev-report 证据 |

原始实现、测试、Spec、checklist 和 dev-report 在当前版本的两个口径中保持相同。
第二个口径只复原正式 runner 应提供的工具布局。

### 新增隐藏回归的区分结果

| 风险 | 当前版本 | 旧候选 | Frozen baseline |
|---|---|---|---|
| AR-001 compact replace 崩溃窗口 | 通过 | 通过 | 通过 |
| AR-002 语义非法 snapshot | 通过 | 通过 | 通过 |
| AR-003 物理完整、语义非法的尾记录 | 通过 | **失败：返回 `RECOVERY_REQUIRED`，期望 `CORRUPT_LOG`** | 通过 |
| AR-004 失败 request_id 可复用 | 通过 | 通过 | 通过 |
| AR-005 七类公开错误契约 | 通过 | **失败：语义非法尾记录仍返回错误分类 6** | 通过 |

这组结果把 baseline 的额外发现转成了正式质量差异：旧候选在新 rubric 下比
frozen baseline 少 8 分，当前版本修复后通过全部五项。

### QA 与修复价值

独立 Q3 reviewer 消耗 `249,306` Token，发现两项 P1：

1. 非字符串 `op` 会触发未捕获类型错误。
2. snapshot 请求历史缺少按 seq 的完整状态机重放校验。

第 1 轮 x-fix 修复两项问题，加入聚焦反例，并完整复跑 20 个测试和 38 个 verify blocks。隐藏运行时断言随后全部通过。

## 对抗 Scenario 的真实证据强度

| Scenario | 来源 | 证据评价 |
|---|---|---|
| SC_29 | AR-001 compact replace 窗口 | 交付测试覆盖核心恢复路径；隐藏 grader 补充旧 request replay |
| SC_30 | AR-002 语义非法 snapshot | 交付测试覆盖三种非法 snapshot；隐藏 grader 补充命令矩阵与文件字节保持 |
| SC_31 | AR-003 逻辑非法尾记录 | 交付测试覆盖 expected_version 非法与 recover 只读；隐藏 grader 补充普通命令分类 |
| SC_32 | AR-004 失败 request_id 可复用 | 交付测试与隐藏 grader 均覆盖核心语义 |
| SC_33 | AR-005 完整错误契约 | 交付测试覆盖 3 类；隐藏 grader 覆盖参数错误与 6 类命名错误 |
| SC_34 | 首次 replay 标记 | 核心语义覆盖完整 |
| SC_35 | missing/tombstone 读取 | Store 层覆盖；CLI exit/schema 证据较弱 |
| SC_36 | 并发相同 request | 测试先提交 request，再并发重试；缺少首次并发竞争、一个 false/其余 true、单 record 断言 |
| SC_37 | compact 期间读取 | 启动多个进程；缺少确定性重叠、live+tombstone 完整状态和前后状态一致性断言 |

重点证据缺口：

- SC_36 的首次并发幂等竞争。
- SC_37 的确定性 compact/read 重叠。

SC_30、SC_31、SC_33 的交付测试矩阵仍可增强；隐藏 grader v2 已从外部验证其
关键行为。SC_35 仍有 CLI 证据强度问题。当前 `100/100` 代表 rubric v2 满分。

## Token 消耗

### Agent tree 总量

| 指标 | Token |
|---|---:|
| Input | 10,489,177 |
| Cached input | 10,218,240 |
| Output | 87,042 |
| Reasoning output | 29,117 |
| Total | **10,576,219** |

缓存输入占 input 的 `97.42%`，占总 Token 的 `96.62%`。主要成本来自累计上下文在多轮工具调用后的重复进入。

### 阶段分布

| 阶段 | Token | 占比 |
|---|---:|---:|
| x-spec3 初版 | 450,928 | 4.26% |
| x-adversarial-risk | 960,376 | 9.08% |
| live skill/tool 读取与 x-req3 | 2,591,564 | 24.50% |
| x-dev 实现与测试 | 1,522,619 | 14.40% |
| dev-report 与 Gate① | 361,173 | 3.41% |
| Gate② 主线程编排 + Q3 reviewer | 1,367,399 | 12.93% |
| x-fix、完整复验与最终报告 | 3,322,160 | 31.41% |

### 与既有 Terra 运行对比

| 运行 | 质量 | Token | 相对本次 |
|---|---:|---:|---:|
| iteration-4 frozen baseline | 96（rubric v2） | 20,619,230 | 本次减少 48.71% |
| iteration-4 candidate | 88（rubric v2） | 3,369,225 | 本次增加 213.91% |
| iteration-5 当前运行 | 100（规范化 rubric v2） | 10,576,219 | — |

当前版本比 frozen baseline 高 4 分，比旧候选高 12 分；Token 达到旧候选的
3.139 倍。

### 最大消耗来源

1. x-fix、完整复验和报告：`3.322M`。
2. x-req 前读取 live skill 与工具源码：`2.592M`。执行器完整读取了 2265 行 `xdev.py`、588 行 `req3.py`、446 行 `verify.py`、713 行 `req.py`，其中 req3/verify 发生重复读取。
3. x-dev 实现与测试：`1.523M`。
4. QA 编排：`1.367M`。Q3 reviewer 自身只有 `249k`，主线程等待和处理回执消耗约 `1.118M`。
5. 对抗检查：`960k`。

主线程两轮共 75 次工具调用，Q3 reviewer 5 次，agent tree 合计 80 次。每个串行工具回执都让增长后的上下文再次进入模型。

## 审计限制

- continuation 按用户要求沿用 Spec turn，上下文包含第一轮完整 Spec 和工具历史。
- 后半程读取的是仓库 live skill 和 tools；运行时 `x-dev/SKILL.md`、`x-qa-gate/SKILL.md`、`tools/req3.py` 位于 dirty worktree，缺少独立冻结快照。
- 当前 workspace 未内置完整 tools，因此原目录无法独立复现隐藏 pipeline 断言。
- `tools/xdev.py` 存在于仓库 live tools 和 iteration-4 两个完整 runner 中。iteration-5
  最初按 Spec-only 范围建包，继续扩展为完整流水线时遗漏了 tools 快照。这属于
  runner 输入包装错误，造成 12 分可复现性损失；产品行为断言保持 21/21。
- task 目录残留一个 `.dev-checklist.md.flag-*.tmp`，内容为 QA 标记期间的中间 checklist。
- Q3 修复后的关闭由主线程依据聚焦反例和完整 Gate①完成，独立 reviewer 只执行初审。

## 下一轮门槛

1. 补强 SC_36、SC_37，并增强 SC_30、SC_31、SC_33、SC_35 的交付测试证据。
2. runner 冻结 skill、tools、题面和 hash，workspace 内携带完整可执行工具。
3. skill 指示执行器直接运行 tools；源码读取只在命令失败且需要诊断时触发。
4. validator 提供 summary 模式，避免把 38 个完整 block 结果重复送入上下文。
5. QA reviewer 使用一次阻塞等待，主线程停止生成轮询消息。
6. 使用新线程一次完成完整流水线，连续运行三次。

晋级目标：隐藏 rubric v2 `100/100`、新增对抗 Scenario 语义缺口为 0、单次总 Token 不超过 `3,200,763`。
