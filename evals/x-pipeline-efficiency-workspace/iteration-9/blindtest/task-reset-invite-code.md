# 重置小组邀请码

> spec: docs/spec/reading-club/spec.md
> feat: feat01, feat02
> 创建: 2026-08-14

## ① 需求

### 功能方向

小组创建人可以把本小组的邀请码换成一个全新的。邀请码泄露后，创建人重置一次，泄露的旧码立即作废，陌生人拿旧码加不进来；创建人同时拿到一个新码，可以继续邀请朋友。

### 功能边界

- 做：创建人对自己创建的小组一键重置邀请码；旧码立即失效、不能再用；返回一个 6 位新码，新码可以正常用于加入小组
- 不做：不改动加入流程的其他规则（昵称必填、最多加入 5 个小组、不能重复加入同一小组）；不做邀请码自动过期/有效期；不支持自定义新码

### 不能破坏的不变量

- 已在小组成员名单里的人不受重置影响：仍然在小组里，昵称和打卡记录都保留，还能继续打卡
- 用有效邀请码加入小组的既有流程完全不变
- 重置只影响本小组，其他小组的邀请码照常可用

## ② 测试用例（先写，此刻失败）

### unit

- test_owner_reset_returns_new_code：创建人重置成功，返回 6 位新码、与旧码不同，且小组当前邀请码同步更新 → 需求"重置后给一个新码"
- test_old_code_invalid_after_reset：重置后用旧码加入，提示"邀请码无效"，加入失败 → 需求"旧码失效不能用了"
- test_new_code_can_join：重置后用新码加入成功，昵称正确写入 → 需求"新码可用"
- test_non_owner_member_cannot_reset：普通成员重置被拒绝，提示"只有创建人可以重置邀请码"，且邀请码保持不变 → 边界：非创建人
- test_stranger_cannot_reset：不在小组里的陌生人重置被拒绝，提示同上，邀请码保持不变 → 边界：陌生人
- test_reset_nonexistent_group：重置不存在的小组提示"小组不存在" → 边界：错误输入
- test_reset_twice_only_latest_code_works：连续重置两次，三个码互不相同，前两个旧码都失效，只有最新码能加入 → 极值：重复操作
- test_existing_members_unaffected_after_reset：重置后原成员仍在小组、昵称与打卡记录保留、还能继续打卡 → 不变量"成员不受影响"
- test_other_group_code_unaffected：重置 A 组后，B 组的邀请码仍可正常加入 → 不变量"不影响其他小组"

### smoke

- test_smoke_reset_flow（最小真实调用链）：创建小组 → 创建人重置邀请码 → 拿泄露旧码的陌生人加入被拒（"邀请码无效"）→ 朋友用新码加入成功 → 创建人当天打卡正常 → 预期全部成立

### e2e

不需要，依据：纯本地内存实现、无网络与多端交互，smoke 已完整覆盖"创建 → 重置 → 旧码拒绝 → 新码加入"的用户操作链，风险不高。

## ③ 技术实现

### 实现步骤

1. reading_club.py：ReadingClub 新增 `reset_invite_code(owner_id, group_id)` 方法——按 group_id 找小组（找不到抛"小组不存在"）；校验操作者是创建人（否则抛"只有创建人可以重置邀请码"）；在旧码仍占据 `_groups_by_code` 的情况下先用 `_new_code()` 生成新码（保证新码 ≠ 旧码且全局唯一）；删除旧码映射、写入新码映射、更新 `group.invite_code`；返回新码。

### 涉及文件

- reading_club.py: 新增 `ReadingClub.reset_invite_code` 方法，其余代码不动
- test_reset_invite_code.py: 新增测试文件（9 个 unit + 1 个 smoke）

## ④ 验证结果

### 测试输出

实现前（红，失败原因均为"功能还没实现"，10/10 失败）：

```
$ python3 -m unittest discover -s . -t . -p "test_reset_invite_code.py" -v
test_smoke_reset_flow ... ERROR
test_existing_members_unaffected_after_reset ... ERROR
test_new_code_can_join ... ERROR
test_non_owner_member_cannot_reset ... ERROR
test_old_code_invalid_after_reset ... ERROR
test_other_group_code_unaffected ... ERROR
test_owner_reset_returns_new_code ... ERROR
test_reset_nonexistent_group ... ERROR
test_reset_twice_only_latest_code_works ... ERROR
test_stranger_cannot_reset ... ERROR
======================================================================
ERROR: test_owner_reset_returns_new_code
----------------------------------------------------------------------
Traceback (most recent call last):
  File "test_reset_invite_code.py", line 19, in test_owner_reset_returns_new_code
    new = self.club.reset_invite_code("u1", self.group.id)
          ^^^^^^^^^^^^^^^^^^^^^^^
AttributeError: 'ReadingClub' object has no attribute 'reset_invite_code'
（其余 9 个错误同为 AttributeError: 'ReadingClub' object has no attribute 'reset_invite_code'）
----------------------------------------------------------------------
Ran 10 tests in 0.004s

FAILED (errors=10)
```

实现后（绿，10/10 通过）：

```
$ python3 -m unittest discover -s . -t . -p "test_reset_invite_code.py" -v
test_smoke_reset_flow ... ok
test_existing_members_unaffected_after_reset ... ok
test_new_code_can_join ... ok
test_non_owner_member_cannot_reset ... ok
test_old_code_invalid_after_reset ... ok
test_other_group_code_unaffected ... ok
test_owner_reset_returns_new_code ... ok
test_reset_nonexistent_group ... ok
test_reset_twice_only_latest_code_works ... ok
test_stranger_cannot_reset ... ok
----------------------------------------------------------------------
Ran 10 tests in 0.000s

OK
```

### 不变量回归

既有测试（test_reading_club.py，12/12 通过）：

```
$ python3 -m unittest discover -s . -t . -p "test_reading_club.py" -v
test_check_in_records_pages_and_note ... ok
test_check_in_start_after_end_rejected ... ok
test_check_in_twice_same_day_rejected ... ok
test_streak_resets_after_gap ... ok
test_create_group_requires_book ... ok
test_create_group_requires_name ... ok
test_create_group_returns_invite_code ... ok
test_join_fifth_group_ok_sixth_rejected ... ok
test_join_requires_nickname ... ok
test_join_same_group_twice_rejected ... ok
test_join_with_invalid_code ... ok
test_join_with_valid_code ... ok
----------------------------------------------------------------------
Ran 12 tests in 0.000s

OK
```

全量测试（既有 + 新增，22/22 通过）：

```
$ python3 -m unittest discover -s . -t . -v
----------------------------------------------------------------------
Ran 22 tests in 0.001s

OK
```

### 结论

- [x] 所有需求点被测试覆盖
- [x] 所有测试真实跑过且通过
- [x] 实现在边界内
- [x] 不变量未破坏
