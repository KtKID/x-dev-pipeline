# cr-handson · 考点（评审侧）

每道题一个小项目，埋了不同的问题和陷阱。判分全部由 `evals/scripts/handson_grade.py` 按 `<题目>/checks.json` 做，不靠人判；隐藏测试 `<题目>/hidden_test.py` 答题方看不到。

| 题目 | 阶段 | 埋了什么 | 考哪条规则 |
|---|---|---|---|
| cr-renew | x-cr，再接 x-fix | 续借上限 off-by-one（C1）、先加次数再校验（D01）、用客户端 member_id 查别人借阅 | 判尺用 C/D/场景原编号；严重度；位置写文件+函数；不改代码。x-fix：P0/P1 都修、反例测试修前失败、隐藏测试过、报告只追加 |
| cr-fine-diff | x-cr | 在 task 里、没给范围：diff 里提前还书罚款为负（C1）；diff 只改了 loan.py 日志；diff 外的 member.py 有 bug；diff 里有个烂变量名 tmp2 | 没给范围查 git diff；报告放 task 的 reports/cr/；不报 diff 外的问题；不报风格；loan:C1 若列出应是没走到/守住了 |
| cr-reserve | x-cr | 有库存也能预约（feat01 场景1 被打破）；预约上限 spec 写 3 本、代码 5 本、用户说早改成 5 本；cancel_reservation() 看着没核对归属，其实 api 层已核对 | 来源不一 → P2 问题；不误报调用方已守住的规则 |
| cr-recommend | x-cr，已知问题 | 推荐缓存键只用了读者偏好类别，同类读者串了推荐；auth.py 是干扰项 | 原因不明时列 2–4 个可能原因逐个排除并坐实；隔离被突破 → P0 |
| fix-mixed | x-fix | 预先写好的报告：B1 P0 真问题；B2 P1 真问题但行号过期；B3 误报（代码其实核对了归属）；B4 来源不一；B5 已修；另有 extend_due() 报告外的 bug | 已修跳过不动；误报写理由不改代码；来源不一改待确认不改代码；行号对不上按函数找；不修报告外的问题；反例测试修前失败；报告只追加修复段、改状态 |

跑法：

```bash
python3 evals/scripts/handson_setup.py <题目> /tmp/eval/<题目>-rN        # 建副本，同时留 .orig 原样
# 派 haiku 子 agent：读 evals/problems/cr-handson/prompt.md，告诉它仓库路径、副本路径、题目编号
python3 evals/scripts/handson_grade.py <题目> cr|fix /tmp/eval/<题目>-rN --json > evals/runs/cr-handson/iteration-N/<题目>-rN.json
# cr-renew 接着跑 x-fix：
python3 evals/scripts/handson_setup.py --chain /tmp/eval/cr-renew-rN /tmp/eval/cr-renew-rN-fix
```
