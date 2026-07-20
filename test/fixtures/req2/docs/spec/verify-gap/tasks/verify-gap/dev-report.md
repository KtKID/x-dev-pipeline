# verify-gap dev-report

⚠️ 故意留缺口的夹具，勿修。归属 spec.md 里的自动场景叫「功能V生效」，
下面这个 verify 块的 `scenario` **故意指向另一个名字**，因此「功能V生效」没有证据回指，
预期 verify 把它列入 `uncovered` 并以退出码 1 结束。

```verify
id: v1
scenario: 一个不相干的场景名
cmd: echo fixture-ok
expect_contains: fixture-ok
mode: auto
```
