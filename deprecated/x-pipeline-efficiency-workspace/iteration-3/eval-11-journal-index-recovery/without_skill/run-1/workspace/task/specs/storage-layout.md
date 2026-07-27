# 固定存储布局

```text
<state-dir>/
  events.log
  snapshot.json
  snapshot.json.tmp   # 仅写入过程中短暂存在
  events.log.tmp      # 仅 compact 过程中短暂存在
  writer.lock
```

实现可在首次命令时创建 state-dir、空 events.log 与 writer.lock。实现不得在该目录创建数据库、pickle、缓存索引或其他持久化真相源。

