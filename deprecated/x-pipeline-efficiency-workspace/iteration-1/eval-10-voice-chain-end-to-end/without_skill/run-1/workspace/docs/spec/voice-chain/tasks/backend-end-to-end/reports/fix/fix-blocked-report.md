# x-fix 熔断报告 — backend-end-to-end

> `reports/.fix-counter` 当前为 3，已达到 x-fix 的三轮共享上限。本轮 R3 问题未进入第四轮修复。

## 已完成处置

- issue-1：R1 修复并增量复审通过。
- issue-2 至 issue-6：R2 修复并增量复审通过。
- issue-10：R2 增量修复并复审通过。
- issue-7、issue-8、issue-9、issue-21：P2 已登记，保持非阻塞。

## 待决策积压

| Issue | 严重度 | Task | 位置 | 问题 |
|---|---|---|---|---|
| issue-11 | P0 | T1,T5 | `fixture/backend/e2e_test.py:16` | 协议 E2E 与生产编解码共享实现，缺独立 raw-byte/golden 证据 |
| issue-12 | P0 | T4,T5 | `fixture/backend/e2e_test.py:218` | PCM 期望使用生产 `wav_pcm`，存在镜像断言 |
| issue-13 | P0 | T1,T2,T3,T4,T5 | `dev-report.md:19` | verify 缺完整 unittest discover，已有回归未全部纳入 |
| issue-14 | P0 | T2,T5 | `fixture/backend/test_app.py:70` | SC_06 缺连接入口的 ERROR、禁止落盘与 ASR 零调用断言 |
| issue-15 | P0 | T1,T2,T3,T5 | `fixture/backend/e2e_test.py:188` | ERROR 路径缺服务端 EOF 与续传状态保留证据 |
| issue-16 | P0 | T3,T5 | `fixture/backend/e2e_test.py:271` | 三类上游失败策略缺完整故障矩阵与调用计数证据 |
| issue-17 | P1 | T4,T5 | `fixture/backend/e2e_test.py:309` | 下行断开测试未确定性触发发送异常 |
| issue-18 | P0 | T2,T3,T4,T5 | `fixture/backend/e2e_test.py:294` | 并发 E2E 缺两会话持久化文件与目录映射断言 |
| issue-19 | P0 | T2,T5 | `dev-report.md:141` | 生产 session 写路径缺原子可见性证据 |
| issue-20 | P1 | T3,T5 | `fix-gate-r2-incremental-20260723-021000.md:5` | 最后一轮 HTTP 修复后缺完整 verify 输出记录 |

## 需要的决策

选择继续第四轮修复、调整 R3 证据要求，或接受当前实现与已知验证缺口。当前 checklist 依门禁规则保持 `[!] 🔴`。
