# 示例图集

> 用于验证 x-spec `diagrams.md` 模板效果：总览节点包含中文模块作用和关键类/函数，数据关系图在暗色预览里保持可读。

## 目录

- [总览](#总览)
- [类关系](#类关系)
- [E2E 测试链路](#e2e-测试链路)
- [数据关系](#数据关系)

图例：总览节点写模块名、中文作用、关键类/函数；数据关系节点统一深色实体样式。

## 总览

[模块级依赖图：每个节点说明模块作用，并给出关键类/函数名]

```mermaid
flowchart TD
  classDef module fill:#E8F1FE,stroke:#0071E3,color:#1D1D1F,stroke-width:1.5px
  classDef support fill:#F2F2F7,stroke:#8E8E93,color:#1D1D1F,stroke-width:1.5px

  Account["账户模块<br/>管理用户身份和登录态<br/>类/函数：AccountService.login()"]:::module
  Order["订单模块<br/>创建订单并维护订单状态<br/>类/函数：OrderService.createOrder()"]:::module
  Payment["支付模块<br/>发起支付并记录支付结果<br/>类/函数：PaymentService.charge()"]:::module
  Notify["通知模块<br/>推送订单和支付状态变更<br/>类/函数：NotificationService.sendPaymentResult()"]:::support

  Account --> Order
  Order --> Payment
  Order -.-> Notify
  Payment -.-> Notify
```

## 类关系

[核心类关系图：展示服务类、仓储类和通知类之间的调用边界]

```mermaid
classDiagram
  class AccountService {
    +createUser(email)
    +login(email, password)
  }

  class OrderService {
    +createOrder(userId, items)
    +cancelOrder(orderId)
  }

  class PaymentService {
    +charge(orderId, amount)
    +refund(paymentId)
  }

  class NotificationService {
    +sendOrderCreated(orderId)
    +sendPaymentResult(paymentId)
  }

  class OrderRepository {
    +save(order)
    +findById(orderId)
  }

  OrderService --> AccountService : 校验用户
  OrderService --> OrderRepository : 读写订单
  OrderService --> PaymentService : 发起支付
  PaymentService --> NotificationService : 通知结果
  OrderService --> NotificationService : 通知订单
```

## E2E 测试链路

[从测试数据准备到结果断言的完整验证路径]

```mermaid
flowchart LR
  classDef setup fill:#E8F1FE,stroke:#0071E3,color:#1D1D1F,stroke-width:1.5px
  classDef action fill:#FFF4E5,stroke:#FF9500,color:#1D1D1F,stroke-width:1.5px
  classDef assert fill:#F2F2F7,stroke:#8E8E93,color:#1D1D1F,stroke-width:1.5px

  Seed["准备测试数据<br/>TestDataFactory.createUserWithCart()"]:::setup
  Login["登录用户<br/>POST /login"]:::action
  Create["创建订单<br/>OrderService.createOrder()"]:::action
  Pay["模拟支付<br/>PaymentGatewayMock.charge()"]:::action
  Assert["断言结果<br/>订单=paid<br/>通知已发送"]:::assert

  Seed --> Login --> Create --> Pay --> Assert
```

## 数据关系

[数据关系图：一个实体一个紧凑节点，关系边表达方向和基数]

```mermaid
%%{init: {"theme": "base", "themeVariables": {"background": "#181A1F", "primaryColor": "#242933", "primaryTextColor": "#F5F7FA", "primaryBorderColor": "#6BA7FF", "lineColor": "#AAB4C0", "textColor": "#F5F7FA", "edgeLabelBackground": "#181A1F"}}}%%
flowchart LR
  classDef entity fill:#1F2633,stroke:#6BA7FF,color:#F5F7FA,stroke-width:1.5px
  classDef supporting fill:#191F29,stroke:#AAB4C0,color:#F5F7FA,stroke-width:1.2px

  USER["USER<br/>────────<br/>PK user_id<br/>status"]:::entity
  ORDER["ORDER<br/>────────<br/>PK order_id<br/>FK user_id<br/>order_status"]:::entity
  ORDER_ITEM["ORDER_ITEM<br/>────────<br/>PK item_id<br/>FK order_id"]:::entity
  PAYMENT["PAYMENT<br/>────────<br/>PK payment_id<br/>FK order_id<br/>pay_status"]:::supporting
  NOTIFICATION["NOTIFICATION<br/>────────<br/>PK notification_id<br/>FK order_id<br/>send_status"]:::supporting

  USER -->|owns 1:N| ORDER
  ORDER -->|contains 1:N| ORDER_ITEM
  ORDER -->|paid_by 1:1| PAYMENT
  ORDER -->|triggers 1:N| NOTIFICATION
```
