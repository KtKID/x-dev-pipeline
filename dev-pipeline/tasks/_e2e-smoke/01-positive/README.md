# 01-positive: e2e 正向用例

需求：在仓库根创建 `dev-pipeline/tasks/_e2e-smoke/01-positive/output.txt`，内容单行 `ok`。

预期：x-dev → x-verify → R1 → R2 → R3 全 pass，fix-counter 始终为 0。
