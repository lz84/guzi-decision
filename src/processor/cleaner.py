"""
数据清洗模块

功能:
- 移除无效字符
- 移除 HTML 标签
- 移除多余空白
- 移除特殊字符
- URL 和邮箱处理
- 表情符号处理
"""

import re
import html
import unicodedata
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime


@dataclass
class CleanerConfig:
    """清洗配置"""
    # 是否移除 HTML 标签
    remove_html: bool = True
    # 是否移除 URL
    remove_urls: bool = False
    # 是否移除邮箱
    remove_emails: bool = False
    # 是否移除表情符号
    remove_emojis: bool = False
    # 是否移除特殊字符（保留中日韩文字）
    remove_special_chars: bool = True
    # 是否规范化空白字符
    normalize_whitespace: bool = True
    # 是否转换为小写（对英文）
    lowercase: bool = False
    # 最小文本长度
    min_length: int = 10
    # 最大文本长度
    max_length: int = 10000
    # 保留的标点符号
    keep_punctuation: str = ".,!?;:'\"()[]{}-—"
    # 语言（用于特殊处理）
    language: str = "zh"  # zh, en, ja, ko


@dataclass
class CleaningResult:
    """清洗结果"""
    original: str
    cleaned: str
    is_valid: bool
    invalid_reason: Optional[str] = None
    removed_urls: list[str] = field(default_factory=list)
    removed_emails: list[str] = field(default_factory=list)
    removed_emojis: list[str] = field(default_factory=list)
    processing_time_ms: float = 0.0


class DataCleaner:
    """数据清洗器"""
    
    # URL 正则表达式
    URL_PATTERN = re.compile(
        r'https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+[/\w .-]*/?(?:\?[-\w%&=]*)?(?:#[-\w]*)?'
    )
    
    # 邮箱正则表达式
    EMAIL_PATTERN = re.compile(
        r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    )
    
    # HTML 标签正则表达式
    HTML_TAG_PATTERN = re.compile(r'<[^>]+>')
    
    # HTML 实体模式
    HTML_ENTITY_PATTERN = re.compile(r'&(?:#(?:x[\da-fA-F]+|\d+)|[a-zA-Z]+);?')
    
    # 表情符号范围（常见的表情符号 Unicode 范围）
    EMOJI_RANGES = [
        (0x1F600, 0x1F64F),  # Emoticons
        (0x1F300, 0x1F5FF),  # Misc Symbols and Pictographs
        (0x1F680, 0x1F6FF),  # Transport and Map
        (0x1F900, 0x1F9FF),  # Supplemental Symbols and Pictographs
        (0x2600, 0x26FF),    # Misc symbols
        (0x2700, 0x27BF),    # Dingbats
        (0xFE00, 0xFE0F),    # Variation Selectors
        (0x1F1E0, 0x1F1FF),  # Flags
        (0x1FA00, 0x1FA6F),  # Chess Symbols
        (0x1FA70, 0x1FAFF),  # Symbols and Pictographs Extended-A
    ]
    
    # 控制字符（需要移除）
    CONTROL_CHARS = set(range(0x00, 0x20)) - {0x09, 0x0A, 0x0D}  # 保留 tab, LF, CR
    
    def __init__(self, config: Optional[CleanerConfig] = None):
        self.config = config or CleanerConfig()
    
    def clean(self, text: str) -> CleaningResult:
        """
        清洗文本
        
        Args:
            text: 原始文本
            
        Returns:
            CleaningResult: 清洗结果
        """
        start_time = datetime.now()
        
        if not text or not isinstance(text, str):
            return CleaningResult(
                original=text or "",
                cleaned="",
                is_valid=False,
                invalid_reason="empty_or_invalid_input",
                processing_time_ms=0.0
            )
        
        original = text
        cleaned = text
        removed_urls = []
        removed_emails = []
        removed_emojis = []
        
        try:
            # 1. 解码 HTML 实体
            cleaned = html.unescape(cleaned)
            
            # 2. 移除 HTML 标签
            if self.config.remove_html:
                cleaned = self.HTML_TAG_PATTERN.sub(' ', cleaned)
            
            # 3. 提取并移除 URL
            if self.config.remove_urls:
                removed_urls = self.URL_PATTERN.findall(cleaned)
                cleaned = self.URL_PATTERN.sub(' ', cleaned)
            else:
                # 保留 URL 但规范化
                cleaned = self.URL_PATTERN.sub(lambda m: m.group(0), cleaned)
            
            # 4. 提取并移除邮箱
            if self.config.remove_emails:
                removed_emails = self.EMAIL_PATTERN.findall(cleaned)
                cleaned = self.EMAIL_PATTERN.sub(' ', cleaned)
            
            # 5. 移除表情符号
            if self.config.remove_emojis:
                cleaned, removed_emojis = self._remove_emojis(cleaned)
            
            # 6. Unicode 规范化
            cleaned = unicodedata.normalize('NFKC', cleaned)
            
            # 7. 移除控制字符
            cleaned = self._remove_control_chars(cleaned)
            
            # 8. 移除特殊字符
            if self.config.remove_special_chars:
                cleaned = self._remove_special_chars(cleaned)
            
            # 9. 规范化空白字符
            if self.config.normalize_whitespace:
                cleaned = self._normalize_whitespace(cleaned)
            
            # 10. 转换为小写
            if self.config.lowercase:
                cleaned = cleaned.lower()
            
            # 11. 验证文本长度
            is_valid, invalid_reason = self._validate_text(cleaned)
            
        except Exception as e:
            return CleaningResult(
                original=original,
                cleaned="",
                is_valid=False,
                invalid_reason=f"cleaning_error: {str(e)}",
                processing_time_ms=self._get_elapsed_ms(start_time)
            )
        
        return CleaningResult(
            original=original,
            cleaned=cleaned,
            is_valid=is_valid,
            invalid_reason=invalid_reason,
            removed_urls=removed_urls,
            removed_emails=removed_emails,
            removed_emojis=removed_emojis,
            processing_time_ms=self._get_elapsed_ms(start_time)
        )
    
    def _remove_emojis(self, text: str) -> tuple[str, list[str]]:
        """移除表情符号"""
        removed = []
        result = []
        
        for char in text:
            code = ord(char)
            is_emoji = any(
                start <= code <= end 
                for start, end in self.EMOJI_RANGES
            )
            
            if is_emoji:
                removed.append(char)
            else:
                result.append(char)
        
        return ''.join(result), removed
    
    def _remove_control_chars(self, text: str) -> str:
        """移除控制字符"""
        return ''.join(
            char for char in text 
            if ord(char) not in self.CONTROL_CHARS
        )
    
    def _remove_special_chars(self, text: str) -> str:
        """
        移除特殊字符，保留中日韩文字、字母、数字和指定标点
        """
        result = []
        
        for char in text:
            code = ord(char)
            
            # 保留中日韩文字范围
            is_cjk = (
                0x4E00 <= code <= 0x9FFF or    # CJK Unified Ideographs
                0x3400 <= code <= 0x4DBF or    # CJK Extension A
                0x20000 <= code <= 0x2A6DF or  # CJK Extension B
                0xF900 <= code <= 0xFAFF or    # CJK Compatibility Ideographs
                0x3040 <= code <= 0x309F or    # Hiragana
                0x30A0 <= code <= 0x30FF or    # Katakana
                0xAC00 <= code <= 0xD7AF       # Hangul
            )
            
            # 保留字母和数字
            is_alnum = char.isalnum()
            
            # 保留空白字符
            is_whitespace = char.isspace()
            
            # 保留指定标点和中英文标点
            is_keep_punct = char in self.config.keep_punctuation
            is_chinese_punct = char in '，。！？；：""''（）【】《》—…·'
            is_english_punct = char in ',.!?;:\'"()[]{}-'
            
            if is_cjk or is_alnum or is_whitespace or is_keep_punct or is_chinese_punct or is_english_punct:
                result.append(char)
            else:
                result.append(' ')
        
        return ''.join(result)
    
    def _normalize_whitespace(self, text: str) -> str:
        """规范化空白字符"""
        # 将所有空白字符替换为空格
        text = re.sub(r'\s+', ' ', text)
        # 移除首尾空白
        text = text.strip()
        return text
    
    def _validate_text(self, text: str) -> tuple[bool, Optional[str]]:
        """验证文本"""
        if not text:
            return False, "empty_after_cleaning"
        
        if len(text) < self.config.min_length:
            return False, f"too_short: {len(text)} < {self.config.min_length}"
        
        if len(text) > self.config.max_length:
            return False, f"too_long: {len(text)} > {self.config.max_length}"
        
        # 检查是否有实际内容（不只是空白或标点）
        content_chars = sum(1 for c in text if c.isalnum() or ord(c) > 0x4E00)
        if content_chars < 3:
            return False, "insufficient_content"
        
        return True, None
    
    def _get_elapsed_ms(self, start_time: datetime) -> float:
        """计算耗时（毫秒）"""
        elapsed = datetime.now() - start_time
        return elapsed.total_seconds() * 1000
    
    def clean_batch(self, texts: list[str]) -> list[CleaningResult]:
        """
        批量清洗文本
        
        Args:
            texts: 文本列表
            
        Returns:
            清洗结果列表
        """
        return [self.clean(text) for text in texts]
    
    def get_stats(self, results: list[CleaningResult]) -> dict:
        """获取清洗统计"""
        total = len(results)
        valid = sum(1 for r in results if r.is_valid)
        invalid = total - valid
        
        reasons = {}
        for r in results:
            if not r.is_valid and r.invalid_reason:
                reason = r.invalid_reason.split(':')[0]
                reasons[reason] = reasons.get(reason, 0) + 1
        
        return {
            "total": total,
            "valid": valid,
            "invalid": invalid,
            "valid_rate": valid / total if total > 0 else 0,
            "invalid_reasons": reasons,
            "avg_processing_time_ms": sum(r.processing_time_ms for r in results) / total if total > 0 else 0
        }