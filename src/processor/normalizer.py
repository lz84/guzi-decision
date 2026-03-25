"""
数据标准化模块

功能:
- 统一数据格式
- 字段映射
- 时间格式标准化
- 语言检测
- 数据质量评估
"""

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
from enum import Enum


class DataFormat(str, Enum):
    """数据格式"""
    STANDARD = "standard"      # 标准格式
    TWITTER = "twitter"        # Twitter 格式
    REDDIT = "reddit"          # Reddit 格式
    NEWS = "news"              # 新闻格式
    WEIBO = "weibo"            # 微博格式
    YOUTUBE = "youtube"        # YouTube 格式
    CUSTOM = "custom"          # 自定义格式


@dataclass
class NormalizerConfig:
    """标准化配置"""
    # 目标格式
    target_format: DataFormat = DataFormat.STANDARD
    # 时区
    timezone: str = "UTC"
    # 语言检测
    detect_language: bool = True
    # 是否计算质量分数
    compute_quality_score: bool = True
    # 最小内容长度
    min_content_length: int = 10
    # 日期格式
    date_format: str = "%Y-%m-%dT%H:%M:%SZ"
    # 是否保留原始数据
    keep_original: bool = True
    # 字段映射（自定义）
    field_mappings: dict[str, str] = field(default_factory=dict)


@dataclass
class NormalizationResult:
    """标准化结果"""
    # 标准化后的数据
    normalized_data: dict[str, Any]
    # 原始数据
    original_data: Optional[dict[str, Any]] = None
    # 是否成功
    is_valid: bool = True
    # 错误原因
    error: Optional[str] = None
    # 数据格式
    source_format: Optional[str] = None
    # 检测到的语言
    detected_language: Optional[str] = None
    # 质量分数（0-1）
    quality_score: float = 1.0
    # 处理时间（毫秒）
    processing_time_ms: float = 0.0


@dataclass
class StandardData:
    """标准数据格式"""
    # 必填字段
    id: str
    content: str
    source: str
    collected_at: str
    
    # 可选字段
    title: Optional[str] = None
    author: Optional[str] = None
    author_id: Optional[str] = None
    url: Optional[str] = None
    published_at: Optional[str] = None
    language: Optional[str] = None
    platform: Optional[str] = None
    
    # 元数据
    metadata: dict[str, Any] = field(default_factory=dict)
    
    # 质量相关
    quality_score: float = 1.0
    content_length: int = 0
    
    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "content": self.content,
            "source": self.source,
            "collected_at": self.collected_at,
            "title": self.title,
            "author": self.author,
            "author_id": self.author_id,
            "url": self.url,
            "published_at": self.published_at,
            "language": self.language,
            "platform": self.platform,
            "metadata": self.metadata,
            "quality_score": self.quality_score,
            "content_length": self.content_length,
        }


class DataNormalizer:
    """数据标准化器"""
    
    # 平台特定字段映射
    PLATFORM_MAPPINGS = {
        DataFormat.TWITTER: {
            "tweet_id": "id",
            "text": "content",
            "user_name": "author",
            "user_id": "author_id",
            "created_at": "published_at",
            "tweet_url": "url",
        },
        DataFormat.REDDIT: {
            "post_id": "id",
            "selftext": "content",
            "title": "title",
            "author": "author",
            "created_utc": "published_at",
            "url": "url",
            "subreddit": "platform",
        },
        DataFormat.NEWS: {
            "article_id": "id",
            "body": "content",
            "headline": "title",
            "author": "author",
            "publish_date": "published_at",
            "article_url": "url",
            "source": "platform",
        },
        DataFormat.WEIBO: {
            "mid": "id",
            "text": "content",
            "user_screen_name": "author",
            "user_id": "author_id",
            "created_at": "published_at",
            "scheme": "url",
        },
        DataFormat.YOUTUBE: {
            "video_id": "id",
            "description": "content",
            "title": "title",
            "channel_title": "author",
            "channel_id": "author_id",
            "published_at": "published_at",
            "video_url": "url",
        },
        DataFormat.STANDARD: {
            "id": "id",
            "content": "content",
            "source": "source",
            "title": "title",
            "author": "author",
            "url": "url",
            "published_at": "published_at",
            "collected_at": "collected_at",
        },
    }
    
    # 语言检测关键词（简单版本）
    LANGUAGE_PATTERNS = {
        "zh": r'[\u4e00-\u9fff]',
        "ja": r'[\u3040-\u309f\u30a0-\u30ff]',
        "ko": r'[\uac00-\ud7af]',
        "en": r'[a-zA-Z]',
    }
    
    def __init__(self, config: Optional[NormalizerConfig] = None):
        self.config = config or NormalizerConfig()
    
    def normalize(
        self, 
        data: dict[str, Any], 
        source_format: Optional[DataFormat] = None
    ) -> NormalizationResult:
        """
        标准化数据
        
        Args:
            data: 原始数据
            source_format: 数据来源格式（可选，自动检测）
            
        Returns:
            NormalizationResult: 标准化结果
        """
        start_time = datetime.now()
        
        if not data or not isinstance(data, dict):
            return NormalizationResult(
                normalized_data={},
                original_data=data,
                is_valid=False,
                error="invalid_input_data",
                processing_time_ms=self._get_elapsed_ms(start_time)
            )
        
        original_data = data.copy() if self.config.keep_original else None
        
        try:
            # 1. 检测数据格式
            if source_format is None:
                source_format = self._detect_format(data)
            
            # 2. 字段映射
            normalized = self._apply_field_mapping(data, source_format)
            
            # 3. 验证必填字段
            is_valid, error = self._validate_required_fields(normalized)
            if not is_valid:
                return NormalizationResult(
                    normalized_data=normalized,
                    original_data=original_data,
                    is_valid=False,
                    error=error,
                    source_format=source_format.value,
                    processing_time_ms=self._get_elapsed_ms(start_time)
                )
            
            # 4. 标准化时间字段
            normalized = self._normalize_datetime_fields(normalized)
            
            # 5. 检测语言
            detected_language = None
            if self.config.detect_language:
                detected_language = self._detect_language(normalized.get("content", ""))
                normalized["language"] = detected_language
            
            # 6. 计算质量分数
            quality_score = 1.0
            if self.config.compute_quality_score:
                quality_score = self._compute_quality_score(normalized)
                normalized["quality_score"] = quality_score
            
            # 7. 添加内容长度
            content = normalized.get("content", "")
            normalized["content_length"] = len(content)
            
            # 8. 确保来源字段
            if "source" not in normalized:
                normalized["source"] = source_format.value
            
            # 9. 确保收集时间
            if "collected_at" not in normalized:
                normalized["collected_at"] = datetime.utcnow().strftime(self.config.date_format)
            
            return NormalizationResult(
                normalized_data=normalized,
                original_data=original_data,
                is_valid=True,
                source_format=source_format.value,
                detected_language=detected_language,
                quality_score=quality_score,
                processing_time_ms=self._get_elapsed_ms(start_time)
            )
            
        except Exception as e:
            return NormalizationResult(
                normalized_data={},
                original_data=original_data,
                is_valid=False,
                error=f"normalization_error: {str(e)}",
                processing_time_ms=self._get_elapsed_ms(start_time)
            )
    
    def _detect_format(self, data: dict[str, Any]) -> DataFormat:
        """检测数据格式"""
        # Twitter 特征字段
        if any(k in data for k in ["tweet_id", "text", "user_name", "retweeted_status"]):
            return DataFormat.TWITTER
        
        # Reddit 特征字段
        if any(k in data for k in ["post_id", "selftext", "subreddit", "permalink"]):
            return DataFormat.REDDIT
        
        # 微博特征字段
        if any(k in data for k in ["mid", "user_screen_name", "reposts_count", "comments_count"]):
            return DataFormat.WEIBO
        
        # YouTube 特征字段
        if any(k in data for k in ["video_id", "channel_id", "video_url", "view_count"]):
            return DataFormat.YOUTUBE
        
        # 新闻特征字段
        if any(k in data for k in ["article_id", "headline", "article_url", "publish_date"]):
            return DataFormat.NEWS
        
        # 标准格式（有 id 和 content 字段）
        if "id" in data and "content" in data:
            return DataFormat.STANDARD
        
        return DataFormat.CUSTOM
    
    def _apply_field_mapping(
        self, 
        data: dict[str, Any], 
        source_format: DataFormat
    ) -> dict[str, Any]:
        """应用字段映射"""
        result = {}
        
        # 获取平台映射
        mappings = self.PLATFORM_MAPPINGS.get(source_format, {})
        
        # 应用自定义映射
        mappings.update(self.config.field_mappings)
        
        # 执行映射
        for old_key, new_key in mappings.items():
            if old_key in data:
                value = data[old_key]
                if value is not None:
                    result[new_key] = value
        
        # 复制未映射的字段到 metadata
        mapped_keys = set(mappings.keys())
        result.setdefault("metadata", {})
        
        for key, value in data.items():
            if key not in mapped_keys and key not in result:
                if value is not None:
                    result["metadata"][key] = value
        
        return result
    
    def _validate_required_fields(self, data: dict[str, Any]) -> tuple[bool, Optional[str]]:
        """验证必填字段"""
        # 至少需要 id 和 content
        if not data.get("id"):
            return False, "missing_required_field: id"
        
        content = data.get("content", "")
        if not content or len(content) < self.config.min_content_length:
            return False, f"content_too_short: {len(content)} < {self.config.min_content_length}"
        
        return True, None
    
    def _normalize_datetime_fields(self, data: dict[str, Any]) -> dict[str, Any]:
        """标准化时间字段"""
        datetime_fields = ["published_at", "collected_at", "created_at", "updated_at"]
        
        for field in datetime_fields:
            if field in data and data[field] is not None:
                normalized = self._normalize_datetime(data[field])
                if normalized:
                    data[field] = normalized
        
        return data
    
    def _normalize_datetime(self, value: Any) -> Optional[str]:
        """标准化时间值"""
        if value is None:
            return None
        
        # 已经是标准格式
        if isinstance(value, str):
            # ISO 格式
            if "T" in value and ("Z" in value or "+" in value):
                return value
            
            # 尝试解析各种格式
            formats = [
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%dT%H:%M:%S",
                "%a %b %d %H:%M:%S %z %Y",  # Twitter 格式
                "%a, %d %b %Y %H:%M:%S %Z",  # RSS 格式
                "%Y-%m-%d",
            ]
            
            for fmt in formats:
                try:
                    dt = datetime.strptime(value, fmt)
                    return dt.strftime(self.config.date_format)
                except ValueError:
                    continue
        
        # Unix 时间戳
        if isinstance(value, (int, float)):
            try:
                dt = datetime.utcfromtimestamp(value)
                return dt.strftime(self.config.date_format)
            except (ValueError, OSError):
                pass
        
        # datetime 对象
        if isinstance(value, datetime):
            return value.strftime(self.config.date_format)
        
        return None
    
    def _detect_language(self, text: str) -> Optional[str]:
        """检测文本语言（简单版本）"""
        if not text:
            return None
        
        # 统计各语言字符比例
        counts = {}
        for lang, pattern in self.LANGUAGE_PATTERNS.items():
            matches = len(re.findall(pattern, text))
            counts[lang] = matches
        
        total = sum(counts.values())
        if total == 0:
            return None
        
        # 返回占比最高的语言
        max_lang = max(counts, key=counts.get)
        if counts[max_lang] / total > 0.3:  # 至少 30%
            return max_lang
        
        return None
    
    def _compute_quality_score(self, data: dict[str, Any]) -> float:
        """计算数据质量分数"""
        score = 1.0
        
        # 1. 内容长度评分
        content = data.get("content", "")
        content_length = len(content)
        
        if content_length < 50:
            score *= 0.7
        elif content_length < 100:
            score *= 0.85
        
        # 2. 字段完整性评分
        important_fields = ["title", "author", "url", "published_at"]
        present_fields = sum(1 for f in important_fields if data.get(f))
        completeness = present_fields / len(important_fields)
        score *= (0.5 + 0.5 * completeness)
        
        # 3. 内容质量评分
        # 检查是否包含有意义的内容
        if content:
            # 检查重复字符
            if re.search(r'(.)\1{5,}', content):
                score *= 0.8
            
            # 检查是否主要是链接
            url_count = len(re.findall(r'https?://\S+', content))
            if url_count > 3:
                score *= 0.9
        
        # 4. 确保分数在 0-1 范围内
        return max(0.0, min(1.0, score))
    
    def _get_elapsed_ms(self, start_time: datetime) -> float:
        """计算耗时（毫秒）"""
        elapsed = datetime.now() - start_time
        return elapsed.total_seconds() * 1000
    
    def normalize_batch(
        self, 
        data_list: list[dict[str, Any]], 
        source_format: Optional[DataFormat] = None
    ) -> list[NormalizationResult]:
        """
        批量标准化数据
        
        Args:
            data_list: 数据列表
            source_format: 数据来源格式（可选）
            
        Returns:
            标准化结果列表
        """
        return [
            self.normalize(data, source_format) 
            for data in data_list
        ]
    
    def get_stats(self, results: list[NormalizationResult]) -> dict:
        """获取标准化统计"""
        total = len(results)
        valid = sum(1 for r in results if r.is_valid)
        invalid = total - valid
        
        formats = {}
        languages = {}
        quality_scores = []
        
        for r in results:
            if r.is_valid:
                if r.source_format:
                    formats[r.source_format] = formats.get(r.source_format, 0) + 1
                if r.detected_language:
                    languages[r.detected_language] = languages.get(r.detected_language, 0) + 1
                quality_scores.append(r.quality_score)
        
        return {
            "total": total,
            "valid": valid,
            "invalid": invalid,
            "valid_rate": valid / total if total > 0 else 0,
            "source_formats": formats,
            "detected_languages": languages,
            "avg_quality_score": sum(quality_scores) / len(quality_scores) if quality_scores else 0,
            "avg_processing_time_ms": sum(r.processing_time_ms for r in results) / total if total > 0 else 0
        }