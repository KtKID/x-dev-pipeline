# cr-review · 考点（评审侧）

规则来源：`skills/x-cr/SKILL.md`、`skills/x-cr/references/`。

- R01–R02：范围。没给范围查 git diff；diff 也空就问用户。
- R03–R06：判尺编号。spec 的 C、D、场景沿用原编号加 spec 名前缀；spec 没写的用 新N，不用旧的 INV-SPEC。
- R07：spec 没写的规则只提醒，不改 spec。
- R08–R11：五种结论。R09 没走到；R10 spec 和用户说法不一 → 来源不一；R11 缺证据 → 没法验证。
- R12：没法验证也要开问题，一般 P2。
- R13–R15：严重度看影响。越权 P0；可恢复的用户可见错误 P1；测试测不出错、代码现在对 → P2。
- R16：风格不报。
- R17–R18：原因排查只在原因不明时做。
- R19：位置写文件、函数和行，不写 commit 哈希。
- R20：task 里报告放 task 的 reports/cr/。
- R21：x-cr 不改代码，要修交 x-fix。
- R22：测试全绿但没测到反例路径，不能直接判守住了。
