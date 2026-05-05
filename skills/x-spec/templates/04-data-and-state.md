# 数据模型与状态

## 核心实体

[系统中最重要的数据对象——每个实体给出名称、字段、关系]

```typescript
// 示例
interface Session {
  id: string
  provider: Provider
  messages: Message[]
  created_at: Date
}

interface Message {
  role: 'user' | 'assistant'
  tokens: { input: number; output: number }
  model: string
}
```

## 实体关系

[用文字或 mermaid ER 图描述实体之间的关系]

## 状态流转

[核心对象的生命周期状态机——从创建到终态]

```
created → scanning → parsed → aggregated → displayed
                       ↓
                    parse_failed → retry
```

## 持久化方案

| 数据 | 存储方式 | 位置 | 备注 |
|------|---------|------|------|
| 原始 session | 本地文件 | 各 client 目录 | 只读 |
| 解析缓存 | SQLite | ~/.cache/xxx | 可删除重建 |
| 聚合结果 | 内存 | 运行时计算 | 不持久化 |

## 共享数据结构

[跨模块共用的类型定义——避免各模块重复定义]

```typescript
// 跨模块共用
type Provider = 'anthropic' | 'openai' | 'google' | ...
type ModelId = string
```
