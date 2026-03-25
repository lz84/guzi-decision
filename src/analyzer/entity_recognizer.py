"""
实体识别器

从文本中识别命名实体，如人名、组织、地点等。
"""

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
import asyncio

from .models import Entity, EntityType


@dataclass
class EntityRecognizerConfig:
    """实体识别器配置"""
    # 模型类型: rule, spacy, llm
    model_type: str = "rule"
    # 语言
    language: str = "zh"
    # 要识别的实体类型
    entity_types: list[EntityType] = field(default_factory=lambda: [
        EntityType.PERSON,
        EntityType.ORGANIZATION,
        EntityType.LOCATION,
        EntityType.MONEY,
        EntityType.DATE,
    ])
    # LLM 配置
    llm_model: str = "gpt-4"
    llm_api_key: Optional[str] = None
    # 最大文本长度
    max_text_length: int = 5000
    # 最小实体长度
    min_entity_length: int = 2


class EntityRecognizer:
    """
    实体识别器
    
    支持多种识别方式:
    - rule: 基于规则的实体识别（快速）
    - spacy: 基于 spaCy 的 NER（准确）
    - llm: 基于大语言模型（最准确）
    """
    
    # 中文常见人名姓氏
    CHINESE_SURNAMES = {
        "王", "李", "张", "刘", "陈", "杨", "赵", "黄", "周", "吴",
        "徐", "孙", "胡", "朱", "高", "林", "何", "郭", "马", "罗",
        "梁", "宋", "郑", "谢", "韩", "唐", "冯", "于", "董", "萧",
        "程", "曹", "袁", "邓", "许", "傅", "沈", "曾", "彭", "吕",
        "苏", "卢", "蒋", "蔡", "贾", "丁", "魏", "薛", "叶", "阎",
    }
    
    # 常见组织名后缀
    ORG_SUFFIXES_ZH = {
        "公司", "集团", "企业", "银行", "证券", "基金", "保险",
        "协会", "研究院", "研究所", "大学", "学院", "医院",
        "政府", "部门", "局", "委员会", "议会", "国会",
    }
    
    ORG_SUFFIXES_EN = {
        "Inc", "Corp", "Company", "Corporation", "LLC", "Ltd",
        "Bank", "Fund", "Institute", "University", "College",
        "Association", "Organization", "Agency", "Department",
    }
    
    # 常见地名后缀
    LOC_SUFFIXES_ZH = {
        "省", "市", "县", "区", "镇", "乡", "村", "州",
        "岛", "半岛", "山脉", "河", "湖", "海", "洋",
    }
    
    # 常见地名
    COMMON_LOCATIONS_ZH = {
        "北京", "上海", "广州", "深圳", "杭州", "南京", "成都", "武汉",
        "西安", "重庆", "天津", "苏州", "长沙", "郑州", "青岛", "大连",
        "香港", "澳门", "台湾", "美国", "中国", "日本", "韩国", "英国",
        "法国", "德国", "俄罗斯", "印度", "巴西", "澳大利亚", "加拿大",
        "纽约", "伦敦", "东京", "巴黎", "柏林", "首尔", "新加坡", "迪拜",
    }
    
    # 金额模式
    MONEY_PATTERNS = [
        # 中文金额
        r'(\d+(?:\.\d+)?)\s*(亿|万|千|百)?元',
        r'(\d+(?:\.\d+)?)\s*(美元|欧元|日元|英镑)',
        r'(\d+(?:,\d{3})*(?:\.\d+)?)\s*(美元|USD|\$)',
        # 英文金额
        r'\$\s*(\d+(?:,\d{3})*(?:\.\d+)?)\s*(million|billion|trillion)?',
        r'(\d+(?:,\d{3})*(?:\.\d+)?)\s*(dollars|USD)',
    ]
    
    # 日期模式
    DATE_PATTERNS = [
        r'\d{4}年\d{1,2}月\d{1,2}日',
        r'\d{4}-\d{2}-\d{2}',
        r'\d{4}/\d{2}/\d{2}',
        r'\d{1,2}月\d{1,2}日',
        r'(今天|昨天|明天|前天|后天)',
        r'(上周|下周|本周)',
        r'(January|February|March|April|May|June|July|August|September|October|November|December)\s*\d{1,2},?\s*\d{4}',
    ]
    
    def __init__(self, config: Optional[EntityRecognizerConfig] = None):
        self.config = config or EntityRecognizerConfig()
        self._nlp = None
    
    async def recognize(
        self,
        text: str,
        options: Optional[dict[str, Any]] = None
    ) -> list[Entity]:
        """
        识别文本中的实体
        
        Args:
            text: 待分析文本
            options: 额外选项
            
        Returns:
            list: 识别到的实体列表
        """
        options = options or {}
        
        # 截断过长的文本
        if len(text) > self.config.max_text_length:
            text = text[:self.config.max_text_length]
        
        # 根据配置选择识别方式
        model_type = options.get("model_type", self.config.model_type)
        
        if model_type == "rule":
            return await self._recognize_by_rule(text)
        elif model_type == "spacy":
            return await self._recognize_by_spacy(text)
        elif model_type == "llm":
            return await self._recognize_by_llm(text, options)
        else:
            return await self._recognize_by_rule(text)
    
    async def _recognize_by_rule(self, text: str) -> list[Entity]:
        """
        基于规则的实体识别
        
        Args:
            text: 待分析文本
            
        Returns:
            list: 实体列表
        """
        entities = []
        
        # 识别金额
        if EntityType.MONEY in self.config.entity_types:
            entities.extend(self._recognize_money(text))
        
        # 识别日期
        if EntityType.DATE in self.config.entity_types:
            entities.extend(self._recognize_date(text))
        
        # 识别组织
        if EntityType.ORGANIZATION in self.config.entity_types:
            entities.extend(self._recognize_organization(text))
        
        # 识别地点
        if EntityType.LOCATION in self.config.entity_types:
            entities.extend(self._recognize_location(text))
        
        # 识别人名
        if EntityType.PERSON in self.config.entity_types:
            entities.extend(self._recognize_person(text))
        
        # 去重并排序
        entities = self._deduplicate(entities)
        entities.sort(key=lambda e: e.start)
        
        return entities
    
    def _recognize_money(self, text: str) -> list[Entity]:
        """识别金额"""
        entities = []
        
        for pattern in self.MONEY_PATTERNS:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                entity = Entity(
                    text=match.group(0),
                    type=EntityType.MONEY,
                    start=match.start(),
                    end=match.end(),
                    confidence=0.9,
                    normalized=match.group(0),
                )
                entities.append(entity)
        
        return entities
    
    def _recognize_date(self, text: str) -> list[Entity]:
        """识别日期"""
        entities = []
        
        for pattern in self.DATE_PATTERNS:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                entity = Entity(
                    text=match.group(0),
                    type=EntityType.DATE,
                    start=match.start(),
                    end=match.end(),
                    confidence=0.9,
                    normalized=match.group(0),
                )
                entities.append(entity)
        
        return entities
    
    def _recognize_organization(self, text: str) -> list[Entity]:
        """识别组织"""
        entities = []
        
        # 中文组织
        for suffix in self.ORG_SUFFIXES_ZH:
            pattern = rf'([^\s，。！？；：""''（）【】《》]{{2,10}}{suffix})'
            for match in re.finditer(pattern, text):
                entity = Entity(
                    text=match.group(0),
                    type=EntityType.ORGANIZATION,
                    start=match.start(),
                    end=match.end(),
                    confidence=0.8,
                )
                entities.append(entity)
        
        # 英文组织
        for suffix in self.ORG_SUFFIXES_EN:
            pattern = rf'([A-Z][A-Za-z\s]{{2,20}}\s{suffix}\b)'
            for match in re.finditer(pattern, text):
                entity = Entity(
                    text=match.group(0).strip(),
                    type=EntityType.ORGANIZATION,
                    start=match.start(),
                    end=match.end(),
                    confidence=0.8,
                )
                entities.append(entity)
        
        return entities
    
    def _recognize_location(self, text: str) -> list[Entity]:
        """识别地点"""
        entities = []
        
        # 常见地名
        for loc in self.COMMON_LOCATIONS_ZH:
            start = 0
            while True:
                pos = text.find(loc, start)
                if pos == -1:
                    break
                entity = Entity(
                    text=loc,
                    type=EntityType.LOCATION,
                    start=pos,
                    end=pos + len(loc),
                    confidence=0.9,
                )
                entities.append(entity)
                start = pos + len(loc)
        
        # 地名后缀模式
        for suffix in self.LOC_SUFFIXES_ZH:
            pattern = rf'([^\s，。！？；：""''（）【】《》]{{2,8}}{suffix})'
            for match in re.finditer(pattern, text):
                # 避免重复
                entity_text = match.group(0)
                if not any(e.text == entity_text for e in entities):
                    entity = Entity(
                        text=entity_text,
                        type=EntityType.LOCATION,
                        start=match.start(),
                        end=match.end(),
                        confidence=0.7,
                    )
                    entities.append(entity)
        
        return entities
    
    def _recognize_person(self, text: str) -> list[Entity]:
        """识别人名"""
        entities = []
        
        # 基于姓氏的人名识别（中文）
        for surname in self.CHINESE_SURNAMES:
            pattern = rf'{surname}([^\s，。！？；：""''（）【】《》]{{1,2}})'
            for match in re.finditer(pattern, text):
                name = match.group(0)
                if len(name) >= 2 and len(name) <= 4:
                    entity = Entity(
                        text=name,
                        type=EntityType.PERSON,
                        start=match.start(),
                        end=match.end(),
                        confidence=0.6,  # 较低的置信度
                    )
                    entities.append(entity)
        
        # 英文人名模式（大写开头 + 空格 + 大写开头）
        pattern = r'([A-Z][a-z]+\s+[A-Z][a-z]+)'
        for match in re.finditer(pattern, text):
            entity = Entity(
                text=match.group(0),
                type=EntityType.PERSON,
                start=match.start(),
                end=match.end(),
                confidence=0.7,
            )
            entities.append(entity)
        
        return entities
    
    async def _recognize_by_spacy(self, text: str) -> list[Entity]:
        """基于 spaCy 的实体识别"""
        if self._nlp is None:
            try:
                import spacy
                if self.config.language == "zh":
                    self._nlp = spacy.load("zh_core_web_sm")
                else:
                    self._nlp = spacy.load("en_core_web_sm")
            except ImportError:
                return await self._recognize_by_rule(text)
        
        try:
            doc = self._nlp(text)
            entities = []
            
            label_map = {
                "PERSON": EntityType.PERSON,
                "ORG": EntityType.ORGANIZATION,
                "GPE": EntityType.LOCATION,
                "LOC": EntityType.LOCATION,
                "MONEY": EntityType.MONEY,
                "DATE": EntityType.DATE,
                "TIME": EntityType.TIME,
                "PERCENT": EntityType.PERCENT,
                "QUANTITY": EntityType.QUANTITY,
                "PRODUCT": EntityType.PRODUCT,
                "EVENT": EntityType.EVENT,
            }
            
            for ent in doc.ents:
                entity_type = label_map.get(ent.label_, EntityType.MISC)
                if entity_type in self.config.entity_types:
                    entity = Entity(
                        text=ent.text,
                        type=entity_type,
                        start=ent.start_char,
                        end=ent.end_char,
                        confidence=0.85,
                    )
                    entities.append(entity)
            
            return entities
        except Exception:
            return await self._recognize_by_rule(text)
    
    async def _recognize_by_llm(
        self,
        text: str,
        options: dict[str, Any]
    ) -> list[Entity]:
        """基于 LLM 的实体识别"""
        # 如果没有配置 LLM，回退到规则方法
        if not self.config.llm_api_key:
            return await self._recognize_by_rule(text)
        
        # 这里应该调用 LLM API
        # 由于是示例，回退到规则方法
        return await self._recognize_by_rule(text)
    
    def _deduplicate(self, entities: list[Entity]) -> list[Entity]:
        """去重"""
        seen = set()
        result = []
        
        for entity in entities:
            key = (entity.text, entity.start, entity.end)
            if key not in seen:
                seen.add(key)
                result.append(entity)
        
        return result
    
    async def recognize_batch(
        self,
        texts: list[str],
        options: Optional[dict[str, Any]] = None
    ) -> list[list[Entity]]:
        """批量识别"""
        results = []
        for text in texts:
            entities = await self.recognize(text, options)
            results.append(entities)
        return results
    
    def get_entity_stats(
        self,
        entities_list: list[list[Entity]]
    ) -> dict[str, Any]:
        """获取实体统计"""
        total_entities = sum(len(entities) for entities in entities_list)
        
        type_counts = {}
        for entities in entities_list:
            for entity in entities:
                type_name = entity.type.value
                type_counts[type_name] = type_counts.get(type_name, 0) + 1
        
        return {
            "total_entities": total_entities,
            "avg_entities_per_text": total_entities / len(entities_list) if entities_list else 0,
            "type_distribution": type_counts,
        }