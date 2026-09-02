---
name: x-req
description: |
  x-spec 的任务拆解 skill。读取 `docs/spec/{spec-name}/spec.md` 的 feat 列表和场景，按 feat 分组拆成若干 task，每个 task 生成一份可执行、可验证的开发 checklist。用户提到 x-req、要求"把 spec 拆成任务""拆 checklist""排开发计划"，或 x-spec 完成需求整理后要进入开发时使用。
---

# x-req

把 spec 的 feat 拆成若干 task，每个 task 一份开发 checklist。checklist 的任务行回指 spec 里的场景：做完一行，按回指场景的 GIVEN/WHEN/THEN 验证；一个 task 的表全部跑完等于它覆盖的 feat 全部交付。

## 产物

在 `docs/spec/<spec-name>/tasks/<task-name>/dev-checklist.md` 生成——task 归属 spec，一个 task 一份 checklist，task 目录名用 `task-<功能名>`。全部 task 的 checklist 合并后覆盖 spec 的每个 feat 和每个场景。每份 checklist 在任务表下方带一棵**影响文件树**：用简化树状图标出本 task 在仓库中要改动的全部文件，`U` 新增 / `M` 修改 / `D` 删除。

## 核心原则

1. **feat 是拆分主轴。** 按 feat 划分 task：一个 task 覆盖一个或一组紧密相关的 feat（同一块数据、同一条链路），不把无关 feat 塞进同一个 task，也不把一个 feat 拆到两个 task。
2. **场景回指，不复述。** 任务行只写 `feat02 场景3` 这样的回指，GIVEN/WHEN/THEN 留在 spec 里做唯一事实源，checklist 不复制它们。
3. **合并后全覆盖。** 全部 task 的任务行合并后必须覆盖 spec 里每个 feat 的每一个场景。
4. **不建依赖图。** 单个 checklist 内任务行按实现顺序自然排列（被别人依赖的排前面），先后关系直接用行序表达，不画图、不写依赖列。task 之间的先后（如公共数据 task 在前）在交付报告里说明即可。

## 就绪检查

拆解前确认，发现问题回 x-spec 修，不要带病拆：

1. spec.md 存在且结构完整：标题 + 概述 + feat 列表。
2. feat 编号从 `feat01` 连续递增、无重复；每个 feat 至少覆盖正常、边界、异常三类场景。
3. 场景里没有留"或""二选一"这类没落定的结果。有就先请用户拍板、把结论回写进 spec 的场景，再拆解。

## 拆解规则

1. 先分组：把 feat 按"能独立交付的一组"划分成 task，公共数据/契约单独成 task 排在最前。
2. task 内每个 feat 按"能独立执行并验证"拆成若干任务行，常见顺序：公共数据/契约 → 核心功能 → 边界与异常 → 集成验证。
3. 场景回指列写 `feat01 场景2` 格式；同一行引用多个场景用逗号分隔（`feat02 场景1, 场景4`）。纯技术支撑行（脚手架、配置、目录初始化）写 `None`，此类行保持最少。
4. 涉及文件从代码调查得到，写到具体路径；确实定不下来的写最小目录或 glob，并在任务说明里写清定位动作。
5. 风险列：改动鉴权、数据持久化或迁移、并发、不可逆操作的行标 `高:<一句依据>`，其余写 `None`。高风险行的验证不允许只有 unit 测试。
6. 能直接转成测试的场景，验证就写成一行测试任务（标注 unit/smoke/e2e）；场景的 THEN 就是该测试的判定标准。
7. **影响文件树。** 汇总本 task 的涉及文件，在任务表下方画一棵以仓库根为起点的简化树：文件路径后标 `U`/`M`/`D`，`#` 后写一句改动说明；同一目录、同一标记、说明相同的文件可合并成一行（`/` 分隔）；定不下来的 glob 写目录级节点并注明定位动作。树与「涉及文件」列一一对应，不引入表外文件。

## 工作流

1. 读完 spec.md 全文，完成就绪检查。
2. 调查代码库，确定每个 feat 落在哪些文件、模块，是否与现有功能共享数据或契约。
3. 分组 feat 成 task，创建各 task 目录，完整读取 `templates/dev-checklist.md` 后逐个填充：task 内按实现顺序填表，再按规则 7 生成影响文件树，删除占位符和空示例。
4. 自检（见下），修完再交付。
5. 报告 task 列表（每个 task 覆盖的 feat）、场景覆盖情况、各 checklist 行数、高风险行、task 间先后建议，及下一步（按 task 逐个交给 x-dev 执行）。

## 自检

- 每个 feat 的每个场景都被至少一行回指？
- 每一行的 feat 号、场景号都真实存在于 spec？
- 每个 task 只覆盖一组相关 feat，没有一个 feat 跨 task？
- 有没有任务行超出 spec 概述声明的范围（"顺便"改了别的）？
- 影响文件树与「涉及文件」列一一对应（无树外文件、表内文件无遗漏），标记只用 U/M/D？
- 高风险行都标了依据，且验证不只 unit？
- 行序即实现顺序，先后关系一眼可读？
- checklist 里没有复制 spec 的 GIVEN/WHEN/THEN 或概述正文？

## 完整示例（节选）

输入是 reading-club 的 spec（结构见 x-spec 示例），7 个 feat 分成 3 个 task。其中 `tasks/task-group-management/` 覆盖 feat01、feat02，它的 checklist 长这样：

````markdown
# task-group-management · 开发清单

> spec: docs/spec/reading-club/spec.md
> 创建: 2026-08-15

**状态**：`[ ] ⏳` 未开始 / `[ ] ▶️` 进行中 / `[x] 🟢` 验证通过 / `[!] 🔴` 验证失败

| # | 任务 | 场景回指 | 涉及文件 | 风险 | 状态 |
|---|---|---|---|---|---|
| T1 | 小组数据结构与创建小组：名字、所选书必填校验，生成邀请码 | feat01 场景1-3 | src/groups.py | None | [ ] ⏳ |
| T2 | 邀请码加入小组：码校验、昵称必填、5 组上限、重复加入拦截 | feat02 场景1-5 | src/groups.py, src/join.py | None | [ ] ⏳ |
| T3 | smoke：创建 → 拿码 → 加入全链路 | feat01 场景1, feat02 场景1 | tests/smoke_join.py | None | [ ] ⏳ |

## 影响文件树

```text
reading-club/
├── src/groups.py        M  # 小组数据结构、创建校验、邀请码生成
├── src/join.py          U  # 新增：邀请码加入、昵称校验、5 组上限、重复拦截
└── tests/smoke_join.py  U  # 新增：创建 → 拿码 → 加入 smoke
```
````

（打卡、进度、讨论、退出等 feat 分进另外两个 task，此处省略。注意每一行都能独立做完并按回指场景验证，树上每个文件都能在「涉及文件」列找到。）
