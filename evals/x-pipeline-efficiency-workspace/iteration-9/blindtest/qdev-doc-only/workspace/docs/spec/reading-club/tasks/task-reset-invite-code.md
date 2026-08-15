# 小组创建人可以重置邀请码

> spec: docs/spec/reading-club/spec.md
> feat: feat01, feat02（重置作用于 feat01 生成的邀请码，并改变 feat02 用码加入的判定）
> 创建: 2026-08-14

## ① 需求

### 功能方向

小组创建人可以把小组的邀请码重置一次换新。重置之后，之前发出去的旧邀请码立刻作废，拿到旧码的陌生人再也不能用它加入小组；同时系统给创建人一个新的邀请码，创建人可以继续用新码邀请朋友。

### 功能边界

- 做：创建人对自己建的小组发起重置；重置成功后旧邀请码不能再用于加入（统一提示"邀请码无效"）；重置后给出一个新邀请码，新码格式与现有邀请码一致（6 位），且与旧码不同、不与其他小组的邀请码重复；新码可以正常用来加入小组
- 做：只有创建人能重置——小组普通成员、不在小组里的人、别的小组的创建人尝试重置都被拒绝，且重置被拒绝时小组邀请码保持不变
- 不做：不做邀请码过期时间、使用次数限制、重置频率限制等更复杂的邀请码管理（只做创建人手动重置）
- 不做：不改变创建小组时自动生成邀请码的现有行为
- 不做：不向小组成员发送"邀请码已重置"的通知
- 不做：重置不踢出任何已有成员、不清除任何打卡记录

### 不能破坏的不变量

- 没有被重置过的有效邀请码，加入流程一切照旧：输入有效码 + 昵称仍能正常加入（feat02 场景1）
- 创建小组时仍会自动生成并展示 6 位邀请码（feat01 场景1）
- 加入小组的各项校验规则不变：码不存在提示"邀请码无效"、不填昵称提示"请填写昵称"、重复加入提示"你已经在这个小组里了"、满 5 个小组提示"最多只能同时加入 5 个小组"（feat02 场景2-5）
- 任意时刻，两个小组不会同时持有同一个有效邀请码（重置产生的新码也不能撞上别组的码）
- 重置只换码、不动人：已有成员的成员资格、昵称、打卡记录在重置前后完全不变

## ② 测试用例（先写，此刻失败）

需求点编号：R1 创建人重置后获得新码；R2 旧码立即失效；R3 新码可正常加入；R4 只有创建人能重置；R5 重置不改变已有成员和数据。
不变量编号：I1 有效码加入流程不变；I2 创建自动出码不变；I3 加入校验规则不变；I4 邀请码全局唯一；I5 成员数据不受重置影响；I6 失效码统一提示"邀请码无效"。

### unit

新增 `ResetInviteCodeTest`（测 `ReadingClub.reset_invite_code`）：

- test_owner_reset_returns_new_six_char_code：创建人重置成功后，小组邀请码变为新的 6 位码，且不等于重置前的旧码 → R1
- test_old_code_invalid_after_reset：重置后用旧码调 `join_group`，抛 ClubError 且提示"邀请码无效" → R2、I6
- test_new_code_join_succeeds：重置后用新码 + 昵称加入成功，成员和昵称正确记录 → R3
- test_old_code_invalid_even_without_nickname：旧码 + 空昵称一起提交，仍提示"邀请码无效"（码校验在前，不因缺昵称而变味）→ R2 边界（错误输入组合）
- test_member_cannot_reset：小组普通成员尝试重置，抛 ClubError 且提示"只有小组创建人可以重置邀请码"，且小组邀请码保持旧码、旧码仍可正常加入 → R4
- test_non_member_cannot_reset：不在小组里的陌生用户尝试重置，同样被拒绝、邀请码不变 → R4 边界（错误输入）
- test_other_group_owner_cannot_reset：另一个小组的创建人尝试重置本小组，被拒绝、邀请码不变 → R4 边界（错误输入）
- test_reset_unknown_group_id：对不存在的小组 id（如 "g999"）和空字符串 id 发起重置，抛 ClubError 且提示"小组不存在" → R4 边界（错误输入、空输入）
- test_reset_twice_invalidates_both_old_codes：连续重置两次，前两个旧码都提示"邀请码无效"，只有最新码能加入 → R1、R2 极值（多次重置）
- test_new_code_unique_across_groups：存在另一个小组时重置，新码不等于另一组的邀请码 → I4
- test_reset_keeps_members_and_data：重置后 members、nicknames、checkins 与重置前完全一致 → R5、I5
- test_existing_join_rules_still_apply_to_new_code：已在组内的成员用新码再加入提示"你已经在这个小组里了"；已满 5 个小组的用户用新码加入提示"最多只能同时加入 5 个小组" → I3

### smoke

新增 `ResetSmokeTest`（最小真实调用链，不 mock）：

- test_smoke_owner_reset_invite_code_flow：`create_group(u1)` 创建小组拿到码 A → `reset_invite_code(u1, group.id)` 重置拿到码 B（B ≠ A）→ 陌生人用码 A 加入，提示"邀请码无效"，未加入 → 朋友用码 B + 昵称加入成功，出现在成员列表里 → R1 + R2 + R3 完整链路

### e2e

不需要，依据：本项目是纯内存逻辑库，没有独立 UI/网络层，smoke 已覆盖"创建 → 重置 → 旧码拒绝 → 新码加入"的完整真实调用链；用户链路上的风险点（旧码失效、新码可用、权限拒绝）已由 unit + smoke 逐条覆盖。

不变量回归计划（实现后执行）：既有 `CreateGroupTest`、`JoinGroupTest`、`CheckInTest` 全量通过即覆盖 I1、I2、I3。

## ③ 技术实现

### 实现步骤

1. `reading_club.py` · `ReadingClub` 新增 `reset_invite_code(user_id, group_id)` 方法（设计草图，供评审）：

   ```python
   def reset_invite_code(self, user_id, group_id):
       group = self._groups_by_id.get(group_id)
       if group is None:
           raise ClubError("小组不存在")
       if user_id != group.owner_id:
           raise ClubError("只有小组创建人可以重置邀请码")
       new_code = self._new_code()   # 关键顺序：旧码此刻仍在 _groups_by_code 里
       del self._groups_by_code[group.invite_code]
       group.invite_code = new_code
       self._groups_by_code[new_code] = group
       return group                  # 调用方从 group.invite_code 读新码
   ```

2. `test_reading_club.py` 新增 `ResetInviteCodeTest`（②unit 12 条）与 `ResetSmokeTest`（②smoke 1 条）；先跑确认红（此刻 `reset_invite_code` 不存在），再实现变绿。

3. 不改动 `join_group`、`create_group`、`_new_code`：旧码从 `_groups_by_code` 移除后自动落入现有"邀请码无效"分支；新码生成复用 `_new_code` 的查重。无需数据迁移。

关键设计决策：

- 生成顺序：先 `_new_code()` 再删旧码映射。`_new_code` 会对 `_groups_by_code` 查重，旧码还在映射里就天然保证新码 ≠ 旧码；若反过来先删后生成，新码有极小概率随机回旧码本身，导致旧码"复活"。test_owner_reset_returns_new_six_char_code 直接断言这一点。
- 权限判据：只认 `group.owner_id`。feat07（创建人退出后转让创建人）尚未实现，一旦实现，新创建人自动获得重置权，本逻辑无需再改。
- 返回值：返回更新后的 group 对象，与 `create_group`/`join_group` 的返回风格一致，新码从 `group.invite_code` 读取。
- 错误文案："小组不存在"、"只有小组创建人可以重置邀请码"为新增文案，沿用 ClubError message 直接展示给用户的既有约定。

### 涉及文件

- reading_club.py: `ReadingClub` 新增 `reset_invite_code` 方法，不改动任何已有方法
- test_reading_club.py: 新增 `ResetInviteCodeTest`、`ResetSmokeTest` 两个测试类

## ④ 验证结果

### 测试输出

待实现后填写（实现阶段按③步骤先红后绿，粘贴真实运行输出）

### 不变量回归

待实现后填写（实现后运行 `python -m unittest test_reading_club -v`，粘贴既有测试全量结果）

### 结论

- [ ] 所有需求点被测试覆盖（②已逐条映射 R1-R5、I1-I6，实现阶段核对）
- [ ] 所有测试真实跑过且通过 —— 待实现后填写
- [ ] 实现在边界内 —— 待实现后核对（③声明仅动 reading_club.py 与 test_reading_club.py，不改已有方法）
- [ ] 不变量未破坏 —— 待实现后跑既有测试确认
