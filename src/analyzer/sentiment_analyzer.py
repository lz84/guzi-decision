"""
情感分析器

对文本进行情感分析，支持多种模型和方案。
"""

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
import asyncio

from .models import SentimentResult, SentimentLabel


@dataclass
class SentimentAnalyzerConfig:
    """情感分析器配置"""
    # 分析模型类型: rule, llm, finbert
    model_type: str = "rule"
    # 语言
    language: str = "zh"
    # 是否启用方面级分析
    enable_aspect: bool = False
    # LLM 配置
    llm_model: str = "gpt-4"
    llm_api_key: Optional[str] = None
    llm_api_url: Optional[str] = None
    # 最大文本长度
    max_text_length: int = 5000
    # 批量大小
    batch_size: int = 10


class SentimentAnalyzer:
    """
    情感分析器
    
    支持多种分析方式:
    - rule: 基于规则的情感分析（快速，无需外部依赖）
    - llm: 基于大语言模型的分析（准确，需要 API）
    - finbert: 基于 FinBERT 模型（金融领域优化）
    """
    
    # 中文情感词典
    POSITIVE_WORDS_ZH = {
        "好", "棒", "优秀", "出色", "喜欢", "支持", "成功", "胜利",
        "增长", "上升", "收益", "盈利", "利好", "积极", "乐观", "繁荣",
        "创新", "突破", "领先", "优质", "稳定", "强劲", "反弹", "回暖",
    }
    
    NEGATIVE_WORDS_ZH = {
        "差", "坏", "糟糕", "失败", "损失", "下跌", "暴跌", "风险",
        "危机", "丑闻", "破产", "亏损", "利空", "消极", "悲观", "衰退",
        "下滑", "疲软", "动荡", "冲突", "制裁", "暴跌", "崩盘", "恐慌",
    }
    
    # 英文情感词典
    POSITIVE_WORDS_EN = {
        "good", "great", "excellent", "success", "win", "growth", "rise",
        "profit", "gain", "positive", "optimistic", "strong", "bullish",
        "breakthrough", "innovation", "leading", "stable", "recovery",
    }
    
    NEGATIVE_WORDS_EN = {
        "bad", "terrible", "failure", "loss", "fall", "drop", "crash",
        "risk", "crisis", "scandal", "bankruptcy", "negative", "pessimistic",
        "weak", "bearish", "recession", "conflict", "sanction", "panic",
    }
    
    # 否定词
    NEGATION_WORDS_ZH = {"不", "没", "无", "非", "未", "别", "莫", "勿"}
    NEGATION_WORDS_EN = {"not", "no", "never", "neither", "nobody", "nothing"}
    
    # 程度副词（加强/减弱）
    INTENSIFIERS_ZH = {
        "非常": 1.5, "极其": 2.0, "特别": 1.5, "相当": 1.3,
        "比较": 0.8, "稍微": 0.6, "有点": 0.5, "略微": 0.5,
    }
    INTENSIFIERS_EN = {
        "very": 1.5, "extremely": 2.0, "highly": 1.5, "quite": 1.3,
        "fairly": 0.8, "slightly": 0.6, "somewhat": 0.5, "a bit": 0.5,
    }
    
    def __init__(self, config: Optional[SentimentAnalyzerConfig] = None):
        self.config = config or SentimentAnalyzerConfig()
        self._model = None
    
    async def analyze(
        self,
        text: str,
        options: Optional[dict[str, Any]] = None
    ) -> SentimentResult:
        """
        分析文本情感
        
        Args:
            text: 待分析文本
            options: 额外选项
            
        Returns:
            SentimentResult: 情感分析结果
        """
        options = options or {}
        
        # 截断过长的文本
        if len(text) > self.config.max_text_length:
            text = text[:self.config.max_text_length]
        
        # 根据配置选择分析方式
        model_type = options.get("model_type", self.config.model_type)
        
        if model_type == "rule":
            return await self._analyze_by_rule(text)
        elif model_type == "llm":
            return await self._analyze_by_llm(text, options)
        elif model_type == "finbert":
            return await self._analyze_by_finbert(text)
        else:
            return await self._analyze_by_rule(text)
    
    async def _analyze_by_rule(self, text: str) -> SentimentResult:
        """
        基于规则的情感分析
        
        Args:
            text: 待分析文本
            
        Returns:
            SentimentResult: 分析结果
        """
        # 选择词典
        if self.config.language == "zh":
            positive_words = self.POSITIVE_WORDS_ZH
            negative_words = self.NEGATIVE_WORDS_ZH
            negation_words = self.NEGATION_WORDS_ZH
            intensifiers = self.INTENSIFIERS_ZH
        else:
            positive_words = self.POSITIVE_WORDS_EN
            negative_words = self.NEGATIVE_WORDS_EN
            negation_words = self.NEGATION_WORDS_EN
            intensifiers = self.INTENSIFIERS_EN
        
        # 分词（简单实现）
        words = self._tokenize(text)
        
        # 计算情感分数
        positive_count = 0
        negative_count = 0
        total_sentiment_words = 0
        
        i = 0
        while i < len(words):
            word = words[i]
            
            # 检查是否为情感词
            is_positive = word in positive_words
            is_negative = word in negative_words
            
            if is_positive or is_negative:
                total_sentiment_words += 1
                
                # 检查否定词
                has_negation = False
                for j in range(max(0, i - 3), i):
                    if words[j] in negation_words:
                        has_negation = True
                        break
                
                # 检查程度副词
                intensity = 1.0
                for j in range(max(0, i - 2), i):
                    if words[j] in intensifiers:
                        intensity = intensifiers[words[j]]
                        break
                
                # 计算分数
                if is_positive:
                    score = 1.0 * intensity
                    if has_negation:
                        score = -score
                    positive_count += max(0, score)
                    negative_count += max(0, -score)
                else:  # is_negative
                    score = 1.0 * intensity
                    if has_negation:
                        score = -score
                    negative_count += max(0, score)
                    positive_count += max(0, -score)
            
            i += 1
        
        # 计算综合分数
        total = positive_count + negative_count
        if total == 0:
            score = 0.0
            confidence = 0.5
            label = SentimentLabel.NEUTRAL
        else:
            score = (positive_count - negative_count) / total
            confidence = min(total / 10, 1.0)  # 情感词越多，置信度越高
            
            if score > 0.2:
                label = SentimentLabel.POSITIVE
            elif score < -0.2:
                label = SentimentLabel.NEGATIVE
            else:
                label = SentimentLabel.NEUTRAL
        
        # 计算各维度分数
        positive_score = positive_count / total if total > 0 else 0
        negative_score = negative_count / total if total > 0 else 0
        neutral_score = 1 - positive_score - negative_score
        
        return SentimentResult(
            label=label,
            score=score,
            confidence=confidence,
            positive_score=positive_score,
            negative_score=negative_score,
            neutral_score=max(0, neutral_score),
        )
    
    async def _analyze_by_llm(
        self,
        text: str,
        options: dict[str, Any]
    ) -> SentimentResult:
        """
        基于 LLM 的情感分析
        
        Args:
            text: 待分析文本
            options: 额外选项
            
        Returns:
            SentimentResult: 分析结果
        """
        # 如果没有配置 LLM，回退到规则方法
        if not self.config.llm_api_key:
            return await self._analyze_by_rule(text)
        
        try:
            # 这里应该调用 LLM API
            # 由于是示例，我们返回模拟结果
            return SentimentResult(
                label=SentimentLabel.NEUTRAL,
                score=0.0,
                confidence=0.9,
                positive_score=0.3,
                negative_score=0.3,
                neutral_score=0.4,
            )
        except Exception as e:
            # 出错时回退到规则方法
            return await self._analyze_by_rule(text)
    
    async def _analyze_by_finbert(self, text: str) -> SentimentResult:
        """
        基于 FinBERT 的情感分析
        
        Args:
            text: 待分析文本
            
        Returns:
            SentimentResult: 分析结果
        """
        # 如果没有加载模型，回退到规则方法
        if self._model is None:
            try:
                # 尝试加载 transformers
                from transformers import pipeline
                self._model = pipeline(
                    "sentiment-analysis",
                    model="ProsusAI/finbert",
                    device=-1  # CPU
                )
            except ImportError:
                return await self._analyze_by_rule(text)
        
        try:
            result = self._model(text)[0]
            
            label_map = {
                "positive": SentimentLabel.POSITIVE,
                "negative": SentimentLabel.NEGATIVE,
                "neutral": SentimentLabel.NEUTRAL,
            }
            
            label = label_map.get(result["label"].lower(), SentimentLabel.NEUTRAL)
            confidence = result["score"]
            
            # 计算分数
            if label == SentimentLabel.POSITIVE:
                score = confidence
            elif label == SentimentLabel.NEGATIVE:
                score = -confidence
            else:
                score = 0.0
            
            return SentimentResult(
                label=label,
                score=score,
                confidence=confidence,
                positive_score=confidence if label == SentimentLabel.POSITIVE else 0,
                negative_score=confidence if label == SentimentLabel.NEGATIVE else 0,
                neutral_score=confidence if label == SentimentLabel.NEUTRAL else 0,
            )
        except Exception as e:
            return await self._analyze_by_rule(text)
    
    def _tokenize(self, text: str) -> list[str]:
        """
        简单分词
        
        Args:
            text: 待分词文本
            
        Returns:
            list: 词列表
        """
        # 对于中文，按字符分割
        # 对于英文，按空格分割
        words = []
        current_word = ""
        
        for char in text:
            if '\u4e00' <= char <= '\u9fff':  # 中文字符
                if current_word:
                    words.extend(current_word.lower().split())
                    current_word = ""
                words.append(char)
            elif char.isalpha():
                current_word += char
            else:
                if current_word:
                    words.extend(current_word.lower().split())
                    current_word = ""
        
        if current_word:
            words.extend(current_word.lower().split())
        
        return words
    
    async def analyze_batch(
        self,
        texts: list[str],
        options: Optional[dict[str, Any]] = None
    ) -> list[SentimentResult]:
        """
        批量分析
        
        Args:
            texts: 文本列表
            options: 额外选项
            
        Returns:
            list: 分析结果列表
        """
        results = []
        for text in texts:
            result = await self.analyze(text, options)
            results.append(result)
        return results
    
    def get_sentiment_stats(
        self,
        results: list[SentimentResult]
    ) -> dict[str, Any]:
        """
        获取情感统计
        
        Args:
            results: 分析结果列表
            
        Returns:
            dict: 统计信息
        """
        total = len(results)
        if total == 0:
            return {
                "total": 0,
                "positive": 0,
                "negative": 0,
                "neutral": 0,
                "mixed": 0,
                "avg_score": 0.0,
                "avg_confidence": 0.0,
            }
        
        positive = sum(1 for r in results if r.label == SentimentLabel.POSITIVE)
        negative = sum(1 for r in results if r.label == SentimentLabel.NEGATIVE)
        neutral = sum(1 for r in results if r.label == SentimentLabel.NEUTRAL)
        mixed = sum(1 for r in results if r.label == SentimentLabel.MIXED)
        
        avg_score = sum(r.score for r in results) / total
        avg_confidence = sum(r.confidence for r in results) / total
        
        return {
            "total": total,
            "positive": positive,
            "negative": negative,
            "neutral": neutral,
            "mixed": mixed,
            "positive_rate": positive / total,
            "negative_rate": negative / total,
            "avg_score": avg_score,
            "avg_confidence": avg_confidence,
        }