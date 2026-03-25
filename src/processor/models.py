"""
数据处理模块 - 数据类型定义
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
    UNKNOWN = "unknown"


class DataStatus(str, Enum):
    """数据状态"""
    RAW = "raw"              # 原始数据
    CLEANED = "cleaned"       # 已清洗
    DEDUPLICATED = "deduplicated"  # 已去重
    NORMALIZED = "normalized"  # 已标准化
    PROCESSED = "processed"    # 已完成处理


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
            "metadata": self.metadata,
        }


@dataclass
class ProcessedData:
    """处理后数据结构"""
    id: str
    source: DataSource
    original_content: str
    cleaned_content: str
    title: Optional[str] = None
    author: Optional[str] = None
    url: Optional[str] = None
    published_at: Optional[datetime] = None
    collected_at: Optional[datetime] = None
    processed_at: datetime = field(default_factory=datetime.now)
    status: DataStatus = DataStatus.PROCESSED
    is_duplicate: bool = False
    duplicate_of: Optional[str] = None
    quality_score: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "source": self.source.value,
            "original_content": self.original_content,
            "cleaned_content": self.cleaned_content,
            "title": self.title,
            "author": self.author,
            "url": self.url,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "collected_at": self.collected_at.isoformat() if self.collected_at else None,
            "processed_at": self.processed_at.isoformat() if self.processed_at else None,
            "status": self.status.value,
            "is_duplicate": self.is_duplicate,
            "duplicate_of": self.duplicate_of,
            "quality_score": self.quality_score,
            "metadata": self.metadata,
        }


@dataclass
class ProcessingStats:
    """处理统计"""
    total_input: int = 0
    total_output: int = 0
    duplicates_removed: int = 0
    invalid_removed: int = 0
    processing_time_ms: float = 0.0
    
    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "total_input": self.total_input,
            "total_output": self.total_output,
            "duplicates_removed": self.duplicates_removed,
            "invalid_removed": self.invalid_removed,
            "processing_time_ms": self.processing_time_ms,
        }