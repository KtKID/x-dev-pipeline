## 1. 前置门禁

- [x] 1.1 检查活跃 OpenSpec、现有 skill 契约和工作区未提交改动，确认采用独立 capability 与显式风险版本标记
- [x] 1.2 完成 proposal、design、capability spec，并通过 `openspec validate add-x-adversarial-risk --strict`

## 2. 代码与测试

- [x] 2.1 实现只读标准库脚本 `risk_contract.py`，覆盖 Spec 评分、预算、状态、审查记录和 Scenario 来源校验
- [x] 2.2 为 `risk_contract.py` 实现错题集三维结构、唯一 ID、确认状态与必需字段校验
- [x] 2.3 增加自包含回归测试，覆盖合法输入、预算升级、pending、来源缺失、错题重复、JSON、退出码和只读幂等

## 3. Skills

- [x] 3.1 使用 skill-creator 初始化并完成 `skills/x-adversarial-risk/`，写明 standard/deep/full 流程和渐进加载纪律
- [x] 3.2 创建独立 `risk-mistakes.md`，录入本轮已确认的 journal recovery 缺口及动作/数据/场景三维证据
- [x] 3.3 更新 x-spec3 的模板与流程，写入双评分、预算、pending 状态、审查记录和 `initial-spec` 来源
- [x] 3.4 更新 x-req3 交接门禁，对带 adversarial risk v1 标记的 Spec 复跑风险契约校验

## 4. 仓库文档

- [x] 4.1 更新主流程文档，说明 `x-spec3 → x-adversarial-risk → x-req3`、错题集边界和动态预算
- [x] 4.2 记录提交边界：代码与测试=`risk_contract.py`+`test_adversarial_risk.py`；skills=`x-adversarial-risk/`+x-spec3/x-req3 接入；仓库文档=`README*`+`CLAUDE.md`+本 OpenSpec change，排除其他工作区改动

## 5. 验证

- [x] 5.1 运行 skill quick validation、风险契约测试与相关 req3/xdev 回归测试
- [x] 5.2 运行 OpenSpec strict validate、`git diff --check` 和最终文件范围审计
