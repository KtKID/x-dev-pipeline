# Qdev Report — verify-module-extraction — 20260720

## 风险与审查路线

- 风险等级：Q2
- 触发因素：验证核心函数迁移、新旧路径共存、重叠工作树改动
- 审查路线：综合 reviewer

## 改动文件

- `tools/verify.py` — 新旧 verify 路径的单一实现 owner
- `tools/xdev.py` — 保留 CLI，委托 `verify_engine.verify`
- `tools/req.py` — 保留 req2 通用解析，移除 verify 专属实现
- `test/test_xdev_verify.py` — 单一 owner 回归断言
- `test/test_req_engine.py` — 内部 owner 引用迁移
- `README.md`、两组 OpenSpec change 文档 — owner 与边界同步

## DoD 证据矩阵

| DoD | 证据类型 | 命令 / 测试 / 代码路径 / 人工步骤 | 实际结果 | 状态 |
|-----|----------|-----------------------------------|----------|------|
| D1 | 静态检查 + 回归测试 | `rg` verify 定义位置；`test_verify_implementation_has_single_module_owner` | 12 个 verify 专属函数只定义在 `tools/verify.py`，owner 测试通过 | pass |
| D2 | 定向测试 | `python3 -m unittest test.test_xdev_verify test.test_req_engine` | 67 tests，exit 0 | pass |
| D3 | diff + 定向测试 | None/空列/悬空 Requirement 回归用例 | 相关用例包含在 67 个定向测试并通过 | pass |
| D4 | 全量测试 | `python3 -m unittest discover -s test` | 166 tests，exit 0 | pass |

## 实际验证命令

| 命令 | 工作目录 | 实际 exit | 关键输出 |
|------|----------|-----------|----------|
| `python3 -m py_compile tools/xdev.py tools/req.py tools/verify.py` | repo root | 0 | 三个模块语法检查通过 |
| `python3 -m unittest test.test_xdev_verify test.test_req_engine` | repo root | 0 | `Ran 67 tests ... OK` |
| `python3 -m unittest discover -s test` | repo root | 0 | `Ran 166 tests ... OK` |
| `openspec validate xdev-task-scoped-verify --strict` | repo root | 0 | change valid |
| `openspec validate xreq-spec-driven --strict` | repo root | 0 | change valid |
| `git diff --check` | repo root | 0 | 无 whitespace error |

## Diff 审查

- 任务起点基线：25 个 tracked 文件已有修改；`tools/req.py`、`test/test_req_engine.py` 与本任务重叠
- `git diff --stat`：本任务新增 `tools/verify.py`，从 `tools/xdev.py`/`tools/req.py` 删除重复实现，并更新测试 owner 与直接关联文档
- 实际范围与声明范围：一致；文档扩展仅修正迁移后失真的 owner/边界描述
- 成功路径证据：旧路径 auto+manual pass、req2 scoped verify pass 与端到端用例通过
- 关键失败路径证据：exit mismatch、missing output、timeout、uncovered、坏 block、坏 checklist/spec 标注用例通过
- 用户既有改动保护：`tools/req.py` 的 None/空列/悬空 Requirement 逻辑搬入 `verify.py` 后由原新增测试继续验证；其余用户 dirty paths 未改动

## 综合 Reviewer（仅 Q2）

- Status：pass
- Evidence：首轮发现 legacy 全角标记语义变化；增加 legacy 专用正则和回归测试后复审通过
- P0：none
- P1：none；原 P1 resolved

## 最终结论

- [x] 每条 DoD 都有真实证据
- [x] 实际 diff 与任务范围一致
- [x] 成功路径已验证
- [x] 适用的关键失败路径已验证
- [x] Q2 综合 reviewer 已通过或当前路线为 Q0/Q1

结论：complete

## 后续收敛 — 删除旧结构 verify — 20260720

- 风险等级：Q1；主 agent 证据闭环。
- `tools/verify.py` 删除 `LEGACY_VALIDATION_RE`、`legacy_acceptance_scenarios()`、
  `verify_legacy()`、仓库根常量和旧路径 fallback。
- `tools/xdev.py` 的 verify 帮助与模块说明同步为仅接受
  `docs/spec/<spec>/tasks/<task>/`。
- `test/test_xdev_verify.py` 的通用执行测试改用真实 spec task 结构，并增加旧路径
  exit 2 与 legacy 定义不存在的回归断言。
- `PYTHONPYCACHEPREFIX=/tmp/xdev-pycache python3 -m py_compile tools/verify.py tools/xdev.py`：exit 0。
- `python3 -m unittest test.test_xdev_verify test.test_req_engine`：67 tests，exit 0。
- `python3 -m unittest discover -s test`：166 tests，exit 0。
