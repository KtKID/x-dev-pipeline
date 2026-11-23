# CR 报告：推荐页把读者 10 的借阅痕迹显示给读者 20

> 时间：2026-11-23 04:13
> 模式：查已知问题
> 范围：`src/library/recommend.py`（主要），上下游 `src/library/history.py`、`src/library/auth.py`、`tests/test_recommend.py`
> spec：docs/spec/recommend/spec.md / 无（没有 tech-design.md）

## 范围

- 现象或检查目标：读者 20 的推荐页出现“因为你借过《三体》”，但读者 20 从没借过《三体》，读者 10 借过。
- 期望：推荐只由读者自己的借阅历史算出；“因为你借过《X》”里的 X 必须是他自己借过的（spec feat01 场景1）。
- 实际：读者 20 拿到的推荐和读者 10 的完全相同，包括“因为你借过《三体》”。
- 看了哪些代码：
  - `src/library/recommend.py`：`_cache_key()`（第 8–9 行）、`_build()`（第 12–19 行）、`get_recommendations()`（第 22–26 行）
  - `src/library/history.py`：`HistoryStore.books_of()`（按 member_id 分桶，正常）
  - `src/library/auth.py`：`Member` 只有 `member_id` 和 `favorite_category`
  - `tests/test_recommend.py`：只有一个用例，只测读者 10

## 规则表

| 编号 | 规则 | 来源 | 最小反例 | 结论 | 问题 |
|---|---|---|---|---|---|
| recommend:feat01-场景1 | 推荐只来自读者自己的借阅历史；“因为你借过《X》”里的 X 必须是他自己借过的 | spec.md feat01 场景1 | GIVEN 读者 10 借过《三体》，读者 20 没借过任何书，两人 favorite_category 都是“科幻”；WHEN 读者 10 先打开推荐页，读者 20 随后打开；THEN 读者 20 的结果不能含“因为你借过《三体》”。实际结果含该句（见 B1 证据） | 被打破 | B1 |
| 新1 | 借阅历史变了，推荐结果要跟着变 | spec 没写；`src/library/recommend.py` 的 `get_recommendations()` 缓存后从不失效，`HistoryStore.add()` 也不通知缓存 | GIVEN 读者 30 首次打开推荐页得到空结果；WHEN 读者 30 借了《活着》再打开；THEN 应能推荐《许三观卖血记》。实际仍为空，因为缓存未失效（见 B2 证据） | 没法验证 | B2 |
| 新2 | 推荐用的读者身份由服务端会话决定，调用方传的身份不能改变查谁的借阅 | spec 没写；`src/library/auth.py` 的 `current_member()` 从会话取 `Member` | 没走到：本次范围里 `get_recommendations()` 直接收 `Member` 对象，调用方怎么拿到它不在范围内，无法判断 | 没走到 | - |

## 问题

| ID | 严重度 | 状态 | 位置 | 一句话 |
|---|---|---|---|---|
| B1 | P0 | 待修 | `src/library/recommend.py` 的 `_cache_key()` 第 9 行，以及 `get_recommendations()` 第 23–25 行 | 缓存键只用 `favorite_category`，不含 `member_id`，同类别的读者共用一份推荐，读者 20 看到读者 10 的借阅 |
| B2 | P2 | 待修 | `src/library/recommend.py` 的 `get_recommendations()` 第 23–25 行 | 缓存从不失效，借了新书后推荐不更新；spec 没写推荐要多快反映新借阅，需要用户确认 |

### B1: 缓存键漏了读者身份，跨读者串数据

- 规则：recommend:feat01-场景1
- 位置：`src/library/recommend.py` 的 `_cache_key()`，第 8–9 行；`get_recommendations()`，第 23–25 行
- 反例：GIVEN 读者 10 借过《三体》，读者 20 没借过任何书，两人 favorite_category 都是“科幻”；WHEN 读者 10 先请求推荐，读者 20 再请求；THEN 读者 20 拿到的结果不应含“因为你借过《三体》”。
- 证据：代码路径和探针复现都指向缓存键（下面逐条列出）
  - 代码路径：`get_recommendations(member, history)`（入口）→ `_cache_key()` 返回 `rec:科幻`（第 9 行，只用 `member.favorite_category`）→ 第 24 行缓存命中 → 直接返回读者 10 算好的列表（校验和过滤都没在这里做）。
  - 复现（在探针脚本里跑，没改代码）：先算读者 10，再算读者 20，结果为：
    - 读者 10：`因为你借过《三体》，推荐《球状闪电》`、`因为你借过《三体》，推荐《沙丘》`、`因为你借过《三体》，推荐《基地》`
    - 读者 20（从没借过书）：与读者 10 完全相同的三行
    - 缓存键只有一个：`['rec:科幻']`
  - 对照：清空缓存后单独算读者 20，结果为空列表。说明结果是缓存串来的，不是 `_build()` 算错的。
  - 为什么测试没抓住：`tests/test_recommend.py::test_recommend_same_category` 只测读者 10 一个人，且每次先 `_cache.clear()`，所以没有“两个读者共用缓存”的用例。`pytest -q` 结果为 1 passed，这只说明被测到的路径没问题。
  - “有时”出现的原因：只有在两个读者 favorite_category 相同、且先算的那位被缓存后，后面的读者才会中招。顺序决定谁的结果被串过去。
- 影响：任何和别人 favorite_category 相同的读者，都可能在推荐页看到别人的借阅书名。这是借阅记录的隔离被突破，按隔离被突破定为 P0。
- 怎么改：把缓存键改成包含 `member_id`，例如 `f"rec:{member.member_id}:{member.favorite_category}"`；并补一个两读者共用类别的反例测试（先算读者 10，再断言读者 20 的结果不含“因为你借过《三体》”）。本次只查，不改代码。

### B2: 推荐缓存不失效，借阅变化后结果不更新

- 规则：新1
- 位置：`src/library/recommend.py` 的 `get_recommendations()`，第 23–25 行；`src/library/history.py` 的 `HistoryStore.add()`
- 反例：GIVEN 读者 30（文学）首次打开推荐页，结果为空；WHEN 读者 30 借了《活着》，再打开推荐页；THEN 按 `CATALOG`，应能推荐《许三观卖血记》。
- 证据：探针脚本复现，首次结果 `[]`，借了《活着》后结果仍为 `[]`，缓存键 `rec:文学` 未被清除。`HistoryStore.add()` 不触发任何缓存更新。
- 影响：读者借了新书，推荐页要等缓存被手动清掉才会更新。不会导致串数据，所以定为 P2。
- 怎么改：先问用户：推荐是否必须借后实时更新？如果需要，可以在 `add()` 后失效该读者的缓存（要配合 B1 的按读者缓存键）；如果允许延迟，则把允许的延迟写进 spec。在用户确认前不改。

## 原因排查

| 可能原因 | 找了什么证据 | 结论 |
|---|---|---|
| 缓存键不含 member_id，两个同类别读者共用结果 | 读 `_cache_key()`，只返回 `rec:{favorite_category}`；探针：读者 10 算完后读者 20 拿到相同结果；清缓存后读者 20 结果为空 | 成立（即 B1） |
| `HistoryStore` 把不同读者的借阅混在一起 | 读 `history.py`，`_by_member` 按 `member_id` 分桶，`books_of()` 只取该 id 的列表；探针中读者 20 的历史为空却有输出，因此输出不是从 history 来的 | 排除 |
| `_build()` 的推荐过滤有错，把别人的书混进来 | `_build()` 只遍历 `books_of(member_id)`；清缓存后读者 20 的结果为空，说明 `_build()` 对空历史是正确的 | 排除 |
| 读者身份在登录层拿错（拿成了读者 10 的 Member） | 读 `auth.py`，`current_member()` 按 token 取会话，本次范围未包含调用方。直接调用时 `Member(20, ...)` 的 member_id 是 20，但真实请求链路没在范围内 | 还不确定；补证据：看 `get_recommendations()` 的调用方和 token 到 Member 的映射 |

## 结论

- 最严重的问题：B1，推荐缓存键不含读者身份，读者 20 能看到读者 10 的借阅书名（P0）。
- spec 要补的规则：新1（借阅变化后推荐多久更新，spec 没写，要用户定）；新2 没走到，不用补，留作参考。
- 另外：`tests/test_recommend.py` 缺一个两读者共用缓存的用例，修 B1 时应一并补上。
