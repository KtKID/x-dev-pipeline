# Bundled executor tools

本目录由 `scripts/refresh_bundled_tools.py` 从仓库根 `tools/` 集中刷新。

`prepare_workspace.py` 只从这里复制考生运行工具，并用 `manifest.json` 校验 SHA。候选 workspace 必须包含：

- `xdev.py`
- `validator.py`
- `flag.py`
- `req.py`
- `spec.py`
- `verify.py`

`metrics.py` 同样打包在本目录，供 collect 阶段使用，不进入考生 workspace。

七个工具文件和 manifest 属于 skill package；考生无需访问源仓库的 `tools/`。
