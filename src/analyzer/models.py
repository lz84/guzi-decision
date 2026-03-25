"""
分析引擎模块 - 数据类型定义
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


class SentimentLabel(str, Enum):
    """情感标签"""
    POSITIVE = "positive"      # 正面
    NEGATIVE = "negative"      # 负面
    NEUTRAL = "neutral"        # 中性
    MIXED = "mixed"            # 混合


class EntityType(str, Enum):
    """实体类型"""
    PERSON = "person"          # 人物
    ORGANIZATION = "organization"  # 组织
    LOCATION = "location"      # 地点
    EVENT = "event"            # 事件
    PRODUCT = "product"        # 产品
    MONEY = "money"            # 金额
    DATE = "date"              # 日期
    TIME = "time"              # 时间
    PERCENT = "percent"        # 百分比
    QUANTITY = "quantity"      # 数量
    MISC = "misc"              # 其他


class EventType(str, Enum):
    """事件类型"""
    ELECTION = "election"      # 选举
    POLICY = "policy"          # 政策
    ECONOMIC = "economic"      # 经济
    SCANDAL = "scandal"        # 丑闻
    DISASTER = "disaster"      # 灾难
    SPORTS = "sports"          # 体育
    ENTERTAINMENT = "entertainment"  # 娱乐
    TECHNOLOGY = "technology"  # 科技
    HEALTH = "health"          # 健康
    CONFLICT = "conflict"      # 冲突
    OTHER = "other"            # 其他


@dataclass
class SentimentResult:
    """情感分析结果"""
    label: SentimentLabel
    score: float  # -1.0 到 1.0，负面到正面
    confidence: float  # 0.0 到 1.0
    positive_score: float = 0.0
    negative_score: float = 0.0
    neutral_score: float = 0.0
    aspects: dict[str, float] = field(default_factory=dict)  # 方面级情感
    
    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "label": self.label.value,
            "score": self.score,
            "confidence": self.confidence,
            "positive_score": self.positive_score,
            "negative_score": self.negative_score,
            "neutral_score": self.neutral_score,
            "aspects": self.aspects,
        }


@dataclass
class Entity:
    """实体"""
    text: str
    type: EntityType
    start: int  # 起始位置
    end: int    # 结束位置
    confidence: float = 1.0
    normalized: Optional[str] = None  # 标准化名称
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "text": self.text,
            "type": self.type.value,
            "start": self.start,
            "end": self.end,
            "confidence": self.confidence,
            "normalized": self.normalized,
            "metadata": self.metadata,
        }


@dataclass
class Event:
    """事件"""
    id: str
    type: EventType
    title: str
    description: str
    entities: list[str]  # 相关实体
    sentiment: Optional[SentimentResult] = None
    impact_score: float = 0.0  # 影响力分数 0-1
    confidence: float = 0.0
    source_url: Optional[str] = None
    published_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "type": self.type.value,
            "title": self.title,
            "description": self.description,
            "entities": self.entities,
            "sentiment": self.sentiment.to_dict() if self.sentiment else None,
            "impact_score": self.impact_score,
            "confidence": self.confidence,
            "source_url": self.source_url,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "metadata": self.metadata,
        }


@dataclass
class AnalysisResult:
    """综合分析结果"""
    text: str
    sentiment: Optional[SentimentResult] = None
    entities: list[Entity] = field(default_factory=list)
    events: list[Event] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    topics: list[str] = field(default_factory=list)
    language: Optional[str] = None
    processed_at: datetime = field(default_factory=datetime.now)
    processing_time_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "text": self.text,
            "sentiment": self.sentiment.to_dict() if self.sentiment else None,
            "entities": [e.to_dict() for e in self.entities],
            "events": [e.to_dict() for e in self.events],
            "keywords": self.keywords,
            "topics": self.topics,
            "language": self.language,
            "processed_at": self.processed_at.isoformat() if self.processed_at else None,
            "processing_time_ms": self.processing_time_ms,
            "metadata": self.metadata,
        }
    
    def get_sentiment_score(self) -> float:
        """获取情感分数"""
        return self.sentiment.score if self.sentiment else 0.0
    
    def get_main_entities(self, limit: int = 5) -> list[Entity]:
        """获取主要实体"""
        # 按置信度排序
        sorted_entities = sorted(
            self.entities,
            key=lambda e: e.confidence,
            reverse=True
        )
        return sorted_entities[:limit]
    
    def get_events_by_type(self, event_type: EventType) -> list[Event]:
        """按类型获取事件"""
        return [e for e in self.events if e.type == event_type]


@dataclass
class BatchAnalysisResult:
    """批量分析结果"""
    results: list[AnalysisResult]
    total_count: int
    success_count: int
    failed_count: int
    avg_sentiment_score: float = 0.0
    processing_time_ms: float = 0.0
    
    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "results": [r.to_dict() for r in self.results],
            "total_count": self.total_count,
            "success_count": self.success_count,
            "failed_count": self.failed_count,
            "avg_sentiment_score": self.avg_sentiment_score,
            "processing_time_ms": self.processing_time_ms,
        }
    
    def get_sentiment_distribution(self) -> dict[str, int]:
        """获取情感分布"""
        distribution = {
            "positive": 0,
            "negative": 0,
            "neutral": 0,
            "mixed": 0,
        }
        
        for result in self.results:
            if result.sentiment:
                label = result.sentiment.label.value
                if label in distribution:
                    distribution[label] += 1
        
        return distribution