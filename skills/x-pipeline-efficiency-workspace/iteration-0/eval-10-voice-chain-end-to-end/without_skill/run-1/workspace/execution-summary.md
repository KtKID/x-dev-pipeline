# Voice Chain baseline 执行总结

## 结果

- 已完成 `spec3 → req3 → dev → verify → Q3 Gate (q1-intent → q2-correctness → q3-evidence) → x-fix → 增量复审` 全闭环。
- Gate ① 最终结果：13 个 Scenario 全部 pass，`fail=[]`、`uncovered=[]`、`manual=[]`。
- Gate ② 最终结果：P0 ×0、P1 ×0；3 个 P2 作为非阻塞风险登记。
- 开发清单 T1–T4 均为 `[x] ✅`，fix-counter 已清零。

## 读取的工作区 skills

1. `skills/x-spec3/SKILL.md` 与 `templates/spec.md`
2. `skills/x-req3/SKILL.md` 与 checklist/diagram 模板
3. `skills/x-dev/SKILL.md`、执行规则与 dev-report 模板
4. `skills/x-verify/SKILL.md` 与 verify-report 模板
5. `skills/x-qa-gate/SKILL.md`、R1/R2/R3 reference 与 ledger 模板
6. `skills/x-fix/SKILL.md`、qa-gate-fix-mode 与 fix 模板

## 主要阶段

1. 读取题面、三份分段任务、三份规范、后端骨架和只读测试设施。
2. 生成 spec3 单一契约，记录分块续传、会话所有权、TTS_END 元数据、路径安全与语义错误码的最小安全假设。
3. 生成 Q3 task checklist 与七模块影响边界图，机械 validate 为零 issue。
4. 先写失败测试，再实现协议接收、续传、WAV 校验、ASR→LLM→TTS、总 HTTP deadline、落盘与 PCM 下行。
5. 使用独立 wire codec、固定 golden frame、独立 PCM oracle、bundled device-sim、故障注入和确定性 socket fault 完成测试增强。
6. x-verify 两次完整复跑；Q3 Gate 两轮 x-fix 后由原 reviewer 增量确认全部 P1 关闭。

## 修改文件

- `fixture/backend/app.py`
- `fixture/backend/audio.py`
- `fixture/backend/http_client.py`
- `fixture/backend/protocol.py`
- `fixture/backend/test_voice_chain.py`
- `docs/spec/voice-chain/spec.md`
- `docs/spec/voice-chain/tasks/voice-chain-backend/dev-checklist.md`
- `docs/spec/voice-chain/tasks/voice-chain-backend/diagram.md`
- `docs/spec/voice-chain/tasks/voice-chain-backend/dev-report.md`
- `docs/spec/voice-chain/tasks/voice-chain-backend/reports/qa-gate/qa-gate-report-20260723-005637.md`
- `docs/spec/voice-chain/tasks/voice-chain-backend/reports/fix/fix-gate-r1-20260722-170633.md`
- `docs/spec/voice-chain/tasks/voice-chain-backend/reports/fix/fix-gate-r2-20260722-172031.md`
- `docs/spec/voice-chain/tasks/voice-chain-backend/reports/.fix-counter`
- `execution-summary.md`

手工 Smoke 还生成了 `fixture/backend/sessions/smoke-weather/upload.wav` 与 `reply.wav` 作为可检查运行产物。

## 测试命令与结果

- `python3 -m unittest -v test_voice_chain`（cwd `fixture/backend`）→ 18 tests，全部通过。
- `python3 tools/xdev.py verify docs/spec/voice-chain/tasks/voice-chain-backend --json` → pass 13，fail 0，uncovered 0，manual 0。
- `python3 tools/xdev.py validate docs/spec/voice-chain --json` → total_issues 0。
- `python3 ../device-sim/device_sim.py --server 127.0.0.1:9000 --wav ../assets/ask_weather.wav --session smoke-weather --out /tmp/voice-chain-smoke-out` → ACK 含预期 text/reply，下行 9 块 / 26656 字节。
- `cmp` 与独立 PCM 校验 → upload.wav、reply.wav、下行 PCM 均与真源素材逐字节一致。
- `env PYTHONPYCACHEPREFIX=/tmp/voice-chain-pycache python3 -m py_compile app.py audio.py http_client.py protocol.py test_voice_chain.py` → 通过。

默认 sandbox 禁止绑定 loopback，首次回环测试出现 `PermissionError: [Errno 1] Operation not permitted`；获得本地回环权限后所有相关测试均通过，题面和 mock 保持只读。

## 遗留风险 / 人工确认

- `issue-1`：超过 3200 字节的 AUDIO_CHUNK 当前在 AUDIO_END 统一拒绝，块接收阶段已经 ACK；是否要求 ACK 前即拒绝需要协议语义确认。
- `issue-2`：题面未定义客户端空闲读写期限；半帧停顿或停止读取可能长期占用连接线程。
- `issue-3`：题面要求进程内续传且未定义 TTL/容量；大量未完成 session 会形成长期内存保留。

以上三项均为 Q3 Gate 登记的 P2，不影响当前题面验收。
