# Dev Report — <task-name> — YYYYMMDD-HHmmss

## 改动文件清单

- <仓库相对路径>

## 验证证据

> 本节是 `python3 "${XDEV_SKILL_DIR}/scripts/xdev.py" verify <task-dir>` 的唯一自动输入。
> 至少保留一条测试类 auto 块；归属 `spec.md` 中标为 `验证: manual` 的场景用 manual 块记录可复现人工步骤与理由。
> 本 task checklist 承接的每个 Scenario 都必须有对应 verify 块；使用 `scenario: SC_01` 精确回指，兄弟 task 承接的 Scenario 不在本报告范围内。

```verify
id: S1
scenario: <SC_01>
cmd: python3 -m unittest discover -s test
cwd: .
expect_exit: 0
expect_contains: OK
mode: auto
```

```verify
id: M1
scenario: <SC_02>
mode: manual
steps: <可复现的人工验收步骤>
```

字段说明：`id` 在本报告内唯一；`cwd` 相对仓库根且可省略；`expect_exit` 缺省为 0；`expect_contains` 可重复；`timeout` 仅在显式填写时生效；manual 块不执行命令。

## 自检结论

本人（x-dev）已在本机运行全部 auto verify 命令，并确认结果与本报告一致。
本报告由 <skill 名> 于 <UTC 时间戳> 生成。
