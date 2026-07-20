# x-spec2 evaluation metrics pilot evidence

日期：2026-07-20

## Paired run 身份

两臂使用同一 prompt hash、模型、仓库 source snapshot 和 12 条 grader-only 断言。executor 未收到 rubric 文件或 expectations。

| configuration | source ID | model | repo SHA |
|---|---|---|---|
| with_skill | `019f7b44-606e-70b0-87d6-1533d95e3bdc` | `gpt-5.6-sol` | `5a63f0e4a83349a01c81e262e980ad058252298e` |
| without_skill | `019f7b44-95e1-7d01-8687-5328af42d3fb` | `gpt-5.6-sol` | `5a63f0e4a83349a01c81e262e980ad058252298e` |

共同 prompt hash：`sha256:9362a7d42d99092396e857721db1cefd9f390737cb0074f23758b5dfa3be2d6a`

## 实测结果

| metric | with_skill | without_skill | delta |
|---|---:|---:|---:|
| 独立断言通过率 | 10/12，83.33% | 4/12，33.33% | +50 个百分点 |
| provider total token | 654,880 | 448,691 | +206,189，约 +46.0% |
| session duration | 590.930 s | 475.935 s | +114.995 s，约 +24.2% |

`with_skill` 独占通过三文件/spec2 产物形态、用户原话追溯、六元组覆盖、Requirement↔Module 闭合、J/D 消费纪律和动态模型集中承载六类契约断言。两臂共同通过低延迟预算、播放打断、跨端可观测和波动恢复四类动态行为断言。

`with_skill` 的两个失败项：

1. U1 的 StackChan/ESP32-S3 平台要求落到模块总览，缺少对应的真实且唯一 Requirement。
2. 六元组覆盖表给出了真实落点，缺少逐项适用理由和可验证证据字段。

本结果是每臂一条 run 的 pilot，只证明隔离、采集、评分与聚合链路成立。

## 验证命令

- `python3 -m unittest test.test_metrics -v`：14/14 通过。
- `python3 tools/xdev.py validate .../with_skill/run-1/outputs --json`：exit 0，type `spec2`，0 issue。
- `python3 tools/xdev.py validate .../without_skill/run-1/outputs --json`：exit 0，type `capability`，0 issue。
- 两次 `extract` 与 `aggregate-spec2` 前后 SHA-256 完全一致，派生产物字节稳定。
- `openspec validate xspec2-evaluation-metrics --type change --strict`：通过。
- `openspec validate --all --strict`：8/8 通过。
- `python3 tools/xdev.py validate openspec/changes/xspec2-evaluation-metrics --json`：0 issue。
- `git diff --check`：通过。

## 已知环境偏离

- `python3 -m unittest discover -s test` 共运行 109 项，102 通过、7 失败。失败均来自当前工作区已删除的 `skills/x-req/templates/README.md`、`dev-checklist.md` 与 `diagram.md`；metrics 相关 14 项全部通过。本 change 保持这些用户迁移文件原样。
- 系统 `python3` 为 3.9.6，skill-creator viewer 需要现代类型语法；改用已安装的 Python 3.12 成功生成静态 review。
- viewer 读取 iteration-1 时被其中缺少 `eval_id` 的 round-trip 目录触发排序错误；最终静态 review 仅嵌入 iteration-2，未带历史输出对照。
- `skills/x-spec2-workspace/` 受仓库 `.gitignore` 保护；pilot 产物保持本地评测工作区，提交需要显式 `git add -f` 授权。
