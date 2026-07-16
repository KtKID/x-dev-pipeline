# Dev Report — <task-name> — YYYYMMDD-HHmmss

## 改动文件清单

- <仓库相对路径>

## 验证证据

> 本节是 `python3 tools/xdev.py verify <task-dir>` 的唯一自动输入。
> 至少保留一条测试类 auto 块；没有测试框架时写 `no-test-framework: true` 与理由，并用 manual 块记录可复现人工步骤。
> README 中每个 `验证: auto` 的 Scenario 都必须有一个 auto 块用 `scenario:` 精确回指。

```verify
id: S1
scenario: <README 验收 Scenario 名>
cmd: python3 -m unittest discover -s test
cwd: .
expect_exit: 0
expect_contains: OK
mode: auto
```

```verify
id: M1
scenario: <README 人工验收 Scenario 名>
mode: manual
steps: <可复现的人工验收步骤>
```

字段说明：`id` 在本报告内唯一；`cwd` 相对仓库根且可省略；`expect_exit` 缺省为 0；`expect_contains` 可重复；`timeout` 仅在显式填写时生效；manual 块不执行命令。

## 自检结论

本人（x-dev）已在本机运行全部 auto verify 命令，并确认结果与本报告一致。
本报告由 <skill 名> 于 <UTC 时间戳> 生成。
