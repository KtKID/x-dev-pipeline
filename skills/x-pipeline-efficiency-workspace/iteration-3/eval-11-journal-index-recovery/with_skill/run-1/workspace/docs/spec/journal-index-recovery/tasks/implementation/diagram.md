# implementation · 影响边界图

```mermaid
flowchart LR
  CLI["fixture/backend/cli.py"]
  Lock["fixture/backend/locking.py"]
  Store["fixture/backend/store.py"]
  Record["fixture/backend/record.py"]
  StateDir["<state-dir> 文件布局"]
  Caller["CLI 子进程调用方"]

  Caller --> CLI --> Lock --> Store
  Store --> Record
  Store --> StateDir
  Caller -.-> Store
```
