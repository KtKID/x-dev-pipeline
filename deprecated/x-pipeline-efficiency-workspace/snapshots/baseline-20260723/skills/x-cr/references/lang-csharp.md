# C# 代码规范

> 语言：C#
> 适用场景：.cs 文件审查

---

## 专项检查项

### P0：C# 特有致命缺陷

检查：
- `NullReferenceException` 风险：是否对可能为 null 的引用进行了空检查
- 值类型 / 引用类型混淆：`struct` 与 `class` 的语义差异是否被正确理解
- `async void` 方法：除事件处理器外，是否误用 `async void`（异常无法被捕获）
- `IDisposable` 未释放：是否遗漏 `using` 语句或 `Dispose()` 调用
- 死锁风险：是否在同步上下文中调用 `.Result` 或 `.Wait()`（ASP.NET / UI 线程）
- 类型转换失败：`InvalidCastException` 风险，是否应使用 `as` + null 检查或 `is` 模式匹配

结论要求：
- 每项都必须给出"通过 / 问题 / 需讨论"

---

### P1：异步 / 并发 / 异常处理

检查：
- `Task` 是否正确 `await`，是否存在 fire-and-forget 未处理异常
- `CancellationToken` 是否在长时间操作中传递和检查
- `lock` 使用是否合理，是否存在锁粒度过大或嵌套锁导致死锁
- `ConcurrentDictionary` / `Interlocked` 等线程安全集合是否在并发场景中使用
- 异常处理层级是否合理：是否存在空 `catch {}` 吞掉异常
- `ConfigureAwait(false)` 在库代码中是否正确使用

结论要求：
- 每项都必须给出"通过 / 问题 / 需讨论"

---

### P1.5：LINQ 与集合操作

检查：
- LINQ 是否存在多次枚举（Multiple Enumeration）：`IEnumerable` 是否被重复遍历
- 延迟执行陷阱：LINQ 查询是否在预期外被多次执行
- `ToList()` / `ToArray()` 是否在适当时机调用以物化结果
- 大集合上的 LINQ 是否有性能隐患（应考虑 `for` 循环替代）
- `FirstOrDefault` / `SingleOrDefault` 返回值是否检查 null / default

结论要求：
- 每项都必须给出"通过 / 问题 / 需讨论"

---

### P2：Nullable Reference Types 与现代 C# 特性

检查：
- 项目是否启用 `<Nullable>enable</Nullable>`，代码是否正确标注 `?` 可空类型
- Pattern Matching（`is`、`switch` 表达式）是否用于替代冗长的 `if-else` 类型检查
- `record` vs `class` vs `struct` 选择是否合理
- `init` 属性和 `required` 关键字是否用于不可变数据
- `string interpolation` 是否替代 `string.Format` 和字符串拼接
- `using` 声明（无大括号）是否用于简化资源管理
- `global using` 是否合理使用以减少重复引用

结论要求：
- 每项都必须给出"通过 / 问题 / 需讨论"

---

### P3：代码风格与最佳实践

检查：

**命名规范**：
- 类、接口、枚举、方法、属性是否使用 PascalCase
- 接口是否以 `I` 前缀命名（如 `IDisposable`）
- 参数、局部变量是否使用 camelCase
- 私有字段是否以 `_` 前缀命名（如 `_logger`）
- 常量是否使用 PascalCase（C# 惯例，非 UPPER_SNAKE_CASE）
- 布尔属性 / 方法是否以 `Is`、`Has`、`Can`、`Should` 开头

**依赖注入**：
- 是否通过构造函数注入依赖而非直接 `new`
- 服务生命周期（Singleton / Scoped / Transient）是否选择正确
- 是否存在 Captive Dependency（Singleton 持有 Scoped 服务）

**资源管理**：
- 数据库连接、HTTP 客户端、文件流是否正确释放
- `HttpClient` 是否通过 `IHttpClientFactory` 使用（避免 socket 耗尽）

**项目组织**：
- `namespace` 是否与目录结构一致
- `using` 语句是否按标准顺序排列（System → 第三方 → 项目内）
- 是否有循环依赖

结论要求：
- 每项都必须给出"通过 / 问题 / 需讨论"

---

## 常见问题模式

### 1. async void 异常丢失

**问题代码**：
```csharp
// 异常无法被调用方捕获，直接崩溃进程
async void LoadData()
{
    var data = await httpClient.GetStringAsync(url);
    Process(data);
}
```

**建议**：
```csharp
async Task LoadDataAsync()
{
    var data = await httpClient.GetStringAsync(url);
    Process(data);
}
```

---

### 2. 同步上下文死锁

**问题代码**：
```csharp
// 在 ASP.NET / WPF 中会死锁
public string GetData()
{
    return GetDataAsync().Result;
}
```

**建议**：
```csharp
// 方案 1：全链路 async
public async Task<string> GetDataAsync()
{
    return await httpClient.GetStringAsync(url);
}

// 方案 2：库代码中使用 ConfigureAwait(false)
public async Task<string> GetDataAsync()
{
    return await httpClient.GetStringAsync(url).ConfigureAwait(false);
}
```

---

### 3. IDisposable 资源泄露

**问题代码**：
```csharp
var stream = new FileStream(path, FileMode.Open);
var content = ReadAll(stream);
// stream 未被释放
```

**建议**：
```csharp
using var stream = new FileStream(path, FileMode.Open);
var content = ReadAll(stream);
// 作用域结束自动释放
```

---

### 4. LINQ 多次枚举

**问题代码**：
```csharp
IEnumerable<User> users = GetUsers(); // 延迟执行
var count = users.Count();            // 第一次枚举
var first = users.First();            // 第二次枚举 — 可能结果不同
```

**建议**：
```csharp
var users = GetUsers().ToList(); // 立即物化
var count = users.Count;
var first = users[0];
```

---

### 5. Null 引用未检查

**问题代码**：
```csharp
var user = db.Users.FirstOrDefault(u => u.Id == id);
var name = user.Name; // NullReferenceException
```

**建议**：
```csharp
var user = db.Users.FirstOrDefault(u => u.Id == id);
if (user is null)
{
    throw new NotFoundException($"User {id} not found");
}
var name = user.Name;

// 或使用 null 条件运算符
var name = user?.Name ?? "Unknown";
```

---

## 报告中的标注方式

在 Code Review 报告中，标注来源为"语言专项检查项"。

示例：
```markdown
| 状态 | 来源 | 检查项 | 文件:位置 | 描述 |
|------|------|--------|-----------|------|
| ❌ | 语言专项 | async void | `UserService.cs:45` | 非事件处理器使用 async void，异常无法被捕获 |
| ⚠️ | 语言专项 | IDisposable | `DataAccess.cs:78` | FileStream 未使用 using 语句 |
| ✅ | 语言专项 | Nullable | - | 已正确启用 nullable reference types |
```

---

## 配合通用检查

本语言专项配置须配合 x-cr 的通用检查项使用：
- 通用 P0（功能正确性）优先于语言专项
- 语言专项检查不重复通用检查项
- 如有冲突，以通用检查项为准
