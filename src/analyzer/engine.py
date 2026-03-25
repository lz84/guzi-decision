"""
分析引擎

协调情感分析、实体识别、事件提取等组件，提供综合分析能力。
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
import uuid

from .models import (
    AnalysisResult,
    BatchAnalysisResult,
    SentimentResult,
    Entity,
    Event,
)
from .sentiment_analyzer import SentimentAnalyzer, SentimentAnalyzerConfig
from .entity_recognizer import EntityRecognizer, EntityRecognizerConfig
from .event_extractor import EventExtractor, EventExtractorConfig


@dataclass
class AnalysisEngineConfig:
    """分析引擎配置"""
    # 是否启用情感分析
    enable_sentiment: bool = True
    # 是否启用实体识别
    enable_entities: bool = True
    # 是否启用事件提取
    enable_events: bool = True
    # 是否启用关键词提取
    enable_keywords: bool = True
    # 语言
    language: str = "zh"
    # 最大文本长度
    max_text_length: int = 5000
    # 并行处理
    parallel: bool = True
    # 情感分析配置
    sentiment_config: Optional[SentimentAnalyzerConfig] = None
    # 实体识别配置
    entity_config: Optional[EntityRecognizerConfig] = None
    # 事件提取配置
    event_config: Optional[EventExtractorConfig] = None


class AnalysisEngine:
    """
    分析引擎
    
    提供文本分析的综合能力，包括：
    - 情感分析
    - 实体识别
    - 事件提取
    - 关键词提取
    """
    
    def __init__(self, config: Optional[AnalysisEngineConfig] = None):
        self.config = config or AnalysisEngineConfig()
    
    async def initialize(self) -> None:
        """初始化引擎（兼容性方法）"""
        # 各组件在 __init__ 中已初始化，这里不做额外操作
        pass
        
        # 初始化各组件
        self.sentiment_analyzer = SentimentAnalyzer(
            self.config.sentiment_config or SentimentAnalyzerConfig(
                language=self.config.language
            )
        )
        
        self.entity_recognizer = EntityRecognizer(
            self.config.entity_config or EntityRecognizerConfig(
                language=self.config.language
            )
        )
        
        self.event_extractor = EventExtractor(
            self.config.event_config or EventExtractorConfig(
                language=self.config.language
            )
        )
    
    async def analyze(
        self,
        text: str,
        options: Optional[dict[str, Any]] = None
    ) -> AnalysisResult:
        """
        综合分析文本
        
        Args:
            text: 待分析文本
            options: 额外选项
                - enable_sentiment: 是否启用情感分析
                - enable_entities: 是否启用实体识别
                - enable_events: 是否启用事件提取
                - enable_keywords: 是否启用关键词提取
                
        Returns:
            AnalysisResult: 分析结果
        """
        start_time = datetime.now()
        options = options or {}
        
        # 截断过长的文本
        original_text = text
        if len(text) > self.config.max_text_length:
            text = text[:self.config.max_text_length]
        
        # 确定启用的分析项
        enable_sentiment = options.get(
            "enable_sentiment",
            self.config.enable_sentiment
        )
        enable_entities = options.get(
            "enable_entities",
            self.config.enable_entities
        )
        enable_events = options.get(
            "enable_events",
            self.config.enable_events
        )
        enable_keywords = options.get(
            "enable_keywords",
            self.config.enable_keywords
        )
        
        # 初始化结果
        sentiment: Optional[SentimentResult] = None
        entities: list[Entity] = []
        events: list[Event] = []
        keywords: list[str] = []
        
        try:
            if self.config.parallel:
                # 并行分析
                tasks = []
                
                if enable_sentiment:
                    tasks.append(self._analyze_sentiment(text, options))
                else:
                    tasks.append(self._empty_sentiment())
                
                if enable_entities:
                    tasks.append(self._recognize_entities(text, options))
                else:
                    tasks.append(self._empty_entities())
                
                results = await asyncio.gather(*tasks)
                
                if enable_sentiment:
                    sentiment = results[0]
                if enable_entities:
                    entities = results[1] if len(results) > 1 else []
                
                # 事件提取依赖实体识别结果
                if enable_events:
                    events = await self._extract_events(text, entities, sentiment, options)
            else:
                # 串行分析
                if enable_sentiment:
                    sentiment = await self.sentiment_analyzer.analyze(text, options)
                
                if enable_entities:
                    entities = await self.entity_recognizer.recognize(text, options)
                
                if enable_events:
                    events = await self.event_extractor.extract(
                        text, entities, sentiment, options
                    )
            
            # 关键词提取
            if enable_keywords:
                keywords = self._extract_keywords(text, entities)
            
        except Exception as e:
            # 记录错误但继续
            pass
        
        processing_time = (datetime.now() - start_time).total_seconds() * 1000
        
        return AnalysisResult(
            text=original_text[:self.config.max_text_length],
            sentiment=sentiment,
            entities=entities,
            events=events,
            keywords=keywords,
            topics=self._extract_topics(events),
            language=self.config.language,
            processed_at=datetime.now(),
            processing_time_ms=processing_time,
        )
    
    async def _analyze_sentiment(
        self,
        text: str,
        options: dict[str, Any]
    ) -> SentimentResult:
        """情感分析"""
        return await self.sentiment_analyzer.analyze(text, options)
    
    async def _recognize_entities(
        self,
        text: str,
        options: dict[str, Any]
    ) -> list[Entity]:
        """实体识别"""
        return await self.entity_recognizer.recognize(text, options)
    
    async def _extract_events(
        self,
        text: str,
        entities: list[Entity],
        sentiment: Optional[SentimentResult],
        options: dict[str, Any]
    ) -> list[Event]:
        """事件提取"""
        return await self.event_extractor.extract(text, entities, sentiment, options)
    
    async def _empty_sentiment(self) -> None:
        """空情感分析"""
        return None
    
    async def _empty_entities(self) -> list[Entity]:
        """空实体识别"""
        return []
    
    def _extract_keywords(
        self,
        text: str,
        entities: list[Entity]
    ) -> list[str]:
        """
        提取关键词
        
        Args:
            text: 文本
            entities: 已识别的实体
            
        Returns:
            list: 关键词列表
        """
        keywords = []
        
        # 实体作为关键词
        for entity in entities:
            if entity.text not in keywords:
                keywords.append(entity.text)
        
        # 简单的关键词提取（基于词频）
        # 这里只是示例，实际应该使用更复杂的方法
        import re
        words = re.findall(r'[\u4e00-\u9fff]{2,4}', text)
        
        # 过滤常见词
        stopwords = {"的是", "不是", "只是", "还是", "也是", "都是", "就是"}
        
        word_freq: dict[str, int] = {}
        for word in words:
            if word not in stopwords and len(word) >= 2:
                word_freq[word] = word_freq.get(word, 0) + 1
        
        # 按词频排序
        sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
        
        for word, freq in sorted_words[:10]:  # 最多10个
            if word not in keywords:
                keywords.append(word)
        
        return keywords[:15]  # 最多返回15个关键词
    
    def _extract_topics(self, events: list[Event]) -> list[str]:
        """从事件中提取主题"""
        topics = []
        for event in events:
            topic = event.type.value
            if topic not in topics:
                topics.append(topic)
        return topics
    
    async def analyze_batch(
        self,
        texts: list[str],
        options: Optional[dict[str, Any]] = None
    ) -> BatchAnalysisResult:
        """
        批量分析文本
        
        Args:
            texts: 文本列表
            options: 额外选项
            
        Returns:
            BatchAnalysisResult: 批量分析结果
        """
        start_time = datetime.now()
        
        results = []
        for text in texts:
            result = await self.analyze(text, options)
            results.append(result)
        
        # 计算统计信息
        total_count = len(results)
        success_count = sum(1 for r in results if r.sentiment is not None)
        failed_count = total_count - success_count
        
        avg_sentiment_score = 0.0
        if success_count > 0:
            total_score = sum(
                r.get_sentiment_score()
                for r in results
                if r.sentiment is not None
            )
            avg_sentiment_score = total_score / success_count
        
        processing_time = (datetime.now() - start_time).total_seconds() * 1000
        
        return BatchAnalysisResult(
            results=results,
            total_count=total_count,
            success_count=success_count,
            failed_count=failed_count,
            avg_sentiment_score=avg_sentiment_score,
            processing_time_ms=processing_time,
        )
    
    async def analyze_sentiment_only(
        self,
        text: str,
        options: Optional[dict[str, Any]] = None
    ) -> SentimentResult:
        """仅进行情感分析"""
        return await self.sentiment_analyzer.analyze(text, options)
    
    async def analyze_entities_only(
        self,
        text: str,
        options: Optional[dict[str, Any]] = None
    ) -> list[Entity]:
        """仅进行实体识别"""
        return await self.entity_recognizer.recognize(text, options)
    
    async def analyze_events_only(
        self,
        text: str,
        options: Optional[dict[str, Any]] = None
    ) -> list[Event]:
        """仅进行事件提取"""
        return await self.event_extractor.extract(text, None, None, options)
    
    def get_stats(self) -> dict[str, Any]:
        """获取引擎统计信息"""
        return {
            "config": {
                "enable_sentiment": self.config.enable_sentiment,
                "enable_entities": self.config.enable_entities,
                "enable_events": self.config.enable_events,
                "enable_keywords": self.config.enable_keywords,
                "language": self.config.language,
                "parallel": self.config.parallel,
            },
            "components": {
                "sentiment_analyzer": type(self.sentiment_analyzer).__name__,
                "entity_recognizer": type(self.entity_recognizer).__name__,
                "event_extractor": type(self.event_extractor).__name__,
            }
        }