## Why

iteration-6 的 `x-adversarial-risk` 是当前冻结基线：它直接读取整份风险示例卡，并依赖模型逐条判断适用性。这个路径已经能够补充 Scenario，但错题集增长后会持续增加上下文与读取成本，也缺少一个可独立验证的语义召回入口。

iteration-7 先完整复制 iteration-6 的全部 skills，再实现最小可行链路：由当前风险审查生成“功能关键词 + Risk”纯文本查询，代码把它与纯文本错题条目做向量相似度排序，直接返回 TopN 的错题 ID 和正文。第一阶段以成功召回一条错题为链路验收，再用一个已知查询验证预期错题进入 Top1。

## What Changes

- 以 iteration-6 的全部 skills 为基线建立 iteration-7，保留相同的目录结构与文件内容。
- 仅为 iteration-7 的 `x-adversarial-risk` 增加纯文本向量召回脚本。
- 将每条错题压缩为三个必要字段：稳定 ID、关键词、Risk。
- 错题 ID 统一使用 `AR-NNN`；检索代码把完整 ID 当作不透明 key。
- 将“关键词 + Risk”作为向量输入 value；错题集继续保存在一个 Markdown 文件中。
- 查询端使用相同的“关键词 + Risk”文本形态，默认返回 Top1，并支持 `--top-n`。
- Embedding 模型延迟加载并限制为本地文件；`Qwen/Qwen3-Embedding-0.6B` 已按固定 revision 下载到 iteration-7 独立目录并通过真实 Top1 Smoke。
- 相似度只用于程序内部排序；公开结果只返回 `id` 与 `text`。
- 检索阶段省去 LLM 精排、经验改写、向量数据库和二次文件读取。
- `x-adversarial-risk` 在进入对抗分析前调用召回脚本，并直接使用返回的错题正文构造风险反例。

## Capabilities

### New Capabilities

- `adversarial-risk-vector-retrieval`: 定义独立错题 key/value、纯文本向量匹配、最小 TopN 输出和风险审查接入行为。

### Modified Capabilities

无。

## Impact

- 冻结基线：`skills/x-pipeline-efficiency-workspace/iteration-6/skills/`。
- 主要目标：`skills/x-pipeline-efficiency-workspace/iteration-7/skills/x-adversarial-risk/`。
- 新增 iteration-7 的向量召回脚本与对应测试。
- 更新 iteration-7 的错题集、风险契约校验和 skill 执行说明。
- 新增本地 Embedding 运行接口与依赖说明；模型资产固定在 iteration-7 评估目录，运行代码保持离线加载。
- 当前 Spec、错题集和新来源统一使用 `AR-NNN`。
- OpenSpec apply 的实现改动全部落在 iteration-7；iteration-6 继续作为冻结基线。
