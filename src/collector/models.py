"""
数据采集模块 - 数据类型定义
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


class DataSource(str, Enum):
    """数据来源"""
    TWITTER = "twitter"
    REDDIT = "reddit"
    NEWS = "news"
    YOUTUBE = "youtube"
    WEIBO = "weibo"
    WECHAT = "wechat"
    UNKNOWN = "unknown"


class CollectStatus(str, Enum):
    """采集状态"""
    PENDING = "pending"         # 待采集
    RUNNING = "running"         # 采集中
    COMPLETED = "completed"     # 已完成
    FAILED = "failed"           # 失败
    CANCELLED = "cancelled"     # 已取消


@dataclass
class RawData:
    """原始数据结构"""
    id: str
    source: DataSource
    content: str
    title: Optional[str] = None
    author: Optional[str] = None
    url: Optional[str] = None
    published_at: Optional[datetime] = None
    collected_at: datetime = field(default_factory=datetime.now)
    language: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "source": self.source.value,
            "content": self.content,
            "title": self.title,
            "author": self.author,
            "url": self.url,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "collected_at": self.collected_at.isoformat() if self.collected_at else None,
            "language": self.language,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RawData":
        """从字典创建"""
        return cls(
            id=data.get("id", ""),
            source=DataSource(data.get("source", "unknown")),
            content=data.get("content", ""),
            title=data.get("title"),
            author=data.get("author"),
            url=data.get("url"),
            published_at=datetime.fromisoformat(data["published_at"]) if data.get("published_at") else None,
            collected_at=datetime.fromisoformat(data["collected_at"]) if data.get("collected_at") else datetime.now(),
            language=data.get("language"),
            metadata=data.get("metadata", {}),
        )


@dataclass
class CollectTask:
    """采集任务"""
    task_id: str
    source: DataSource
    keywords: list[str]
    status: CollectStatus = CollectStatus.PENDING
    limit: int = 100
    time_range: Optional[str] = None  # 如 "1h", "24h", "7d"
    options: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result_count: int = 0
    error_message: Optional[str] = None
    
    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "task_id": self.task_id,
            "source": self.source.value,
            "keywords": self.keywords,
            "status": self.status.value,
            "limit": self.limit,
            "time_range": self.time_range,
            "options": self.options,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "result_count": self.result_count,
            "error_message": self.error_message,
        }


@dataclass
class CollectStats:
    """采集统计"""
    total_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    total_items: int = 0
    avg_items_per_task: float = 0.0
    avg_time_per_task_ms: float = 0.0
    errors: list[dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "total_tasks": self.total_tasks,
            "completed_tasks": self.completed_tasks,
            "failed_tasks": self.failed_tasks,
            "total_items": self.total_items,
            "avg_items_per_task": self.avg_items_per_task,
            "avg_time_per_task_ms": self.avg_time_per_task_ms,
            "errors": self.errors,
        }