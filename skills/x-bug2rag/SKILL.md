---
name: x-bug2rag
description: |
  把 bug 描述沉淀到用户 Home 下的通用 RAG，形成可召回的失败机制经验，并维护可扩展到数千条的聚合 corpus。输入一条或多条 bug 描述，按泛用性规则筛选后写入；也能初始化 `~/.x-dev-pipeline/rag`、复制插件已有 catalog、把单文件 catalog 聚合为 taxonomy、短卡搜索视图、JSONL 机器索引和稳定 Markdown 分片，重建/校验索引，并按 AR-ID 批量读取详情。用户说"这个 bug 记一下""沉淀到错题库""这条经验加进 RAG""bug 转 corpus""初始化用户 RAG""聚合错题库""给 RAG 分片""重建风险目录/索引"时使用；从 x-cr 报告、复盘记录、issue 列表批量提取经验时也使用。
  单文件与聚合模式的写入、校验、目录生成、短卡搜索、TopN、详情读取和重建全部由本 skill 自己完成，便于独立测试聚合效果。
---

# x-bug2rag · bug → RAG 经验沉淀

把"一次性 bug"转成"可召回的失败机制"。错题库记的不是 bug 本身，而是 bug 暴露的**失败机制**：触发条件 + 错误实现长什么样 + 正确实现长什么样 + 可观察差异。这种结构跨项目可复现，召回后能直接构造对/错实现的最小反例。

## 记什么 / 不记什么

错题库是召回素材，不是 bug tracker。一条经验值得记，当且仅当它能脱离具体项目，被未来的 spec/代码 review 召回并直接用于构造反例。

### 值得记（同时满足）

1. **是失败机制，不是一次性事件**：能说清"在什么场景下、错实现长什么样、对实现长什么样、两者可观察差异是什么"。
2. **跨项目可复现**：把项目名、库名、具体业务名词换掉，经验依然成立。
3. **落入泛用类别之一**（详见 `references/triage-rules.md`）：

   | 类别 | 典型失败机制 |
   |---|---|
   | 状态机 | 恢复只校验形状不校验转换、状态跳跃、非法历史态被接受 |
   | 并发/时序 | 重试与首次并发、消息乱序、读写交错、部分失败 |
   | 幂等/唯一 | 重试产生重复副作用、键冲突、去重漏网 |
   | 边界/默认值 | 空集合、单元素、off-by-one、默认值被绕过 |
   | 权限/越权 | 身份切换后权限残留、横向越权、共享状态污染 |
   | 资源生命周期 | 超时分支漏清理、句柄泄漏、资源耗尽 |
   | 持久化一致性 | 多阶段提交中断、索引与正文不一致、崩溃恢复窗口 |
   | 数据敏感 | 日志/错误信息泄漏 PII、secret 进日志、错误码可枚举 |

### 抛弃信号（任一命中即弃）

- **纯领域事实**：业务规则、API 限额、产品约束——这是 spec 该写的，不是经验。
- **一次性运维/环境 bug**：磁盘满、机器挂了、配置手抖——不可重述，召回不到。
- **编程常识**：判 null、边界检查、基本类型转换——LLM 自己会，浪费召回预算。
- **时效性强、易腐烂**：某库升级后行为变了、某版本特定 bug——半年后召回到反而是误导。
- **补不齐必填字段**：场景/错误实现/正确实现/可观察差异任一无法说清——召回素材不完整，等于没记。

## corpus 条目格式

每条 `## AR-NNN`，字段顺序固定。前三位补零，条目超过 999 后自然增长为 `AR-1000`。ID 由脚本自动分配，LLM 不手写。

```text
## AR-NNN
关键词：<召回语义锚点，3-6 个，逗号分隔>
Risk：<一句具体失败机制，主语+条件+后果>
场景：<触发条件、上下文、前置状态>
错误实现：<常见错误做法长什么样>
正确实现：<对的实现长什么样>
可观察差异：<错实现 vs 对实现的可观察区分点>
分类：<上述 8 类之一>
来源：<项目/报告/issue，可选>
```

字段必须自包含：召回后 LLM 只读这一段就能构造反例，不需要再翻原 bug。Risk 句禁止空泛（"可能有 bug""要小心"），必须落到具体机制。

## 用户级默认 corpus

所有平台都通过 Python 的 `Path.home()` 定位用户 Home，默认 corpus 固定为：

```text
~/.x-dev-pipeline/rag/risk-catalog.md
```

新用户设置分成两个独立操作。第一步只创建用户 RAG 目录：

```bash
BUG2RAG_SKILL_DIR="<当前已加载的 x-bug2rag/SKILL.md 所在目录>"

python3 "${BUG2RAG_SKILL_DIR}/scripts/home_corpus.py" init --json
```

第二步把插件已有 `risk-catalog.md` 原样复制到用户目录：

```bash
python3 "${BUG2RAG_SKILL_DIR}/scripts/home_corpus.py" \
  import-existing \
  --json
```

`import-existing` 默认从同一插件的
`x-adversarial-risk/references/risk-catalog.md` 读取。目标文件已有相同内容时返回
`copied: false`；目标文件已有其他内容时停止覆盖。测试新用户流程时用
`--home <temporary-home>` 隔离真实用户数据。

## 两种 corpus 存储模式

### 单文件模式

`risk-catalog.md` 保存全部 `## AR-NNN`。适合小语料，由 `triage_store.py` 直接追加。

### 聚合目录模式

数百到数千条经验使用以下结构：

```text
risk-corpus/
├── manifest.json
├── taxonomy.md
├── indexes/
│   ├── all.md
│   ├── all.jsonl
│   ├── locator.jsonl
│   ├── <route>.md
│   └── <route>.jsonl
└── shards/
    ├── risk-000001-000200.md
    └── risk-000201-000400.md
```

- `shards/*.md` 是事实源，每个分片默认容纳 200 个 ID 区间。
- `taxonomy.md` 是给 LLM 全量读取的一级路由目录。
- `indexes/<route>.md` 是给 LLM 检查候选范围的二级短卡搜索视图。
- `indexes/<route>.jsonl` 是机器索引，同一 ID 可以出现在多个路由索引中。
- `indexes/locator.jsonl` 把稳定 ID 映射到 `shard + section`。
- `manifest.json` 固定 schema、条目数、分片大小和生成文件清单。

聚合只改变物理存储。检索、引用、去重和读取继续以单条 `AR-ID` 为单位。

## 五轮执行契约

### 第 1 轮：读取

批量读取：

1. 本 `SKILL.md`。
2. 用户输入的全部 bug 描述（一条或多条）。
3. 默认读取 `~/.x-dev-pipeline/rag/risk-catalog.md`；调用方给出 `--target` 时读取该目标。聚合目录读取 `taxonomy.md` 和相关二级索引，了解已有条目并避免重复。

### 第 2 轮：判断

逐条 bug 完成判断，每条给出：

| 字段 | 内容 |
|---|---|
| bug 摘要 | 一句话还原用户输入的故障 |
| 判定 | 通过 / 抛弃 |
| 命中类别 | 通过条目填上述 8 类之一；抛弃条目填命中了哪个抛弃信号 |
| 理由 | 一句话：通过条目说明它泛用在哪个失败机制上；抛弃条目说明为什么不可召回 |
| 字段草稿 | 通过条目预填关键词/Risk/场景/错误实现/正确实现/可观察差异/分类/来源 |

边界用例参考 `references/triage-rules.md`，里面给出每类的进/弃对照例子。判断阶段不写盘。

### 第 3 轮：集中写入

当前已加载的 `x-bug2rag/SKILL.md` 所在目录是 `BUG2RAG_SKILL_DIR`。每条通过项调用一次 `triage_store.py`。默认目标是用户 Home 下的 `~/.x-dev-pipeline/rag/risk-catalog.md`；调用方可用 `--target` 覆盖。脚本根据目标类型选择单文件追加或聚合目录追加：

```bash
BUG2RAG_SKILL_DIR="<当前已加载的 x-bug2rag/SKILL.md 所在目录>"

python3 "${BUG2RAG_SKILL_DIR}/scripts/triage_store.py" \
  --keywords "<关键词，逗号分隔>" \
  --risk "<一句失败机制>" \
  --scene "<触发条件与上下文>" \
  --wrong "<错误实现>" \
  --correct "<正确实现>" \
  --observable "<可观察差异>" \
  --category "<8 类之一>" \
  --source "<来源，可选>" \
  --json
```

单文件目标由本 skill 的 rich-card parser 校验；目录目标自动转交同目录的 `corpus_aggregate.py append`，同步更新分片、taxonomy、索引和 manifest。`--target` 接受显式单文件或聚合目录。默认路径由 `home_corpus.py` 通过 `Path.home()` 解析，与调用项目 cwd 和操作系统无关。

脚本负责：分配下一个连续 `AR-NNN`、按字段顺序格式化、校验八类路由、追加到 corpus 末尾、调用本 skill 的 corpus contract 校验、校验失败自动回滚。

`triage_store.py` 的拒绝情况按脚本回执处理，不自行改盘：

- 缺必填字段 → 补齐后重试，或降级为抛弃并说明。
- Risk 文本与已有条目重复 → 视为已沉淀，回执记为"已存在"而非新存。
- 校验失败且回滚 → 把脚本返回的 issue 原样上报，不修复 corpus。

写入命令固定使用 `python3`，由当前环境解释器执行；脚本只调用当前 `x-bug2rag` 目录内的代码。

### 第 4 轮：验证

全部写入完成后，对目标 corpus 跑一次整体验证。单文件运行：

```bash
python3 "${BUG2RAG_SKILL_DIR}/scripts/corpus_aggregate.py" validate-flat \
  --target "<risk-catalog.md>" \
  --json
```

`valid: true` 才算本轮成功。出现 issue 时上报，不自行编辑 corpus 修复。

聚合目录运行：

```bash
python3 "${BUG2RAG_SKILL_DIR}/scripts/corpus_aggregate.py" validate \
  --target "<risk-corpus-directory>" \
  --json
```

该验证从分片重算所有生成文件，并检查 taxonomy、二级索引、locator、manifest、ID 唯一性、Risk 去重和分片内容一致性。

### 第 5 轮：回执

向用户报告：

- **存入**：列出每条的 `AR-NNN`、Risk 摘要、命中类别。
- **抛弃**：列出每条的 bug 摘要、命中的抛弃信号、一句话理由。
- **去重**：Risk 文本已存在的，单独列出并标"已存在（AR-NNN）"。
- corpus 最终路径和总条目数。
- 验证结果（通过 / 失败 + issue）。

回执后结束本轮。单文件模式只修改目标文件；聚合模式只修改目标目录中的 manifest、taxonomy、indexes 和 shards。

## 聚合维护流程

### 1. 从单文件建立聚合 corpus

```bash
python3 "${BUG2RAG_SKILL_DIR}/scripts/corpus_aggregate.py" build \
  --source "<risk-catalog.md>" \
  --target "<risk-corpus-directory>" \
  --shard-size 200 \
  --json
```

目标目录必须尚未存在。脚本先完整解析和去重，再一次写出全部事实分片与生成索引。

### 2. 读取一级目录并搜索二级索引

完整读取 `<risk-corpus-directory>/taxonomy.md`，从当前问题提取对象、动作、失败机制、触发条件和可观察结果，选择全部相关 route。使用本 skill 的确定性短卡搜索，字段权重为 Risk、关键词、可观察差异、场景、分类：

```bash
python3 "${BUG2RAG_SKILL_DIR}/scripts/corpus_aggregate.py" search \
  --target "<risk-corpus-directory>" \
  --routes authorization boundary-default \
  --query "<对象、动作、失败机制、触发条件、可观察结果>" \
  --top-n 5 \
  --json
```

搜索先合并多个 route、按稳定 ID 去重，再对二级短卡统一排序。输出只包含 `id + score + summary + locator + text`，LLM 此时看到的是短卡。

路由不明确时省略 `--routes`，进入全库短卡搜索。

需要检查路由合并后的完整候选集合时运行 `select`，输出一个去重后的临时 Markdown 搜索视图：

```bash
python3 "${BUG2RAG_SKILL_DIR}/scripts/corpus_aggregate.py" select \
  --target "<risk-corpus-directory>" \
  --routes authorization boundary-default \
  --output "<temporary-directory>/selected.md" \
  --json
```

### 3. 按命中 ID 批量读取完整经验

```bash
python3 "${BUG2RAG_SKILL_DIR}/scripts/corpus_aggregate.py" read \
  --target "<risk-corpus-directory>" \
  --ids AR-006 AR-127 AR-308 \
  --json
```

脚本保持请求顺序、按 ID 去重，并只返回指定 section 的完整正文。

### 4. 从分片重建生成文件

```bash
python3 "${BUG2RAG_SKILL_DIR}/scripts/corpus_aggregate.py" rebuild \
  --target "<risk-corpus-directory>" \
  --json
```

`shards/*.md` 是重建事实源。重建会重新生成 taxonomy、全部二级索引、locator 和 manifest。

## 关键约束

- 判断的是"失败机制的泛用性"，不是"bug 的严重程度"。严重但不泛用的 bug 不进 corpus。
- 一条 bug 可能提炼出多条失败机制：拆开判断、拆开写入。
- 一条 bug 也可能提炼不出任何失败机制：直接抛弃，不强凑。
- 不猜测用户没说的字段。场景/错误实现/正确实现/可观察差异说不清的，要么回问用户，要么抛弃。
- 不为通过而通过：宁可全抛弃，也不写入空泛的"要小心并发"这类废话条目。
- 默认 corpus 固定使用用户 Home 下的 `.x-dev-pipeline/rag/risk-catalog.md`；显式 `--target` 只覆盖当前调用，不触发工作区扫描。
