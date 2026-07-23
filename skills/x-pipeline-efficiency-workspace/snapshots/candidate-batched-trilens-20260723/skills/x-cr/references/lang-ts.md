# TypeScript 代码规范

> 语言：TypeScript
> 适用场景：.ts, .tsx 文件审查

---

## 专项检查项

### P0：TypeScript 特有致命缺陷

检查：
- `any` 类型滥用是否导致类型安全丧失
- 类型断言（`as`）是否掩盖了潜在类型错误
- `strict: true` 是否被绕过
- 泛型是否使用不当导致运行时错误
- 接口 / 类型定义是否与实际数据结构不匹配
- 类型推断是否产生意外结果

结论要求：
- 每项都必须给出"通过 / 问题 / 需讨论"

---

### P1：类型系统最佳实践

检查：
- 是否优先使用具体类型而非 `any` / `unknown`
- 是否正确使用联合类型 / 交叉类型
- 可选属性是否标注 `?`
- 是否使用类型守卫进行类型收窄
- 枚举使用是否恰当
- `unknown` vs `any` 使用是否正确
- 泛型约束是否合理

结论要求：
- 每项都必须给出"通过 / 问题 / 需讨论"

---

### P2：TS 特性正确使用

检查：
- `readonly` 是否用于不可变数据
- 可选链（`?.`）和空值合并（`??`）是否正确使用
- 模板字面量类型是否恰当使用
- 装饰器是否正确使用
- 类型别名 vs 接口是否选择恰当
- 索引签名是否必要

结论要求：
- 每项都必须给出"通过 / 问题 / 需讨论"

---

### P3：代码风格与最佳实践

检查：

**命名规范**：
- 类 / 接口 / 类型 / 枚举是否使用 PascalCase
- 布尔变量是否以 `is`, `has`, `can`, `should` 开头

**类型设计**：
- 类型是否单一职责
- 是否有过于复杂的类型推导
- 是否有不必要的类型层级

**模块组织**：
- import 语句是否按标准顺序排列
- 是否有循环依赖
- barrel 文件（index.ts）是否合理使用

结论要求：
- 每项都必须给出"通过 / 问题 / 需讨论"

---

## 常见问题模式

### 1. `any` 滥用

**问题代码**：
```typescript
function process(data: any): any {
  return data.foo.bar;
}
```

**建议**：
```typescript
interface Data {
  foo: {
    bar: string;
  };
}
function process(data: Data): string {
  return data.foo.bar;
}
```

---

### 2. 类型断言过度使用

**问题代码**：
```typescript
const value = something as string;
console.log(value.length); // 可能运行时崩溃
```

**建议**：
```typescript
// 使用类型守卫
if (typeof value === 'string') {
  console.log(value.length);
}
// 或使用 unknown
function safeLength(val: unknown): number {
  if (typeof val === 'string') return val.length;
  return 0;
}
```

---

### 3. 可选链缺失

**问题代码**：
```typescript
const len = data.foo && data.foo.bar && data.foo.bar.baz.length;
```

**建议**：
```typescript
const len = data.foo?.bar?.baz?.length;
```

---

### 4. 泛型不当使用

**问题代码**：
```typescript
function identity<T>(arg: T): T {
  return arg; // 丢失了具体类型信息
}
```

**建议**：
```typescript
// 使用具体类型约束
function identity<T extends string>(arg: T): T {
  return arg;
}
```

---

## 报告中的标注方式

在 Code Review 报告中，标注来源为"语言专项检查项"。

示例：
```markdown
| 状态 | 来源 | 检查项 | 文件:位置 | 描述 |
|------|------|--------|-----------|------|
| ❌ | 语言专项 | any 类型滥用 | `user.ts:15` | 使用 any 导致类型安全丧失 |
| ⚠️ | 语言专项 | 类型断言 | `api.ts:42` | 过度使用类型断言掩盖错误 |
| ✅ | 语言专项 | 可选链使用 | - | 已正确使用可选链 |
```

---

## 配合通用检查

本语言专项配置须配合 x-cr 的通用检查项使用：
- 通用 P0（功能正确性）优先于语言专项
- 语言专项检查不重复通用检查项
- 如有冲突，以通用检查项为准
