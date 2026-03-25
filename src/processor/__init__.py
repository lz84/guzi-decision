"""
数据处理模块

对原始数据进行清洗、去重、标准化处理。

模块结构:
- cleaner: 数据清洗
- deduplicator: 文本去重
- normalizer: 数据标准化
- pipeline: 处理管道
- models: 数据模型
"""

from .cleaner import DataCleaner, CleanerConfig, CleaningResult
from .deduplicator import TextDeduplicator, DeduplicatorConfig, DeduplicationResult
from .normalizer import DataNormalizer, NormalizerConfig, NormalizationResult
from .pipeline import DataProcessingPipeline, PipelineConfig, PipelineResult
from .models import (
    RawData,
    ProcessedData,
    ProcessingStats,
    DataSource,
    DataStatus,
)

__all__ = [
    # 清洗模块
    "DataCleaner",
    "CleanerConfig",
    "CleaningResult",
    # 去重模块
    "TextDeduplicator",
    "DeduplicatorConfig",
    "DeduplicationResult",
    # 标准化模块
    "DataNormalizer",
    "NormalizerConfig",
    "NormalizationResult",
    # 管道
    "DataProcessingPipeline",
    "PipelineConfig",
    "PipelineResult",
    # 数据模型
    "RawData",
    "ProcessedData",
    "ProcessingStats",
    "DataSource",
    "DataStatus",
]