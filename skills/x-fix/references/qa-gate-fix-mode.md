# x-fix · qa-gate-fix-mode

> 当 x-fix 由 x-verify 或 x-qua-gate 的 R1/R2/R3 触发时，进入本模式。

## 输入识别

- 入参里包含 `verify-report-*.md` 路径 → mode: verify-fix
- 入参里包含 `qa-gate-report-*.md` 中 R1 fail → mode: r1-spec-fix
- 入参里包含 R2 fail → mode: r2-boundary-fix
- 入参里包含 R3 fail → mode: r3-test-fix

## 通用流程

1. 读 fix-counter，counter >= 6 → 生成 fix-blocked-report.md，停。
2. counter +1，写回 .fix-counter。
3. 读对应 fail 报告中的具体问题列表（P0 必修、P1 选修、P2 跳过）。
4. 逐条修复。
5. 按 SKILL.md 4 条规则判定回流目标，写回流标签到 fix 报告 footer。
6. 写 fix 报告到对应路径（见 SKILL.md 路径表）。
7. 把控制权交给主 agent，由主 agent 触发回流目标节点（x-verify / R1 / R2 / R3）。

## mode 特殊规则

### verify-fix
- 只修让命令 fail 的代码（编译错误 / 测试 fail / lint error）。
- 修完触发回流：默认回 x-verify 重新复跑命令。
- **注意**：不要去改 dev-report.md 里的命令清单或预期 exit！那会绕过验证。

### r1-spec-fix
- 修 spec 不符问题（缺实现 / 偏离 / 多余功能）。
- 修完触发回流：回 R1 重审。

### r2-boundary-fix
- 加边界处理代码（null check / 异常处理 / 错误消息）。
- 修完按 4 条规则判：如改了核心业务函数 → 回 R1；只加防御代码 → 回 R2。

### r3-test-fix
- **只改测试代码**，不动业务代码（如果业务代码有问题应该是 R1/R2 拦下）。
- 修完触发回流：回 R3 重审。
- 警告：如果发现"测试改不对是因为业务代码本身有问题"，停下提示用户——这是 R1/R2 的漏检，要回前面节点。
