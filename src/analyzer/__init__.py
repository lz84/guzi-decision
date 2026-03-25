"""
分析引擎模块

对文本进行情感分析、实体识别、事件提取等 NLP 分析。

模块结构:
- sentiment_analyzer: 情感分析
- entity_recognizer: 实体识别
- event_extractor: 事件提取
- models: 数据模型
- engine: 分析引擎
"""

from .models import (
    SentimentResult,
    SentimentLabel,
    Entity,
    EntityType,
    Event,
    EventType,
    AnalysisResult,
)
from .sentiment_analyzer import SentimentAnalyzer, SentimentAnalyzerConfig
from .entity_recognizer import EntityRecognizer, EntityRecognizerConfig
from .event_extractor import EventExtractor, EventExtractorConfig
from .engine import AnalysisEngine, AnalysisEngineConfig

__all__ = [
    # 情感分析
    "SentimentAnalyzer",
    "SentimentAnalyzerConfig",
    "SentimentResult",
    "SentimentLabel",
    # 实体识别
    "EntityRecognizer",
    "EntityRecognizerConfig",
    "Entity",
    "EntityType",
    # 事件提取
    "EventExtractor",
    "EventExtractorConfig",
    "Event",
    "EventType",
    # 分析引擎
    "AnalysisEngine",
    "AnalysisEngineConfig",
    "AnalysisResult",
]