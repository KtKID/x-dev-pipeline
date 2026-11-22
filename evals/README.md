# evals：管线的评测

这个目录放管线 skill 的评测：题目、答案、评分脚本，以及每次运行留下的记录。

## 目录里有什么

```text
evals/
├── README.md                 # 本文件
├── evals.json                # 全部评测的登记表：名字、题面、评分方式
├── problems/<eval>/          # 题面：答题 agent 只能读这里和题面里点名的规则文件
├── answers/<eval>/           # 答案与考点：只给评分脚本和评审看，答题 agent 不读
│   └── INDEX.md              # 每条设计规则测哪些题、每道题考什么
├── runs/<eval>/              # 运行记录，按测试目的分目录
│   ├── HISTORY.md            # 这组题每一轮的分数和发生了什么
│   └── iteration-N/run-M/
│       ├── answer.json       # 答题 agent 交的答案
│       └── grading.json      # 评分脚本当时打的分（逐题对错、错在哪个字段、答题理由）
├── scripts/                  # 评分、汇总和准备脚本
└── x-pipeline-efficiency-workspace/   # 旧链路的 token 效率实验（见文末）
```

## 怎么查看结果

先看汇总，再看细节：

```bash
python3 evals/scripts/runs_summary.py              # 每组题最近一轮的分数
python3 evals/scripts/runs_summary.py --all        # 全部轮次
python3 evals/scripts/runs_summary.py spec-scope   # 一组题的全部轮次
```

- 想知道某组题为什么改过、哪轮错在哪：看 `runs/<eval>/HISTORY.md`。
- 想看某次运行具体错了哪题：看 `runs/<eval>/iteration-N/run-M/grading.json`，`rows` 里 `ok: false` 的就是错题，`wrong` 写着期望值和实际值，`reason` 是答题 agent 自己给的理由。
- 想知道一道题考什么：看 `answers/INDEX.md` 或 `answers/<eval>/rubric.md`。

分数是按当时的题目和答案算的。之后修过的题，老分数不再重算，所以早期轮次的分数会比现在低，这是正常的。

## 判题类评测（检查规则能否被准确执行）

题目项目是一个虚构的图书馆借阅系统。每组题考一份规则文件：

| eval | 题数 | 测什么 | 规则来源 |
|---|---|---|---|
| spec-scope | 20 | 需求写进哪几份 spec：加到已有、新建、只记变更，还是问用户 | `skills/x-ask-spec/references/spec-scope.md` |
| qdev-spec-routing | 17 | 留在 qdev 还是转主线、task 放哪、要不要停下给用户确认、技术设计写在哪 | `skills/x-qdev/SKILL.md`、`skills/x-qdev/references/risk-rules.md` |
| change-sync | 7 | spec 变了，哪些 D、T、任务行、测试要改、新增、退役、重开或重跑 | `skills/x-tech-design/references/change-sync.md` |
| qdev-confirm-check | 6 | x-verify-spec 能否发现"改了场景却没记用户确认" | `skills/x-verify-spec/SKILL.md` |
| req-grouping | 7 | 并行组怎么分：按任务量定组数，不为并行而拆 | `skills/x-req/SKILL.md` |
| dev-worker | 12 | 工人子 agent 遇到越界情况怎么做；约束只是任务的一部分 | `skills/x-dev/references/parallel-dev.md` |
| dev-main | 14 | 主 agent 在多 agent 协作里的下一步 | `skills/x-dev/references/parallel-dev.md` |
| td-confirm | 6 | tech-design 不需要用户确认，只有会改变结果的取舍单独问 | `skills/x-tech-design/SKILL.md`、`skills/x-req/SKILL.md` |
| dev-delivery | 18 | 看到 xdev coverage / check / 功能检查的结果后下一步做什么；不再另写测试报告 | `skills/x-dev/SKILL.md`、`skills/x-dev/references/test-reporting.md`、`skills/x-qdev/SKILL.md`、`skills/x-verify-spec/` |
| ask-spec | 12 | 需求讨论时会不会主动复述、追问，何时才写 spec，超过 5 个 feat 怎么分期 | `skills/x-ask-spec/SKILL.md` |
| feature-check | 17 | 便宜的模型能不能凭清单识破功能漏做多做和假测试、又不误报 | `skills/x-verify-spec/references/feature-check.md` |
| verify-route | 22 | 验收怎么走：哪种 risk 做功能检查、严重度、哪些交给定期巡检、回执存几份、修完怎么关闭；架构约束怎么处理 | `skills/x-verify-spec/`、`skills/x-tech-design/SKILL.md`、spec 模板「关键约束」 |

规则里能机械判断的部分（编号引用、文件交集必须同组、依赖无环、risk 计算、需求变化同步清单）由脚本负责，测试在 `test/test_checklist_engine.py`，不需要 LLM 判题。

**怎么跑一轮**

1. 改了上表里的规则文件后，对应那组题要重跑。新开一个轮次目录：`evals/runs/<eval>/iteration-N/run-1/`、`run-2/`。
2. 派便宜模型（如 haiku）的子 agent 当答题者，每组至少跑 2 次。提示词写：完整阅读 `evals/problems/<eval>/prompt.md` 并照做，只读它列出的文件，不读 `evals/answers/` 和 `evals/runs/`，答案写到 `evals/runs/<eval>/iteration-N/run-M/answer.json`。
3. 评分并保存：

   ```bash
   python3 evals/scripts/grade.py <eval> evals/runs/<eval>/iteration-N/run-M/answer.json
   python3 evals/scripts/grade.py <eval> evals/runs/<eval>/iteration-N/run-M/answer.json --json > evals/runs/<eval>/iteration-N/run-M/grading.json
   ```
4. 在 `runs/<eval>/HISTORY.md` 加一行：这一轮的分数、错题，错题是规则的问题还是题目的问题、改了什么。
5. 新增或修改了规则，就在 `answers/INDEX.md` 登记它对应的题。

评分是确定性的：答案按集合比较，新建 spec 或新增 D/T 的名字不限，只要不和已有编号重名。

## 实现类评测

### x-dev 交付冒烟测试

每次修改 `skills/x-dev/` 后跑一遍「待办清单只看已完成」。任务只执行 x-dev 阶段。独立执行器读取公开题面和当前工作区的 x-dev，评分脚本留在执行目录外。

环境需有可登录的 Codex CLI、Python 3、Node.js、可由 `require('playwright')` 加载的 Playwright 及其 Chromium。Playwright 已装在其他目录时，用 `NODE_PATH` 指向对应 `node_modules`。

```bash
bash evals/scripts/run_x_dev_receipt.sh
```

结果在命令打印的 `evals/x-dev-receipt-runs/run-…/` 中。先看 `receipt.md` 和其中的截图，再看 `grading.json`。评分脚本独立在浏览器操作筛选和恢复，并核对回执中的文件、函数名和截图附件。说明是否通俗、截图是否拍到对应状态由人对照回执检查。

CLI 无法连接时，可用同一命令加 `--prepare-only` 生成并校验独立输入。让无历史上下文的执行器在生成的 `workspace/` 中按 `PROMPT.md` 完成任务，把它的原始最终回复存为 run 目录下的 `receipt.md`，再执行 `node evals/answers/x-dev-receipt/grade.cjs <run-dir>`。

### 其他实现题

`evals.json` 里的 voice-chain-end-to-end（完整管线端到端实现语音链路）、journal-index-recovery（本地日志恢复）、ledger-audit（CSV 流水审计）是不绑定单个 skill 的实现题，题面在 `problems/<eval>/PROMPT.md`，评分在 `answers/<eval>/`。

⚠️ voice-chain-end-to-end 的评分（`answers/voice-chain-end-to-end/evaluate.py` 的 `verify_evidence`）和 `skills/pipeline-efficiency-benchmark/assets/executor-tools/` 里的工具包还停在旧链路：要求 dev-report 和 `xdev verify`。现行流程（checklist「结果」+ `xdev check`）下跑它会误判，先刷新工具包并把这一项改成 `xdev check` 再用。

### DeepSeek Harness ACP 配对评测

使用同一份真实 Harness 源码和 [ACP 题面](problems/deepseek-acp/PROMPT.md)，对比冻结版与当前 pipeline。考生在干净工作区实现 ACP 服务；评审独立验收运行行为、阶段交接和 Token。准备命令、评分与预算见 [操作协议](answers/deepseek-acp/BENCHMARK.md)（评审侧）。


## x-cr 评测记录

`runs/x-cr/iteration-1/` 是 x-cr 四组评测的一次 dry-run 记录，汇总在其中的 `summary.md`。题目在 `skills/x-cr/evals/evals.json`。

## 旧链路的 token 效率实验

`x-pipeline-efficiency-workspace/` 是 `skills/pipeline-efficiency-benchmark` 的结果目录，记录的是旧链路（x-spec3 → x-req3 → x-dev → x-verify）在 voice-chain 题上的 token 优化实验，入口见其中的 `README.md` 和 `final-report.md`。被测的旧 skill 已经不在 `skills/` 里，这些结果只作历史参考。
