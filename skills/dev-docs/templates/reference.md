---
doc_id: {MOD-id}
type: reference
module_id: {MOD-id}
source_commit: {commit}
generated_at: {generated_at}
inventory_hash: {inventory_hash}
status: {status}
---

# {module_name}

> 路径：{path}　语言：{lang}　符号 {n_symbols}

<!-- AI-GEN:BEGIN -->
## 概览（四问）

- **做什么**：<!-- TODO AI：一句话职责（evidence: 推断） -->
- **为何存在**：<!-- TODO AI：为何存在（evidence: 推断/假设需注明） -->（evidence: 推断/假设时标注依据）
- **依赖什么**：{deps}
- **谁依赖它**：<!-- TODO AI：谁依赖它（可反向扫描 import） -->

## 符号索引

| ID | 符号 | 类型 | 说明 |
|---|---|---|---|
{index_rows}

## 详细契约

<!-- 分节顺序：模块级函数 → 类 → HTTP 端点 → 接口契约资产（ROS 话题/服务/消息类型，条目来自语义地图或 register 登记，每条带来源文件） -->
{detail_rows}
<!-- AI-GEN:END -->

## 人工补充（机器不覆盖）

<!-- TODO: 业务上下文、设计取舍、注意事项，由人工填写 -->
