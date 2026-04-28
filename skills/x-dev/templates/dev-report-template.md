# Dev Report — <task-name> — YYYYMMDD-HHmmss

## 改动文件清单
- <绝对路径或仓库相对路径>
- ...

## 验证命令清单
> ⚠️ **本节是 x-verify 的输入。x-verify 会复跑下表全部命令并对比 exit code 与关键输出。**
> ⚠️ 至少必须包含一条"测试"类命令；项目无测试框架时必须显式写 `no-test-framework: true` 行 + 理由。

| 命令 | 工作目录 | 预期 exit | 关键输出片段（用于 grep 校验） |
|------|---------|----------|------------------------------|
| `npm run build` | 项目根 | 0 | `Compiled successfully` |
| `npm test` | 项目根 | 0 | `Tests: 42 passed` |
| `npm run lint` | 项目根 | 0 | `0 errors` |

## 自检结论
本人（x-dev / x-qdev）已在本机完整运行上述命令，确认全部通过。
本报告由 <skill 名> 于 <UTC 时间戳> 生成。
