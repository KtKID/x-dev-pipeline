# JavaScript 代码规范

> 语言：JavaScript
> 适用场景：.js, .jsx 文件审查

---

## 专项检查项

### P0：JavaScript 特有致命缺陷

检查：
- `null` / `undefined` 是否导致运行时错误
- `this` 绑定是否正确
- 变量提升（hoisting）是否导致意外行为
- 隐式类型转换是否导致错误结果
- 全局变量是否污染

结论要求：
- 每项都必须给出"通过 / 问题 / 需讨论"

---

### P1：异步 / Promise / 错误处理

检查：
- Promise 错误是否被 `.catch()` 捕获
- `async/await` 是否正确使用 `try/catch`
- 是否有未处理的 Promise rejection
- 回调函数是否正确处理错误
- 是否有 promise 链断裂风险
- 是否有回调地狱

结论要求：
- 每项都必须给出"通过 / 问题 / 需讨论"

---

### P2：ES6+ 特性正确使用

检查：
- 箭头函数 `=>` 是否正确使用（注意 this 绑定）
- 解构赋值是否恰当使用
- 展开运算符 `...` 是否正确使用
- 模板字面量是否替代字符串拼接
- `let` / `const` 是否替代 `var`
- 异步函数是否替代回调

结论要求：
- 每项都必须给出"通过 / 问题 / 需讨论"

---

### P3：代码风格与最佳实践

检查：

**命名规范**：
- 变量 / 函数是否使用 camelCase
- 类是否使用 PascalCase
- 常量是否使用 UPPER_SNAKE_CASE
- 布尔变量是否以 `is`, `has`, `can`, `should` 开头

**函数设计**：
- 函数是否遵循单一职责
- 参数是否过多
- 是否有不必要的嵌套

**模块组织**：
- import / export 是否正确使用
- CommonJS vs ES Module 是否一致
- 是否有循环依赖

**最佳实践**：
- 是否使用严格模式 `'use strict'`
- 是否有不必要的全局变量
- 是否有重复代码

结论要求：
- 每项都必须给出"通过 / 问题 / 需讨论"

---

## 常见问题模式

### 1. this 绑定问题

**问题代码**：
```javascript
class Counter {
  constructor() {
    this.count = 0;
  }
  increment() {
    setTimeout(function() {
      this.count++; // this 指向 window 或 undefined
    }, 1000);
  }
}
```

**建议**：
```javascript
class Counter {
  constructor() {
    this.count = 0;
  }
  increment() {
    setTimeout(() => {
      this.count++; // 箭头函数保持 this 绑定
    }, 1000);
  }
}
```

---

### 2. Promise 未捕获错误

**问题代码**：
```javascript
fetchData()
  .then(data => console.log(data));
// 错误未被捕获
```

**建议**：
```javascript
fetchData()
  .then(data => console.log(data))
  .catch(err => console.error(err));

// 或使用 async/await
try {
  const data = await fetchData();
  console.log(data);
} catch (err) {
  console.error(err);
}
```

---

### 3. 回调地狱

**问题代码**：
```javascript
getData(a => {
  getMoreData(b => {
    getEvenMoreData(c => {
      // 嵌套过深
    });
  });
});
```

**建议**：
```javascript
const data = await getData(a);
const more = await getMoreData(data);
const evenMore = await getEvenMoreData(more);
```

---

### 4. 变量提升问题

**问题代码**：
```javascript
console.log(x); // undefined（不是 ReferenceError）
var x = 5;
```

**建议**：
```javascript
let x = 5;
console.log(x（); // ReferenceError明确报错）
```

---

### 5. 隐式类型转换

**问题代码**：
```javascript
if (value) { // 隐式转换
  // value 为 0、''、null、undefined 时不会进入
}
```

**建议**：
```javascript
if (value !== null && value !== undefined) {
  // 明确检查
}
```

---

## 报告中的标注方式

在 Code Review 报告中，标注来源为"语言专项检查项"。

示例：
```markdown
| 状态 | 来源 | 检查项 | 文件:位置 | 描述 |
|------|------|--------|-----------|------|
| ❌ | 语言专项 | this 绑定 | `counter.js:15` | setTimeout 回调中 this 指向错误 |
| ⚠️ | 语言专项 | Promise 错误捕获 | `api.js:42` | Promise rejection 未被捕获 |
| ✅ | 语言专项 | 箭头函数 | - | 已正确使用箭头函数保持 this |
```

---

## 配合通用检查

本语言专项配置须配合 x-cr 的通用检查项使用：
- 通用 P0（功能正确性）优先于语言专项
- 语言专项检查不重复通用检查项
- 如有冲突，以通用检查项为准
