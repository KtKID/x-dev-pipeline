# 考题①：设备音频上传通道

> 附件清单（随卷必发）：`specs/audio-format.md`、`specs/wire-protocol.md`
> 起始环境：`fixture/`（后端骨架 `backend/`、仿真设备 `device-sim/`、素材 `assets/`）

## 背景

一台语音设备（现阶段用仿真设备 `device-sim` 代替，相当于发给你一块开发板）通过 TCP
向后端上传录音文件。你要实现后端的接收端。

## 需求

1. 在 `fixture/backend/app.py` 中实现连接处理：按 `wire-protocol.md` 完成
   HELLO / AUDIO_CHUNK / AUDIO_END / ACK / ERROR 的完整流程；
2. 收齐后重组音频，校验 AUDIO_END 携带的 sha256，落盘
   `sessions/<session_id>/upload.wav`（相对后端工作目录），须与设备侧原始文件**逐字节一致**；
3. 断线续传：设备用同一 session_id 重连后，后端在 HELLO 的 ACK 里告知已收到的最大块号，
   设备从断点继续（进程内存续传即可，不要求跨进程持久化）；
4. 协议健壮性：
   - 设备可能不等 ACK 连续发送（流水线发送），也可能一次网络包里粘着多个帧、
     或一个帧拆成多个网络包到达（TCP 是字节流）；
   - 非法帧（魔数错、CRC 错、载荷超限）按规范回 ERROR 帧。

## 约束

- 只准用 Python 标准库；
- 数值常量（端口、块大小、载荷上限等）以 `backend/config.json` 与规范文件为真源，禁止在代码里另立硬编码；
- 骨架里已提供 `protocol.py`（帧编解码）、`http_client.py`、`audio.py` 三个工具模块，
  可以直接用也可以改——**但对其正确性负责的是你**；
- 后端启动契约（判分依赖，勿改）：`python3 app.py --port 9000 --config config.json`。

## 交付与自测

- 自测方法：起后端后运行
  `python3 ../device-sim/device_sim.py --server 127.0.0.1:9000 --wav ../assets/ask_weather.wav --upload-only`；
- 注意：仿真设备只覆盖正常路径，异常路径（粘包、断连、坏帧）需要你自行构造验证；
- 按你自己的开发流程产出规划/设计/验证文档，判分会按评分表评审。
- 规范未尽事宜：向出题人提问澄清，或在文档中显式记录你的假设。
