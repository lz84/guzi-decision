"""
事件提取器

从文本中提取事件信息，包括事件类型、相关实体等。
"""

import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
import asyncio

from .models import Event, EventType, Entity, EntityType, SentimentResult


@dataclass
class EventExtractorConfig:
    """事件提取器配置"""
    # 提取方式: rule, llm
    method: str = "rule"
    # 语言
    language: str = "zh"
    # LLM 配置
    llm_model: str = "gpt-4"
    llm_api_key: Optional[str] = None
    # 最大文本长度
    max_text_length: int = 5000
    # 最小事件关键词数
    min_keywords: int = 2


class EventExtractor:
    """
    事件提取器
    
    从文本中识别和提取事件信息。
    """
    
    # 事件关键词映射
    EVENT_KEYWORDS_ZH = {
        EventType.ELECTION: [
            "选举", "投票", "候选人", "竞选", "总统", "议员", "大选",
            "primary", "投票率", "选票", "当选", "胜选",
        ],
        EventType.POLICY: [
            "政策", "法案", "立法", "通过", "否决", "签署", "实施",
            "规定", "条例", "法规", "改革", "措施",
        ],
        EventType.ECONOMIC: [
            "经济", "GDP", "增长", "衰退", "通胀", "利率", "降息",
            "加息", "就业", "失业", "股市", "汇市", "贸易",
        ],
        EventType.SCANDAL: [
            "丑闻", "贪污", "腐败", "贿赂", "泄密", "欺诈",
            "丑事", "内幕", "违规", "违法",
        ],
        EventType.DISASTER: [
            "灾难", "地震", "洪水", "台风", "火灾", "疫情",
            "事故", "爆炸", "坍塌", "海啸",
        ],
        EventType.CONFLICT: [
            "冲突", "战争", "军事", "攻击", "轰炸", "入侵",
            "制裁", "抗议", "示威", "暴力", "恐怖",
        ],
        EventType.TECHNOLOGY: [
            "科技", "技术", "创新", "AI", "人工智能", "芯片",
            "软件", "互联网", "数字化", "自动驾驶",
        ],
        EventType.HEALTH: [
            "健康", "医疗", "疾病", "疫苗", "药物", "医院",
            "治疗", "病毒", "疫情", "公共卫生",
        ],
    }
    
    # 事件触发词
    EVENT_TRIGGERS_ZH = [
        "宣布", "发布", "发生", "爆发", "通过", "否决",
        "签署", "实施", "启动", "暂停", "取消", "批准",
        "确认", "报道", "披露", "曝光", "揭露",
    ]
    
    # 影响力关键词
    IMPACT_KEYWORDS = {
        "高": ["重大", "重要", "关键", "突破", "历史性", "首次", "创纪录"],
        "中": ["显著", "明显", "较大", "积极", "消极"],
        "低": ["一般", "普通", "常规"],
    }
    
    def __init__(self, config: Optional[EventExtractorConfig] = None):
        self.config = config or EventExtractorConfig()
    
    async def extract(
        self,
        text: str,
        entities: Optional[list[Entity]] = None,
        sentiment: Optional[SentimentResult] = None,
        options: Optional[dict[str, Any]] = None
    ) -> list[Event]:
        """
        从文本中提取事件
        
        Args:
            text: 待分析文本
            entities: 已识别的实体
            sentiment: 情感分析结果
            options: 额外选项
            
        Returns:
            list: 提取的事件列表
        """
        options = options or {}
        
        # 截断过长的文本
        if len(text) > self.config.max_text_length:
            text = text[:self.config.max_text_length]
        
        # 根据配置选择提取方式
        method = options.get("method", self.config.method)
        
        if method == "llm":
            return await self._extract_by_llm(text, entities, sentiment, options)
        else:
            return await self._extract_by_rule(text, entities, sentiment)
    
    async def _extract_by_rule(
        self,
        text: str,
        entities: Optional[list[Entity]],
        sentiment: Optional[SentimentResult]
    ) -> list[Event]:
        """
        基于规则的事件提取
        
        Args:
            text: 待分析文本
            entities: 已识别的实体
            sentiment: 情感分析结果
            
        Returns:
            list: 事件列表
        """
        events = []
        
        # 获取相关实体
        related_entities = []
        if entities:
            related_entities = [
                e.text for e in entities
                if e.type in [EntityType.PERSON, EntityType.ORGANIZATION, EntityType.LOCATION]
            ]
        
        # 识别事件类型
        event_types = self._identify_event_types(text)
        
        # 查找事件触发词
        trigger_positions = []
        for trigger in self.EVENT_TRIGGERS_ZH:
            pos = text.find(trigger)
            if pos != -1:
                trigger_positions.append((trigger, pos))
        
        # 为每个事件类型创建事件
        for event_type in event_types:
            # 提取事件标题
            title = self._extract_title(text, trigger_positions)
            
            # 计算影响力分数
            impact_score = self._calculate_impact(text)
            
            # 创建事件
            event = Event(
                id=f"evt_{uuid.uuid4().hex[:12]}",
                type=event_type,
                title=title,
                description=text[:500],  # 截取前500字符作为描述
                entities=related_entities[:5],  # 最多5个相关实体
                sentiment=sentiment,
                impact_score=impact_score,
                confidence=self._calculate_confidence(text, event_type),
                created_at=datetime.now(),
            )
            events.append(event)
        
        return events
    
    def _identify_event_types(self, text: str) -> list[EventType]:
        """识别事件类型"""
        event_types = []
        
        for event_type, keywords in self.EVENT_KEYWORDS_ZH.items():
            keyword_count = sum(1 for kw in keywords if kw in text)
            if keyword_count >= self.config.min_keywords:
                event_types.append(event_type)
        
        # 如果没有识别到具体类型，但有事件触发词
        if not event_types:
            has_trigger = any(trigger in text for trigger in self.EVENT_TRIGGERS_ZH)
            if has_trigger:
                event_types.append(EventType.OTHER)
        
        return event_types
    
    def _extract_title(
        self,
        text: str,
        trigger_positions: list[tuple[str, int]]
    ) -> str:
        """提取事件标题"""
        if not trigger_positions:
            # 取第一句话作为标题
            sentences = re.split(r'[。！？\n]', text)
            if sentences:
                return sentences[0][:100]
            return text[:100]
        
        # 以第一个触发词为中心，提取上下文
        trigger, pos = trigger_positions[0]
        
        # 向前找到句首
        start = text.rfind('。', 0, pos)
        start = max(0, start + 1) if start != -1 else 0
        
        # 向后找到句末
        end = text.find('。', pos)
        if end == -1:
            end = len(text)
        else:
            end += 1
        
        # 提取标题
        title = text[start:end].strip()
        
        # 限制长度
        if len(title) > 100:
            title = title[:100] + "..."
        
        return title
    
    def _calculate_impact(self, text: str) -> float:
        """计算影响力分数"""
        # 基于关键词判断
        high_count = sum(1 for kw in self.IMPACT_KEYWORDS["高"] if kw in text)
        medium_count = sum(1 for kw in self.IMPACT_KEYWORDS["中"] if kw in text)
        
        # 计算分数
        score = 0.5  # 基础分
        score += high_count * 0.15
        score += medium_count * 0.05
        
        # 限制在 0-1 范围
        return min(max(score, 0.0), 1.0)
    
    def _calculate_confidence(
        self,
        text: str,
        event_type: EventType
    ) -> float:
        """计算置信度"""
        # 检查关键词匹配数量
        keywords = self.EVENT_KEYWORDS_ZH.get(event_type, [])
        keyword_count = sum(1 for kw in keywords if kw in text)
        
        # 检查是否有触发词
        has_trigger = any(trigger in text for trigger in self.EVENT_TRIGGERS_ZH)
        
        # 计算置信度
        confidence = 0.5
        confidence += min(keyword_count * 0.1, 0.3)
        if has_trigger:
            confidence += 0.1
        
        return min(confidence, 1.0)
    
    async def _extract_by_llm(
        self,
        text: str,
        entities: Optional[list[Entity]],
        sentiment: Optional[SentimentResult],
        options: dict[str, Any]
    ) -> list[Event]:
        """基于 LLM 的事件提取"""
        # 如果没有配置 LLM，回退到规则方法
        if not self.config.llm_api_key:
            return await self._extract_by_rule(text, entities, sentiment)
        
        # 这里应该调用 LLM API
        # 由于是示例，回退到规则方法
        return await self._extract_by_rule(text, entities, sentiment)
    
    async def extract_batch(
        self,
        texts: list[str],
        entities_list: Optional[list[list[Entity]]] = None,
        sentiments: Optional[list[SentimentResult]] = None,
        options: Optional[dict[str, Any]] = None
    ) -> list[list[Event]]:
        """批量提取事件"""
        results = []
        
        for i, text in enumerate(texts):
            entities = entities_list[i] if entities_list else None
            sentiment = sentiments[i] if sentiments else None
            
            events = await self.extract(text, entities, sentiment, options)
            results.append(events)
        
        return results
    
    def get_event_stats(
        self,
        events_list: list[list[Event]]
    ) -> dict[str, Any]:
        """获取事件统计"""
        total_events = sum(len(events) for events in events_list)
        
        type_counts = {}
        for events in events_list:
            for event in events:
                type_name = event.type.value
                type_counts[type_name] = type_counts.get(type_name, 0) + 1
        
        avg_impact = 0.0
        if total_events > 0:
            total_impact = sum(
                event.impact_score
                for events in events_list
                for event in events
            )
            avg_impact = total_impact / total_events
        
        return {
            "total_events": total_events,
            "avg_events_per_text": total_events / len(events_list) if events_list else 0,
            "type_distribution": type_counts,
            "avg_impact_score": avg_impact,
        }
    
    def filter_by_impact(
        self,
        events: list[Event],
        min_impact: float = 0.5
    ) -> list[Event]:
        """按影响力过滤事件"""
        return [e for e in events if e.impact_score >= min_impact]
    
    def filter_by_type(
        self,
        events: list[Event],
        event_types: list[EventType]
    ) -> list[Event]:
        """按类型过滤事件"""
        return [e for e in events if e.type in event_types]
    
    def sort_by_impact(
        self,
        events: list[Event],
        descending: bool = True
    ) -> list[Event]:
        """按影响力排序"""
        return sorted(events, key=lambda e: e.impact_score, reverse=descending)