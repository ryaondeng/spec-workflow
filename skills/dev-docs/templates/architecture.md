---
doc_id: ARCH-001
type: architecture
source_commit: {commit}
generated_at: {generated_at}
inventory_hash: {inventory_hash}
status: {status}
---

# 架构视图：{project}

> 一句话定位：{summary}

<!-- AI-GEN:BEGIN -->
## 技术栈

- 语言/框架：{langs}

## 模块划分与依赖

| MOD-id | 模块 | 路径 | 职责 | 主要依赖 |
|:---|:---|:---|:---|:---|
{module_rows}

## 数据流 / 调用链

```text
（AI 依据 inventory 与源码绘制：外部触发 → 核心组件 → 出口）
```

## 关键入口

{entry_rows}
<!-- AI-GEN:END -->

## 人工补充（机器不覆盖）

<!-- TODO: 设计意图 / why / 历史权衡 / 相关 ADR 链接，由人工填写（evidence: 人类） -->
