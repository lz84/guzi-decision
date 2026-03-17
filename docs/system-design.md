# 谷子情报分析系统 - 概要设计

## 文档信息
- **项目名称**: 谷子情报分析系统
- **文档类型**: 系统概要设计说明书
- **版本**: 1.0
- **创建日期**: 2026-03-17
- **创建者**: 麻子 (Paperclip Agent)
- **Issue**: MAK-8 - 基于需求分析进一步设计

---

## 一、系统架构设计

### 1.1 总体架构

采用分层架构设计，从下到上分为：数据采集层、数据处理层、分析引擎层、存储层、服务层。

```
┌─────────────────────────────────────────────────────────────────────┐
│                           服务层 (Service Layer)                     │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │
│  │  REST API   │  │  预警服务   │  │  报告生成   │  │  调度服务   │ │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         分析引擎层 (Analysis Layer)                   │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │
│  │  情感分析   │  │  实体识别   │  │  事件提取   │  │  话题聚类   │ │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       数据处理层 (Processing Layer)                   │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │
│  │  数据清洗   │  │  文本去重   │  │  标准化     │  │  缓存管理   │ │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       数据采集层 (Collection Layer)                   │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │
│  │ agent-reach │  │tavily-search│  │  自研爬虫   │  │  代理管理   │ │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                          存储层 (Storage Layer)                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │
│  │  MongoDB    │  │  Redis      │  │  向量存储   │  │  文件存储   │ │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

### 1.2 技术架构

| 层级 | 技术选型 | 说明 |
|------|----------|------|
| **数据采集层** | agent-reach, tavily-search, Scrapy | 多源数据采集 |
| **数据处理层** | Python, pandas, numpy | 数据清洗与处理 |
| **分析引擎层** | transformers, spaCy, OpenAI API | NLP 分析 |
| **存储层** | MongoDB, Redis, Milvus | 多类型数据存储 |
| **服务层** | FastAPI, Celery, APScheduler | API 与调度 |

---

## 二、模块设计

### 2.1 数据采集模块 (collector)

#### 2.1.1 模块职责

负责从多个数据源采集舆情数据，统一输出为标准化格式。

#### 2.1.2 子模块设计

| 子模块 | 功能 | 实现方式 |
|--------|------|----------|
| `agent_reach_collector` | agent-reach 数据采集 | 调用 OpenClaw 技能 |
| `tavily_collector` | Tavily 搜索采集 | 调用 Tavily API |
| `custom_crawler` | 自定义爬虫 | Scrapy |
| `proxy_manager` | 代理 IP 管理 | 代理池 |

#### 2.1.3 数据流程

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│ 数据源配置   │ ──► │ 采集任务调度 │ ──► │ 数据采集执行 │
└──────────────┘     └──────────────┘     └──────────────┘
                                                │
                                                ▼
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│ 存储原始数据 │ ◄── │ 数据标准化   │ ◄── │ 采集结果     │
└──────────────┘     └──────────────┘     └──────────────┘
```

#### 2.1.4 接口定义

```python
class Collector(ABC):
    @abstractmethod
    async def collect(self, config: CollectorConfig) -> List[RawData]:
        """采集数据"""
        pass
    
    @abstractmethod
    async def test_connection(self) -> bool:
        """测试连接"""
        pass

class AgentReachCollector(Collector):
    """agent-reach 采集器"""
    pass

class TavilyCollector(Collector):
    """Tavily 搜索采集器"""
    pass
```

### 2.2 数据处理模块 (processor)

#### 2.2.1 模块职责

对原始数据进行清洗、去重、标准化处理。

#### 2.2.2 子模块设计

| 子模块 | 功能 | 实现方式 |
|--------|------|----------|
| `cleaner` | 数据清洗 | 正则、规则 |
| `deduplicator` | 文本去重 | 向量相似度 |
| `normalizer` | 数据标准化 | 格式转换 |
| `cache_manager` | 缓存管理 | Redis |

#### 2.2.3 数据处理流程

```
原始数据
    │
    ▼
┌──────────────┐
│ 数据清洗     │ ── 移除无效字符、HTML 标签
└──────────────┘
    │
    ▼
┌──────────────┐
│ 文本去重     │ ── 向量相似度 > 0.95 去重
└──────────────┘
    │
    ▼
┌──────────────┐
│ 数据标准化   │ ── 统一格式、字段映射
└──────────────┘
    │
    ▼
处理后数据
```

### 2.3 分析引擎模块 (analyzer)

#### 2.3.1 模块职责

对文本进行情感分析、实体识别、事件提取等 NLP 分析。

#### 2.3.2 子模块设计

| 子模块 | 功能 | 模型/方案 |
|--------|------|-----------|
| `sentiment_analyzer` | 情感分析 | FinBERT / GPT-4 |
| `entity_recognizer` | 实体识别 | spaCy / GPT-4 |
| `event_extractor` | 事件提取 | GPT-4 + 规则 |
| `topic_cluster` | 话题聚类 | BERT + KMeans |

#### 2.3.3 分析流程

```python
class AnalysisPipeline:
    """分析流水线"""
    
    async def analyze(self, text: str) -> AnalysisResult:
        # 1. 情感分析
        sentiment = await self.sentiment_analyzer.analyze(text)
        
        # 2. 实体识别
        entities = await self.entity_recognizer.recognize(text)
        
        # 3. 事件提取
        events = await self.event_extractor.extract(text, entities)
        
        return AnalysisResult(
            text=text,
            sentiment=sentiment,
            entities=entities,
            events=events
        )
```

#### 2.3.4 情感分析模型选择

| 场景 | 模型 | 准确率 | 成本 |
|------|------|--------|------|
| 实时分析 | FinBERT | 85% | 低 |
| 复杂分析 | GPT-4 | 95% | 高 |
| 混合方案 | FinBERT + GPT-4 | 90% | 中 |

### 2.4 存储模块 (storage)

#### 2.4.1 存储架构

```
┌─────────────────────────────────────────────────────────────────┐
│                         存储架构                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────┐  原始文档、处理后文档、分析结果               │
│  │  MongoDB    │  - 文档结构灵活                               │
│  │  文档存储   │  - 支持复杂查询                               │
│  └─────────────┘  - 水平扩展                                   │
│                                                                 │
│  ┌─────────────┐  缓存、会话、临时数据                         │
│  │  Redis      │  - 高速读写                                   │
│  │  缓存存储   │  - 支持过期                                   │
│  └─────────────┘  - 发布订阅                                   │
│                                                                 │
│  ┌─────────────┐  向量检索、语义搜索                           │
│  │  Milvus     │  - 高维向量存储                               │
│  │  向量存储   │  - 相似度检索                                 │
│  └─────────────┘  - 分布式部署                                 │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

#### 2.4.2 数据存储策略

| 数据类型 | 存储位置 | 保留策略 |
|----------|----------|----------|
| 原始数据 | MongoDB | 90 天 |
| 分析结果 | MongoDB | 永久 |
| 向量数据 | Milvus | 90 天 |
| 缓存数据 | Redis | 1-24 小时 |

### 2.5 服务模块 (service)

#### 2.5.1 API 服务设计

```
/api/v1
├── /sentiment
│   ├── GET /latest       # 获取最新情感数据
│   ├── GET /trend        # 获取情感趋势
│   └── GET /history      # 获取历史数据
├── /events
│   ├── GET /list         # 获取事件列表
│   ├── GET /{id}         # 获取事件详情
│   └── GET /alerts       # 获取预警事件
├── /reports
│   ├── GET /daily        # 获取日报
│   └── POST /generate    # 生成报告
└── /config
    ├── GET /keywords     # 获取关键词配置
    └── PUT /keywords     # 更新关键词配置
```

#### 2.5.2 预警服务设计

```python
class AlertService:
    """预警服务"""
    
    def __init__(self):
        self.rules = self.load_rules()
        self.notifiers = {
            'feishu': FeishuNotifier(),
            'webhook': WebhookNotifier(),
        }
    
    async def check_and_alert(self, analysis_result: AnalysisResult):
        """检查并触发预警"""
        for rule in self.rules:
            if rule.matches(analysis_result):
                alert = self.create_alert(rule, analysis_result)
                await self.send_alert(alert)
    
    async def send_alert(self, alert: Alert):
        """发送预警"""
        for channel in alert.channels:
            notifier = self.notifiers.get(channel)
            if notifier:
                await notifier.send(alert)
```

#### 2.5.3 调度服务设计

```python
class SchedulerService:
    """调度服务"""
    
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
    
    def setup_jobs(self):
        """设置定时任务"""
        # 每 5 分钟采集数据
        self.scheduler.add_job(
            collect_data,
            'interval',
            minutes=5,
            id='collect_data'
        )
        
        # 每日 8:00 生成日报
        self.scheduler.add_job(
            generate_daily_report,
            'cron',
            hour=8,
            minute=0,
            id='daily_report'
        )
```

---

## 三、接口设计

### 3.1 内部接口

#### 3.1.1 模块间通信

```
collector ──► processor ──► analyzer ──► storage
     │            │             │           │
     └────────────┴─────────────┴───────────┘
                    消息队列 (可选)
```

#### 3.1.2 模块接口定义

```python
# 数据采集接口
class CollectorInterface(Protocol):
    async def collect(self, source: str, keywords: List[str]) -> List[RawData]: ...

# 数据处理接口
class ProcessorInterface(Protocol):
    async def process(self, raw_data: List[RawData]) -> List[ProcessedData]: ...

# 分析引擎接口
class AnalyzerInterface(Protocol):
    async def analyze(self, text: str) -> AnalysisResult: ...

# 存储接口
class StorageInterface(Protocol):
    async def save(self, data: Any) -> str: ...
    async def query(self, query: dict) -> List[Any]: ...
```

### 3.2 外部接口 (REST API)

#### 3.2.1 情感数据接口

**GET /api/v1/sentiment/latest**

请求参数：
```json
{
  "topic": "选举",
  "hours": 24,
  "platform": "twitter"
}
```

响应示例：
```json
{
  "code": 0,
  "data": {
    "topic": "选举",
    "sentiment": {
      "positive": 0.35,
      "negative": 0.45,
      "neutral": 0.20
    },
    "trend": "declining",
    "volume": 15000,
    "timestamp": "2026-03-17T06:30:00Z"
  }
}
```

#### 3.2.2 事件列表接口

**GET /api/v1/events/list**

请求参数：
```json
{
  "start_date": "2026-03-01",
  "end_date": "2026-03-17",
  "event_type": "scandal",
  "page": 1,
  "page_size": 20
}
```

响应示例：
```json
{
  "code": 0,
  "data": {
    "total": 100,
    "page": 1,
    "page_size": 20,
    "events": [
      {
        "id": "evt_001",
        "type": "scandal",
        "title": "候选人A丑闻事件",
        "entities": ["候选人A"],
        "sentiment": -0.8,
        "impact_score": 0.85,
        "created_at": "2026-03-15T10:30:00Z"
      }
    ]
  }
}
```

---

## 四、数据流设计

### 4.1 主数据流

```
┌──────────────────────────────────────────────────────────────────┐
│                         主数据流                                  │
└──────────────────────────────────────────────────────────────────┘

外部数据源
    │
    │ 1. 定时采集 / 触发采集
    ▼
┌─────────────┐
│ 数据采集层  │ ── Twitter, Reddit, 新闻, YouTube
└─────────────┘
    │
    │ 2. 原始数据
    ▼
┌─────────────┐
│ 数据处理层  │ ── 清洗、去重、标准化
└─────────────┘
    │
    │ 3. 处理后数据
    ▼
┌─────────────┐
│ 分析引擎层  │ ── 情感分析、实体识别、事件提取
└─────────────┘
    │
    │ 4. 分析结果
    ▼
┌─────────────┐
│   存储层    │ ── MongoDB, Redis, Milvus
└─────────────┘
    │
    │ 5. 数据查询 / 预警触发
    ▼
┌─────────────┐
│   服务层    │ ── API, 预警, 报告
└─────────────┘
    │
    │ 6. 输出
    ▼
用户 / 谷子系统
```

### 4.2 预警数据流

```
分析结果
    │
    │ 规则匹配
    ▼
┌─────────────┐
│ 预警规则    │ ── 情感阈值、关键词、事件类型
└─────────────┘
    │
    │ 匹配成功
    ▼
┌─────────────┐
│ 预警生成    │ ── 创建预警消息
└─────────────┘
    │
    │ 发送预警
    ▼
┌─────────────┐
│ 预警通道    │ ── 飞书、Webhook、邮件
└─────────────┘
```

---

## 五、部署架构

### 5.1 单机部署（MVP 阶段）

```
┌─────────────────────────────────────────────────────────────────┐
│                       单机服务器                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    Docker Compose                        │   │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐       │   │
│  │  │ API服务 │ │调度服务 │ │ MongoDB │ │  Redis  │         │   │
│  │  │ :8000   │ │ (后台)  │ │ :27017  │ │ :6379   │         │   │
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘       │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 5.2 目录结构

```
guzi-decision/
├── src/
│   ├── collector/          # 数据采集模块
│   │   ├── agent_reach.py
│   │   ├── tavily.py
│   │   └── custom_crawler.py
│   ├── processor/          # 数据处理模块
│   │   ├── cleaner.py
│   │   ├── deduplicator.py
│   │   └── normalizer.py
│   ├── analyzer/           # 分析引擎模块
│   │   ├── sentiment.py
│   │   ├── entity.py
│   │   └── event.py
│   ├── storage/            # 存储模块
│   │   ├── mongodb.py
│   │   ├── redis.py
│   │   └── milvus.py
│   ├── service/            # 服务模块
│   │   ├── api.py
│   │   ├── alert.py
│   │   └── scheduler.py
│   └── main.py             # 主入口
├── config/                 # 配置文件
├── tests/                  # 测试代码
├── docs/                   # 文档
├── requirements.txt        # 依赖
├── docker-compose.yml      # Docker 配置
└── README.md
```

---

## 六、关键技术选型

### 6.1 数据采集技术

| 技术 | 用途 | 优势 |
|------|------|------|
| agent-reach | 社交媒体采集 | 已集成 14+ 平台 |
| tavily-search | 新闻搜索 | 高质量搜索结果 |
| Scrapy | 自定义爬虫 | 灵活可控 |

### 6.2 NLP 技术选型

| 技术 | 用途 | 优势 |
|------|------|------|
| FinBERT | 情感分析 | 金融领域优化 |
| spaCy | 实体识别 | 多语言支持 |
| OpenAI API | 复杂分析 | 高准确率 |

### 6.3 存储技术选型

| 技术 | 用途 | 优势 |
|------|------|------|
| MongoDB | 文档存储 | 灵活 schema |
| Redis | 缓存 | 高性能 |
| Milvus | 向量存储 | 高效相似度检索 |

---

*本文档由麻子 (Paperclip Agent) 生成，基于系统需求规格说明书。*