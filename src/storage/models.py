"""
存储模块 - 数据类型定义
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


class DocumentStatus(str, Enum):
    """文档状态"""
    RAW = "raw"                # 原始采集
    PROCESSING = "processing"  # 处理中
    ANALYZED = "analyzed"      # 已分析
    ARCHIVED = "archived"      # 已归档
    DELETED = "deleted"        # 已删除


class AlertLevel(str, Enum):
    """预警级别"""
    CRITICAL = "critical"  # 严重
    HIGH = "high"          # 高
    MEDIUM = "medium"      # 中
    LOW = "low"            # 低
    INFO = "info"          # 信息


class ReportType(str, Enum):
    """报告类型"""
    DAILY = "daily"        # 日报
    WEEKLY = "weekly"      # 周报
    MONTHLY = "monthly"    # 月报
    SPECIAL = "special"    # 专题报告


@dataclass
class StoredDocument:
    """存储的文档"""
    id: str
    source: str
    content: str
    title: Optional[str] = None
    author: Optional[str] = None
    url: Optional[str] = None
    published_at: Optional[datetime] = None
    collected_at: datetime = field(default_factory=datetime.now)
    processed_at: Optional[datetime] = None
    status: DocumentStatus = DocumentStatus.RAW
    language: Optional[str] = None
    sentiment_score: Optional[float] = None
    sentiment_label: Optional[str] = None
    entities: list[dict[str, Any]] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    quality_score: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "source": self.source,
            "content": self.content,
            "title": self.title,
            "author": self.author,
            "url": self.url,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "collected_at": self.collected_at.isoformat() if self.collected_at else None,
            "processed_at": self.processed_at.isoformat() if self.processed_at else None,
            "status": self.status.value,
            "language": self.language,
            "sentiment_score": self.sentiment_score,
            "sentiment_label": self.sentiment_label,
            "entities": self.entities,
            "keywords": self.keywords,
            "quality_score": self.quality_score,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StoredDocument":
        """从字典创建"""
        return cls(
            id=data.get("id", ""),
            source=data.get("source", ""),
            content=data.get("content", ""),
            title=data.get("title"),
            author=data.get("author"),
            url=data.get("url"),
            published_at=datetime.fromisoformat(data["published_at"]) if data.get("published_at") else None,
            collected_at=datetime.fromisoformat(data["collected_at"]) if data.get("collected_at") else datetime.now(),
            processed_at=datetime.fromisoformat(data["processed_at"]) if data.get("processed_at") else None,
            status=DocumentStatus(data.get("status", "raw")),
            language=data.get("language"),
            sentiment_score=data.get("sentiment_score"),
            sentiment_label=data.get("sentiment_label"),
            entities=data.get("entities", []),
            keywords=data.get("keywords", []),
            quality_score=data.get("quality_score", 1.0),
            metadata=data.get("metadata", {}),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.now(),
            updated_at=datetime.fromisoformat(data["updated_at"]) if data.get("updated_at") else datetime.now(),
        )


@dataclass
class StoredAnalysis:
    """存储的分析结果"""
    id: str
    document_id: str
    text: str
    sentiment_label: Optional[str] = None
    sentiment_score: Optional[float] = None
    confidence: float = 0.0
    entities: list[dict[str, Any]] = field(default_factory=list)
    events: list[dict[str, Any]] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    topics: list[str] = field(default_factory=list)
    language: Optional[str] = None
    processing_time_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "document_id": self.document_id,
            "text": self.text,
            "sentiment_label": self.sentiment_label,
            "sentiment_score": self.sentiment_score,
            "confidence": self.confidence,
            "entities": self.entities,
            "events": self.events,
            "keywords": self.keywords,
            "topics": self.topics,
            "language": self.language,
            "processing_time_ms": self.processing_time_ms,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StoredAnalysis":
        """从字典创建"""
        return cls(
            id=data.get("id", ""),
            document_id=data.get("document_id", ""),
            text=data.get("text", ""),
            sentiment_label=data.get("sentiment_label"),
            sentiment_score=data.get("sentiment_score"),
            confidence=data.get("confidence", 0.0),
            entities=data.get("entities", []),
            events=data.get("events", []),
            keywords=data.get("keywords", []),
            topics=data.get("topics", []),
            language=data.get("language"),
            processing_time_ms=data.get("processing_time_ms", 0.0),
            metadata=data.get("metadata", {}),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.now(),
        )


@dataclass
class StoredAlert:
    """存储的预警"""
    id: str
    level: AlertLevel
    title: str
    message: str
    source: Optional[str] = None
    document_id: Optional[str] = None
    keywords: list[str] = field(default_factory=list)
    sentiment_score: Optional[float] = None
    triggered_at: datetime = field(default_factory=datetime.now)
    acknowledged: bool = False
    acknowledged_at: Optional[datetime] = None
    acknowledged_by: Optional[str] = None
    notification_sent: bool = False
    notification_channels: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "level": self.level.value,
            "title": self.title,
            "message": self.message,
            "source": self.source,
            "document_id": self.document_id,
            "keywords": self.keywords,
            "sentiment_score": self.sentiment_score,
            "triggered_at": self.triggered_at.isoformat() if self.triggered_at else None,
            "acknowledged": self.acknowledged,
            "acknowledged_at": self.acknowledged_at.isoformat() if self.acknowledged_at else None,
            "acknowledged_by": self.acknowledged_by,
            "notification_sent": self.notification_sent,
            "notification_channels": self.notification_channels,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StoredAlert":
        """从字典创建"""
        return cls(
            id=data.get("id", ""),
            level=AlertLevel(data.get("level", "info")),
            title=data.get("title", ""),
            message=data.get("message", ""),
            source=data.get("source"),
            document_id=data.get("document_id"),
            keywords=data.get("keywords", []),
            sentiment_score=data.get("sentiment_score"),
            triggered_at=datetime.fromisoformat(data["triggered_at"]) if data.get("triggered_at") else datetime.now(),
            acknowledged=data.get("acknowledged", False),
            acknowledged_at=datetime.fromisoformat(data["acknowledged_at"]) if data.get("acknowledged_at") else None,
            acknowledged_by=data.get("acknowledged_by"),
            notification_sent=data.get("notification_sent", False),
            notification_channels=data.get("notification_channels", []),
            metadata=data.get("metadata", {}),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.now(),
        )


@dataclass
class StoredReport:
    """存储的报告"""
    id: str
    report_type: ReportType
    title: str
    content: str
    date: str  # 日期标识，如 "2024-01-15"
    summary: Optional[str] = None
    total_documents: int = 0
    sentiment_distribution: dict[str, int] = field(default_factory=dict)
    top_keywords: list[str] = field(default_factory=list)
    top_entities: list[str] = field(default_factory=list)
    alerts_count: int = 0
    generated_at: datetime = field(default_factory=datetime.now)
    file_path: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "report_type": self.report_type.value,
            "title": self.title,
            "content": self.content,
            "summary": self.summary,
            "date": self.date,
            "total_documents": self.total_documents,
            "sentiment_distribution": self.sentiment_distribution,
            "top_keywords": self.top_keywords,
            "top_entities": self.top_entities,
            "alerts_count": self.alerts_count,
            "generated_at": self.generated_at.isoformat() if self.generated_at else None,
            "file_path": self.file_path,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StoredReport":
        """从字典创建"""
        return cls(
            id=data.get("id", ""),
            report_type=ReportType(data.get("report_type", "daily")),
            title=data.get("title", ""),
            content=data.get("content", ""),
            summary=data.get("summary"),
            date=data.get("date", ""),
            total_documents=data.get("total_documents", 0),
            sentiment_distribution=data.get("sentiment_distribution", {}),
            top_keywords=data.get("top_keywords", []),
            top_entities=data.get("top_entities", []),
            alerts_count=data.get("alerts_count", 0),
            generated_at=datetime.fromisoformat(data["generated_at"]) if data.get("generated_at") else datetime.now(),
            file_path=data.get("file_path"),
            metadata=data.get("metadata", {}),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.now(),
        )