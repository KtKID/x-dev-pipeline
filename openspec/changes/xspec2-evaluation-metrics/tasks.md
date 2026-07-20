# xspec2-evaluation-metrics Tasks

## 0. 前置门禁

- [x] 0.1 确认 `openspec status --change xspec-v2` 为 Complete，现有 x-spec2 skill、eval 1 与 workspace 目录可读；记录当前 `git rev-parse HEAD`
- [x] 0.2 冻结首版 schema 与范围：Codex、fresh 单-turn、显式 session 文件、session duration、真实 token、独立 grading；人工等待与全 pipeline 指标保持延后
- [x] 0.3 保存 iteration-1 的 benchmark/metrics 文件哈希，确保实现与 pilot 运行不回写历史代理指标

## 1. Commit A：工具与测试

- [x] 1.1 先建立 Codex rollout 与子 agent timing 最小 fixture/失败 fixture：累计 token 多快照、多个 turn、缺 token、缺或多个 task_complete、通知字段缺失、JSON 损坏、时间戳非法、多个 session ID
- [x] 1.2 新增 `test/test_metrics.py`，覆盖最后累计快照、provider total 原样使用、通知 total/duration、duration 复算、prompt hash、grading 汇总、隐私字段排除与退出码
- [x] 1.3 实现 `tools/metrics.py extract`：读取显式 rollout 或 timing、eval metadata 与 grading，输出统一 `measurement.json`
- [x] 1.4 实现确定性落盘：同目录临时文件、flush/fsync、原子替换、稳定 key 顺序；相同输入重复生成字节一致
- [x] 1.5 实现 rubric 输入边界校验：metadata 明确列出 executor inputs 与 grader-only inputs，两者重叠或记录 rubric exposure 时退出 1
- [x] 1.6 实现 `aggregate-spec2`：按 `(eval_id, run_number)` 配对，校验 prompt/model/repo 一致，输出真实 quality/token/duration、delta、样本数和 pilot 标志
- [x] 1.7 跑 `python3 -m unittest discover -s test` 与 metrics 正反 fixture；提交代码与测试切片

## 2. Commit B：x-spec2 eval 协议与 pilot

- [x] 2.1 新增 x-spec2 eval 运行说明：executor 只收 prompt 与题目输入，grader 独立持有 expectations；collector 在两个被测 session 结束后运行
- [x] 2.2 修正 eval 1 输入清单，移除向 executor 暴露 rubric 的文件；metadata 增加 configuration、run_number、executor inputs、grader-only inputs
- [x] 2.3 从同一 source snapshot、同一模型并行启动 eval 1 的一条 fresh `with_skill` 子 agent 与一条 fresh `without_skill` 子 agent；每个 agent 只接收一个 eval task
- [x] 2.4 独立评分两臂输出，生成各自 `grading.json`；确认评分规则与生成输入分离
- [x] 2.5 两个子 agent 完成后解析与其一一对应的显式 rollout；通知直接提供统计时也可保存 `timing.json`。主 agent 收尾执行 `extract` 生成两份 `measurement.json`，复核 session/agent ID、repo SHA、prompt hash、真实 total token 与 duration
- [x] 2.6 运行 `aggregate-spec2` 生成新 iteration 的 `benchmark.json` / `benchmark.md`，确认 `pilot: true`、每臂样本数 1、time 非代理值、tokens 非 output chars
- [x] 2.7 使用 skill-creator 的 `eval-viewer/generate_review.py` 生成静态 review HTML，人工核对两臂输出、formal grades 与 benchmark；提交 skill/eval 协议和 pilot 产物切片

## 3. Commit C：仓库文档

- [x] 3.1 更新 `CLAUDE.md`：记录 `tools/metrics.py` 边界、fresh-session 纪律、collector 不入样本与退出码
- [x] 3.2 更新 `README.md` / `README_zh.md`：增加 x-spec2 pilot metrics 的命令、最小字段和单样本解释边界
- [ ] 3.3 提交仓库文档切片；历史 task、x-spec2 产物模板与 validator 文档保持原样

## 4. 交付验证与验收

- [ ] 4.1 复跑 `python3 -m unittest discover -s test`、extract 幂等性测试、aggregate 幂等性测试与 `git diff --check`
- [x] 4.2 运行 `openspec validate xspec2-evaluation-metrics --type change --strict` 与 `openspec validate --all --strict`
- [ ] 4.3 交付两条 session ID、两份 measurement、paired benchmark、静态 review 页面、三段提交记录及所有偏离说明
- [ ] 4.4 用户确认 pilot 数据与展示口径后再归档 change；确认前保持 active
