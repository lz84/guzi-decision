"""
文本去重模块

功能:
- 基于向量相似度的去重
- 基于 SimHash 的快速去重
- 精确匹配去重
- 支持增量去重
"""

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from collections import defaultdict


@dataclass
class DeduplicatorConfig:
    """去重配置"""
    # 相似度阈值（0-1），超过此阈值视为重复
    similarity_threshold: float = 0.95
    # 去重方法: "exact", "simhash", "minhash", "all"
    method: str = "simhash"
    # SimHash 汉明距离阈值
    simhash_distance: int = 3
    # MinHash 排列数量
    minhash_permutations: int = 128
    # 是否保留第一条（True）或最后一条（False）
    keep_first: bool = True
    # 最小文本长度（低于此长度不做去重）
    min_text_length: int = 20
    # 是否启用内容哈希缓存
    enable_cache: bool = True
    # 缓存过期时间（秒）
    cache_ttl: int = 86400  # 24小时


@dataclass
class DeduplicationResult:
    """去重结果"""
    text: str
    text_id: str
    is_duplicate: bool
    duplicate_of: Optional[str] = None
    similarity_score: float = 0.0
    match_method: Optional[str] = None
    processing_time_ms: float = 0.0


class SimHash:
    """SimHash 实现 - 用于快速文本相似度检测"""
    
    def __init__(self, text: str, hash_bits: int = 64):
        self.hash_bits = hash_bits
        self.hash_value = self._compute(text)
    
    def _compute(self, text: str) -> int:
        """计算 SimHash 值"""
        # 分词
        words = self._tokenize(text)
        
        # 初始化向量
        v = [0] * self.hash_bits
        
        for word in words:
            # 计算词的哈希值
            word_hash = int(hashlib.md5(word.encode()).hexdigest(), 16)
            
            # 更新向量
            for i in range(self.hash_bits):
                bit = (word_hash >> i) & 1
                if bit:
                    v[i] += 1
                else:
                    v[i] -= 1
        
        # 生成最终哈希值
        result = 0
        for i in range(self.hash_bits):
            if v[i] > 0:
                result |= (1 << i)
        
        return result
    
    def _tokenize(self, text: str) -> list[str]:
        """分词 - 简单的字符 n-gram 分词"""
        # 移除空白
        text = re.sub(r'\s+', '', text)
        
        # 使用 2-gram
        n = 2
        tokens = []
        for i in range(len(text) - n + 1):
            tokens.append(text[i:i+n])
        
        return tokens if tokens else [text]
    
    def distance(self, other: 'SimHash') -> int:
        """计算汉明距离"""
        x = self.hash_value ^ other.hash_value
        distance = 0
        while x:
            distance += 1
            x &= x - 1
        return distance
    
    def similarity(self, other: 'SimHash') -> float:
        """计算相似度（0-1）"""
        dist = self.distance(other)
        return 1.0 - (dist / self.hash_bits)


class TextDeduplicator:
    """文本去重器"""
    
    def __init__(self, config: Optional[DeduplicatorConfig] = None):
        self.config = config or DeduplicatorConfig()
        
        # 存储已见过的文本
        self._seen_texts: dict[str, str] = {}  # text_id -> original_text
        self._text_hashes: dict[str, str] = {}  # hash -> text_id
        self._simhash_index: dict[int, str] = {}  # simhash -> text_id
        
        # 缓存
        self._cache: dict[str, tuple[bool, Optional[str], float]] = {}
    
    def check(self, text: str, text_id: Optional[str] = None) -> DeduplicationResult:
        """
        检查文本是否重复
        
        Args:
            text: 待检查的文本
            text_id: 文本ID（可选）
            
        Returns:
            DeduplicationResult: 去重结果
        """
        start_time = datetime.now()
        
        if text_id is None:
            text_id = self._generate_id(text)
        
        # 短文本不做去重
        if len(text) < self.config.min_text_length:
            return DeduplicationResult(
                text=text,
                text_id=text_id,
                is_duplicate=False,
                processing_time_ms=self._get_elapsed_ms(start_time)
            )
        
        # 检查缓存
        if self.config.enable_cache:
            cache_key = self._get_cache_key(text)
            if cache_key in self._cache:
                cached_is_dup, cached_dup_of, cached_score = self._cache[cache_key]
                # 如果之前检查过且不是重复，需要检查是否已被添加到索引
                if not cached_is_dup:
                    # 检查是否已添加到索引
                    text_hash = hashlib.sha256(text.encode()).hexdigest()
                    if text_hash in self._text_hashes:
                        existing_id = self._text_hashes[text_hash]
                        if existing_id != text_id:
                            return DeduplicationResult(
                                text=text,
                                text_id=text_id,
                                is_duplicate=True,
                                duplicate_of=existing_id,
                                similarity_score=1.0,
                                match_method="exact",
                                processing_time_ms=self._get_elapsed_ms(start_time)
                            )
                return DeduplicationResult(
                    text=text,
                    text_id=text_id,
                    is_duplicate=cached_is_dup,
                    duplicate_of=cached_dup_of,
                    similarity_score=cached_score,
                    match_method="cache",
                    processing_time_ms=self._get_elapsed_ms(start_time)
                )
        
        # 执行去重检查
        result = self._check_duplicate(text, text_id)
        
        # 更新缓存
        if self.config.enable_cache:
            self._cache[self._get_cache_key(text)] = (
                result.is_duplicate,
                result.duplicate_of,
                result.similarity_score
            )
        
        # 更新处理时间
        result.processing_time_ms = self._get_elapsed_ms(start_time)
        
        return result
    
    def _check_duplicate(self, text: str, text_id: str) -> DeduplicationResult:
        """执行去重检查"""
        method = self.config.method.lower()
        
        # 1. 精确匹配检查
        if method in ("exact", "all"):
            exact_result = self._check_exact(text, text_id)
            if exact_result.is_duplicate:
                return exact_result
        
        # 2. SimHash 检查
        if method in ("simhash", "all"):
            simhash_result = self._check_simhash(text, text_id)
            if simhash_result.is_duplicate:
                return simhash_result
        
        # 3. MinHash 检查（暂时使用简单的 n-gram 相似度）
        if method in ("minhash", "all"):
            minhash_result = self._check_ngram_similarity(text, text_id)
            if minhash_result.is_duplicate:
                return minhash_result
        
        # 不重复，添加到索引（即使短文本也要添加，以支持精确匹配去重）
        self._add_to_index(text, text_id)
        
        return DeduplicationResult(
            text=text,
            text_id=text_id,
            is_duplicate=False
        )
    
    def _check_exact(self, text: str, text_id: str) -> DeduplicationResult:
        """精确匹配检查"""
        text_hash = hashlib.sha256(text.encode()).hexdigest()
        
        if text_hash in self._text_hashes:
            duplicate_of = self._text_hashes[text_hash]
            return DeduplicationResult(
                text=text,
                text_id=text_id,
                is_duplicate=True,
                duplicate_of=duplicate_of,
                similarity_score=1.0,
                match_method="exact"
            )
        
        return DeduplicationResult(
            text=text,
            text_id=text_id,
            is_duplicate=False
        )
    
    def _check_simhash(self, text: str, text_id: str) -> DeduplicationResult:
        """SimHash 相似度检查"""
        simhash = SimHash(text)
        
        best_match_id = None
        best_similarity = 0.0
        
        for existing_hash, existing_id in self._simhash_index.items():
            existing_simhash = SimHash.__new__(SimHash)
            existing_simhash.hash_bits = simhash.hash_bits
            existing_simhash.hash_value = existing_hash
            
            distance = simhash.distance(existing_simhash)
            
            if distance <= self.config.simhash_distance:
                similarity = simhash.similarity(existing_simhash)
                if similarity > best_similarity:
                    best_similarity = similarity
                    best_match_id = existing_id
        
        if best_match_id and best_similarity >= self.config.similarity_threshold:
            return DeduplicationResult(
                text=text,
                text_id=text_id,
                is_duplicate=True,
                duplicate_of=best_match_id,
                similarity_score=best_similarity,
                match_method="simhash"
            )
        
        return DeduplicationResult(
            text=text,
            text_id=text_id,
            is_duplicate=False
        )
    
    def _check_ngram_similarity(self, text: str, text_id: str) -> DeduplicationResult:
        """基于 n-gram 的相似度检查"""
        ngrams = self._get_ngrams(text, n=3)
        
        if not ngrams:
            return DeduplicationResult(
                text=text,
                text_id=text_id,
                is_duplicate=False
            )
        
        best_match_id = None
        best_similarity = 0.0
        
        for existing_id, existing_text in self._seen_texts.items():
            existing_ngrams = self._get_ngrams(existing_text, n=3)
            
            if not existing_ngrams:
                continue
            
            # 计算 Jaccard 相似度
            intersection = len(ngrams & existing_ngrams)
            union = len(ngrams | existing_ngrams)
            
            if union > 0:
                similarity = intersection / union
                
                if similarity > best_similarity:
                    best_similarity = similarity
                    best_match_id = existing_id
        
        if best_match_id and best_similarity >= self.config.similarity_threshold:
            return DeduplicationResult(
                text=text,
                text_id=text_id,
                is_duplicate=True,
                duplicate_of=best_match_id,
                similarity_score=best_similarity,
                match_method="ngram"
            )
        
        return DeduplicationResult(
            text=text,
            text_id=text_id,
            is_duplicate=False
        )
    
    def _add_to_index(self, text: str, text_id: str):
        """添加到索引"""
        self._seen_texts[text_id] = text
        
        # 添加精确哈希
        text_hash = hashlib.sha256(text.encode()).hexdigest()
        self._text_hashes[text_hash] = text_id
        
        # 添加 SimHash
        simhash = SimHash(text)
        self._simhash_index[simhash.hash_value] = text_id
    
    def _get_ngrams(self, text: str, n: int = 3) -> set:
        """获取 n-gram 集合"""
        text = re.sub(r'\s+', '', text)
        if len(text) < n:
            return {text}
        
        return {text[i:i+n] for i in range(len(text) - n + 1)}
    
    def _generate_id(self, text: str) -> str:
        """生成文本ID"""
        return hashlib.md5(text.encode()).hexdigest()[:16]
    
    def _get_cache_key(self, text: str) -> str:
        """获取缓存键"""
        return hashlib.sha256(text.encode()).hexdigest()
    
    def _get_elapsed_ms(self, start_time: datetime) -> float:
        """计算耗时（毫秒）"""
        elapsed = datetime.now() - start_time
        return elapsed.total_seconds() * 1000
    
    def check_batch(
        self, 
        texts: list[str], 
        text_ids: Optional[list[str]] = None
    ) -> list[DeduplicationResult]:
        """
        批量检查文本
        
        Args:
            texts: 文本列表
            text_ids: 文本ID列表（可选）
            
        Returns:
            去重结果列表
        """
        if text_ids is None:
            text_ids = [None] * len(texts)
        
        return [
            self.check(text, text_id) 
            for text, text_id in zip(texts, text_ids)
        ]
    
    def get_stats(self, results: list[DeduplicationResult]) -> dict:
        """获取去重统计"""
        total = len(results)
        duplicates = sum(1 for r in results if r.is_duplicate)
        unique = total - duplicates
        
        methods = defaultdict(int)
        for r in results:
            if r.is_duplicate and r.match_method:
                methods[r.match_method] += 1
        
        return {
            "total": total,
            "unique": unique,
            "duplicates": duplicates,
            "duplicate_rate": duplicates / total if total > 0 else 0,
            "match_methods": dict(methods),
            "avg_processing_time_ms": sum(r.processing_time_ms for r in results) / total if total > 0 else 0
        }
    
    def reset(self):
        """重置去重器状态"""
        self._seen_texts.clear()
        self._text_hashes.clear()
        self._simhash_index.clear()
        self._cache.clear()
    
    def get_index_size(self) -> dict:
        """获取索引大小"""
        return {
            "texts": len(self._seen_texts),
            "hashes": len(self._text_hashes),
            "simhash_index": len(self._simhash_index),
            "cache": len(self._cache)
        }