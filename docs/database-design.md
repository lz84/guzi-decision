# 谷子情报分析系统 - 数据库设计

## 文档信息
- **项目名称**: 谷子情报分析系统
- **文档类型**: 数据库设计说明书
- **版本**: 1.0
- **创建日期**: 2026-03-17
- **创建者**: 麻子 (Paperclip Agent)
- **Issue**: MAK-8 - 基于需求分析进一步设计

---

## 一、数据库架构

### 1.1 存储架构概览

本系统采用多数据库架构，针对不同数据类型使用最合适的存储方案：

```
┌─────────────────────────────────────────────────────────────────┐
│                       数据库架构                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    MongoDB (主数据库)                    │   │
│  │  - 原始文档数据                                          │   │
│  │  - 处理后数据                                            │   │
│  │  - 分析结果                                              │   │
│  │  - 配置数据                                              │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    Redis (缓存)                          │   │
│  │  - 会话数据                                              │   │
│  │  - 缓存数据                                              │   │
│  │  - 任务队列                                              │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    Milvus (向量存储)                     │   │
│  │  - 文本向量                                              │   │
│  │  - 语义检索                                              │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 数据库选型理由

| 数据库 | 选型理由 | 适用场景 |
|--------|----------|----------|
| MongoDB | 文档结构灵活、支持复杂查询、水平扩展 | 文档存储 |
| Redis | 高速读写、支持过期、发布订阅 | 缓存、队列 |
| Milvus | 高维向量存储、相似度检索 | 向量检索 |

---

## 二、MongoDB 数据库设计

### 2.1 数据库命名

```
数据库名: guzi_sentiment
```

### 2.2 集合设计

#### 2.2.1 原始数据集合 (raw_documents)

存储从各数据源采集的原始数据。

**集合名**: `raw_documents`

**文档结构**:
```json
{
  "_id": ObjectId,
  "source": "twitter",                    // 数据来源
  "source_id": "1234567890",              // 来源平台ID
  "platform": "twitter",                  // 平台名称
  "author": {
    "id": "user_123",                     // 作者ID
    "name": "用户名",                      // 作者名称
    "followers": 10000                    // 粉丝数
  },
  "content": "原始文本内容...",             // 原始内容
  "content_type": "text",                 // 内容类型: text, image, video
  "language": "zh",                       // 语言
  "url": "https://...",                   // 原文链接
  "published_at": ISODate("2026-03-17T06:00:00Z"),  // 发布时间
  "collected_at": ISODate("2026-03-17T06:05:00Z"),  // 采集时间
  "metadata": {                           // 元数据
    "retweet_count": 100,
    "like_count": 500,
    "reply_count": 50
  },
  "tags": ["选举", "政治"],                 // 标签
  "status": "pending",                    // 状态: pending, processed, failed
  "created_at": ISODate("2026-03-17T06:05:00Z"),
  "updated_at": ISODate("2026-03-17T06:05:00Z")
}
```

**索引设计**:
```javascript
// 1. 来源+来源ID复合索引（唯一）
db.raw_documents.createIndex({ "source": 1, "source_id": 1 }, { unique: true })

// 2. 发布时间索引（查询优化）
db.raw_documents.createIndex({ "published_at": -1 })

// 3. 状态索引（任务处理）
db.raw_documents.createIndex({ "status": 1 })

// 4. 标签索引（分类查询）
db.raw_documents.createIndex({ "tags": 1 })

// 5. 采集时间索引（TTL清理）
db.raw_documents.createIndex({ "collected_at": 1 })
```

**TTL 索引**（自动清理 90 天前的数据）:
```javascript
db.raw_documents.createIndex({ "collected_at": 1 }, { expireAfterSeconds: 7776000 })  // 90天
```

#### 2.2.2 处理后数据集合 (processed_documents)

存储经过清洗、去重、标准化处理后的数据。

**集合名**: `processed_documents`

**文档结构**:
```json
{
  "_id": ObjectId,
  "raw_document_id": ObjectId,            // 关联原始文档
  "source": "twitter",
  "platform": "twitter",
  "cleaned_content": "清洗后的文本...",    // 清洗后内容
  "normalized_content": "标准化内容...",   // 标准化内容
  "content_hash": "sha256:abc123...",     // 内容哈希（去重用）
  "language": "zh",
  "published_at": ISODate("2026-03-17T06:00:00Z"),
  "processed_at": ISODate("2026-03-17T06:10:00Z"),
  "processing_steps": [                   // 处理步骤记录
    "cleaned",
    "deduplicated",
    "normalized"
  ],
  "metadata": {
    "word_count": 150,
    "has_media": false
  },
  "status": "pending_analysis",
  "created_at": ISODate("2026-03-17T06:10:00Z"),
  "updated_at": ISODate("2026-03-17T06:10:00Z")
}
```

**索引设计**:
```javascript
// 1. 原始文档ID索引
db.processed_documents.createIndex({ "raw_document_id": 1 })

// 2. 内容哈希索引（去重）
db.processed_documents.createIndex({ "content_hash": 1 }, { unique: true })

// 3. 状态索引
db.processed_documents.createIndex({ "status": 1 })

// 4. 发布时间索引
db.processed_documents.createIndex({ "published_at": -1 })
```

#### 2.2.3 分析结果集合 (analysis_results)

存储情感分析、实体识别、事件提取的分析结果。

**集合名**: `analysis_results`

**文档结构**:
```json
{
  "_id": ObjectId,
  "processed_document_id": ObjectId,       // 关联处理后文档
  "source": "twitter",
  "platform": "twitter",
  "content": "分析的文本内容...",
  "sentiment": {                           // 情感分析结果
    "label": "negative",                   // 标签: positive, negative, neutral
    "score": -0.75,                        // 分数: -1 到 1
    "confidence": 0.85,                    // 置信度: 0 到 1
    "model": "finbert",                    // 使用的模型
    "analyzed_at": ISODate("2026-03-17T06:15:00Z")
  },
  "entities": [                            // 实体识别结果
    {
      "text": "候选人A",
      "type": "PERSON",
      "start": 10,
      "end": 14,
      "confidence": 0.95
    },
    {
      "text": "美国",
      "type": "GPE",
      "start": 20,
      "end": 22,
      "confidence": 0.98
    }
  ],
  "events": [                              // 事件提取结果
    {
      "type": "scandal",                   // 事件类型
      "title": "丑闻事件",
      "description": "候选人A卷入丑闻...",
      "entities": ["候选人A"],
      "impact": {
        "direction": "negative",
        "magnitude": 0.8,
        "confidence": 0.75
      },
      "extracted_at": ISODate("2026-03-17T06:20:00Z")
    }
  ],
  "keywords": ["选举", "丑闻", "候选人"],    // 关键词
  "topics": ["政治", "选举"],               // 话题
  "published_at": ISODate("2026-03-17T06:00:00Z"),
  "analyzed_at": ISODate("2026-03-17T06:20:00Z"),
  "created_at": ISODate("2026-03-17T06:20:00Z")
}
```

**索引设计**:
```javascript
// 1. 处理后文档ID索引
db.analysis_results.createIndex({ "processed_document_id": 1 })

// 2. 情感标签索引
db.analysis_results.createIndex({ "sentiment.label": 1 })

// 3. 发布时间索引
db.analysis_results.createIndex({ "published_at": -1 })

// 4. 事件类型索引
db.analysis_results.createIndex({ "events.type": 1 })

// 5. 关键词索引
db.analysis_results.createIndex({ "keywords": 1 })

// 6. 话题索引
db.analysis_results.createIndex({ "topics": 1 })

// 7. 复合索引：时间+情感
db.analysis_results.createIndex({ "published_at": -1, "sentiment.label": 1 })
```

#### 2.2.4 事件集合 (events)

存储提取的重要事件，用于预警和报告。

**集合名**: `events`

**文档结构**:
```json
{
  "_id": ObjectId,
  "event_id": "evt_20260317_001",          // 业务ID
  "type": "scandal",                       // 事件类型
  "category": "political",                 // 事件分类
  "title": "候选人A卷入丑闻事件",
  "description": "详细描述...",
  "summary": "简短摘要...",
  "entities": [                            // 相关实体
    {
      "name": "候选人A",
      "type": "PERSON",
      "role": "主角"
    }
  ],
  "sources": [                             // 数据来源
    {
      "platform": "twitter",
      "url": "https://...",
      "published_at": ISODate("2026-03-17T06:00:00Z")
    }
  ],
  "sentiment": {                           // 整体情感
    "label": "negative",
    "score": -0.8
  },
  "impact": {                              // 影响评估
    "level": "high",                       // 影响级别
    "score": 0.85,                         // 影响分数
    "prediction": "可能导致支持率下降3-5%"
  },
  "alert_sent": true,                      // 是否已发送预警
  "alert_channels": ["feishu"],            // 预警渠道
  "alert_sent_at": ISODate("2026-03-17T06:30:00Z"),
  "status": "active",                      // 状态: active, resolved, archived
  "occurred_at": ISODate("2026-03-17T06:00:00Z"),
  "detected_at": ISODate("2026-03-17T06:25:00Z"),
  "created_at": ISODate("2026-03-17T06:25:00Z"),
  "updated_at": ISODate("2026-03-17T06:30:00Z")
}
```

**索引设计**:
```javascript
// 1. 事件ID索引（唯一）
db.events.createIndex({ "event_id": 1 }, { unique: true })

// 2. 事件类型索引
db.events.createIndex({ "type": 1 })

// 3. 状态索引
db.events.createIndex({ "status": 1 })

// 4. 发生时间索引
db.events.createIndex({ "occurred_at": -1 })

// 5. 影响级别索引
db.events.createIndex({ "impact.level": 1 })

// 6. 预警状态索引
db.events.createIndex({ "alert_sent": 1 })
```

#### 2.2.5 预警配置集合 (alert_configs)

存储预警规则配置。

**集合名**: `alert_configs`

**文档结构**:
```json
{
  "_id": ObjectId,
  "name": "负面情感预警",
  "description": "当情感分数低于-0.5时触发预警",
  "enabled": true,
  "conditions": {
    "sentiment_score_max": -0.5,
    "keywords": ["丑闻", "危机"],
    "event_types": ["scandal", "crisis"]
  },
  "channels": ["feishu", "webhook"],
  "webhook_url": "https://...",
  "template": "预警模板内容...",
  "priority": "high",
  "cooldown_minutes": 30,                  // 冷却时间
  "created_at": ISODate("2026-03-17T00:00:00Z"),
  "updated_at": ISODate("2026-03-17T00:00:00Z")
}
```

#### 2.2.6 系统配置集合 (system_configs)

存储系统配置。

**集合名**: `system_configs`

**文档结构**:
```json
{
  "_id": ObjectId,
  "key": "keywords_config",
  "value": {
    "tracking_keywords": ["选举", "政策", "经济"],
    "exclude_keywords": ["广告", "推广"]
  },
  "description": "关键词追踪配置",
  "created_at": ISODate("2026-03-17T00:00:00Z"),
  "updated_at": ISODate("2026-03-17T00:00:00Z")
}
```

#### 2.2.7 日报集合 (daily_reports)

存储每日报告。

**集合名**: `daily_reports`

**文档结构**:
```json
{
  "_id": ObjectId,
  "report_date": "2026-03-17",
  "title": "舆情日报 - 2026年3月17日",
  "summary": "今日舆情摘要...",
  "statistics": {
    "total_documents": 5000,
    "sentiment_distribution": {
      "positive": 1500,
      "negative": 2000,
      "neutral": 1500
    },
    "top_events": 10,
    "top_keywords": ["选举", "政策"]
  },
  "highlights": [
    {
      "title": "重点事件1",
      "description": "描述...",
      "sentiment": "negative"
    }
  ],
  "content": "完整报告内容（Markdown）...",
  "format": "markdown",
  "generated_at": ISODate("2026-03-17T08:00:00Z"),
  "sent_to_feishu": true,
  "created_at": ISODate("2026-03-17T08:00:00Z")
}
```

---

## 三、Redis 数据库设计

### 3.1 数据结构设计

#### 3.1.1 缓存数据

| Key 模式 | 数据类型 | 说明 | TTL |
|----------|----------|------|-----|
| `cache:sentiment:{topic}:{date}` | Hash | 情感数据缓存 | 1小时 |
| `cache:document:{id}` | String | 文档缓存 | 24小时 |
| `cache:trend:{topic}` | List | 趋势数据缓存 | 1小时 |

#### 3.1.2 会话数据

| Key 模式 | 数据类型 | 说明 | TTL |
|----------|----------|------|-----|
| `session:{session_id}` | Hash | 会话数据 | 30分钟 |

#### 3.1.3 任务队列

| Key 模式 | 数据类型 | 说明 |
|----------|----------|------|
| `queue:collect` | List | 采集任务队列 |
| `queue:analyze` | List | 分析任务队列 |
| `queue:alert` | List | 预警任务队列 |

#### 3.1.4 统计计数

| Key 模式 | 数据类型 | 说明 |
|----------|----------|------|
| `stats:daily:{date}:documents` | String | 当日文档数 |
| `stats:daily:{date}:alerts` | String | 当日预警数 |
| `stats:realtime:active_users` | String | 实时活跃用户 |

### 3.2 示例数据

```redis
# 情感数据缓存
HSET cache:sentiment:选举:2026-03-17 positive 0.35 negative 0.45 neutral 0.20
EXPIRE cache:sentiment:选举:2026-03-17 3600

# 任务队列
LPUSH queue:collect '{"source":"twitter","keywords":["选举"],"priority":"high"}'

# 统计计数
INCR stats:daily:2026-03-17:documents
```

---

## 四、Milvus 向量数据库设计

### 4.1 Collection 设计

#### 4.1.1 文档向量集合 (document_vectors)

**Collection 名**: `document_vectors`

**字段定义**:
```python
from pymilvus import CollectionSchema, FieldSchema, DataType

fields = [
    FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
    FieldSchema(name="document_id", dtype=DataType.VARCHAR, max_length=100),
    FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=768),
    FieldSchema(name="source", dtype=DataType.VARCHAR, max_length=50),
    FieldSchema(name="published_at", dtype=DataType.INT64),  # timestamp
]

schema = CollectionSchema(fields, "文档向量集合")
```

**索引配置**:
```python
index_params = {
    "metric_type": "COSINE",
    "index_type": "IVF_FLAT",
    "params": {"nlist": 1024}
}
```

**用途**:
- 文本语义去重
- 相似文档检索
- 话题聚类

---

## 五、数据关系图

```
┌─────────────────────────────────────────────────────────────────┐
│                       数据关系图                                 │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────┐     1:1      ┌─────────────────┐
│  raw_documents  │ ──────────►  │processed_documents│
│  (原始数据)      │              │  (处理后数据)     │
└─────────────────┘              └─────────────────┘
                                         │
                                         │ 1:1
                                         ▼
                                ┌─────────────────┐
                                │ analysis_results │
                                │  (分析结果)      │
                                └─────────────────┘
                                         │
                                         │ N:1
                                         ▼
                                ┌─────────────────┐
                                │     events      │
                                │   (事件)        │
                                └─────────────────┘
                                         │
                                         │ 触发
                                         ▼
                                ┌─────────────────┐
                                │ alert_configs   │
                                │  (预警配置)     │
                                └─────────────────┘

┌─────────────────┐              ┌─────────────────┐
│ daily_reports   │              │ system_configs  │
│  (日报)         │              │  (系统配置)     │
└─────────────────┘              └─────────────────┘
```

---

## 六、数据迁移策略

### 6.1 初始化脚本

```javascript
// 初始化数据库和集合
use guzi_sentiment

// 创建集合
db.createCollection("raw_documents")
db.createCollection("processed_documents")
db.createCollection("analysis_results")
db.createCollection("events")
db.createCollection("alert_configs")
db.createCollection("system_configs")
db.createCollection("daily_reports")

// 创建索引（见上述各集合索引设计）
```

### 6.2 数据清理策略

| 集合 | 保留策略 | 清理方式 |
|------|----------|----------|
| raw_documents | 90 天 | TTL 索引自动清理 |
| processed_documents | 90 天 | 定时任务清理 |
| analysis_results | 永久 | 手动归档 |
| events | 永久 | 手动归档 |
| daily_reports | 永久 | 不清理 |

---

## 七、性能优化建议

### 7.1 MongoDB 优化

1. **分片策略**: 当数据量超过 1000 万时，按 `published_at` 分片
2. **读写分离**: 使用副本集实现读写分离
3. **索引优化**: 定期分析慢查询，优化索引

### 7.2 Redis 优化

1. **内存优化**: 使用合适的数据结构
2. **过期策略**: 设置合理的 TTL
3. **持久化**: 开启 RDB+AOF 混合持久化

### 7.3 Milvus 优化

1. **索引选择**: 根据数据量选择合适的索引类型
2. **批量插入**: 使用批量插入提高效率
3. **分区策略**: 按时间分区

---

*本文档由麻子 (Paperclip Agent) 生成，基于系统概要设计。*