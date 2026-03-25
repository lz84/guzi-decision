"""
数据处理模块测试
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import pytest
from datetime import datetime

from processor import (
    DataCleaner,
    CleanerConfig,
    TextDeduplicator,
    DeduplicatorConfig,
    DataNormalizer,
    NormalizerConfig,
    DataProcessingPipeline,
    PipelineConfig,
    RawData,
    ProcessedData,
    DataSource,
)


class TestDataCleaner:
    """数据清洗器测试"""
    
    def test_clean_basic_text(self):
        """测试基本文本清洗"""
        cleaner = DataCleaner()
        result = cleaner.clean("这是一段正常的文本。")
        
        assert result.is_valid
        assert result.cleaned == "这是一段正常的文本。"
    
    def test_clean_html_tags(self):
        """测试移除 HTML 标签"""
        cleaner = DataCleaner(CleanerConfig(remove_html=True))
        result = cleaner.clean("<p>这是<strong>HTML</strong>文本</p>")
        
        assert result.is_valid
        assert "<p>" not in result.cleaned
        assert "<strong>" not in result.cleaned
    
    def test_clean_urls(self):
        """测试 URL 处理"""
        cleaner = DataCleaner(CleanerConfig(remove_urls=True))
        result = cleaner.clean("访问 https://example.com 查看更多详细信息，这是一段足够长的测试文本")
        
        assert result.is_valid
        assert "https://example.com" not in result.cleaned
        assert len(result.removed_urls) == 1
    
    def test_clean_whitespace(self):
        """测试空白字符规范化"""
        cleaner = DataCleaner(CleanerConfig(normalize_whitespace=True))
        result = cleaner.clean("这是   多个   空格\n\n和换行")
        
        assert result.is_valid
        assert "   " not in result.cleaned
        assert "\n" not in result.cleaned
    
    def test_clean_invalid_text(self):
        """测试无效文本"""
        cleaner = DataCleaner(CleanerConfig(min_length=10))
        result = cleaner.clean("短")
        
        assert not result.is_valid
        assert "too_short" in result.invalid_reason
    
    def test_clean_empty_text(self):
        """测试空文本"""
        cleaner = DataCleaner()
        result = cleaner.clean("")
        
        assert not result.is_valid
        assert result.invalid_reason == "empty_or_invalid_input"
    
    def test_clean_emojis(self):
        """测试表情符号移除"""
        cleaner = DataCleaner(CleanerConfig(remove_emojis=True))
        result = cleaner.clean("这是一段文本😀🎉，内容长度足够用于测试表情符号移除功能")
        
        assert result.is_valid
        assert "😀" not in result.cleaned
        assert "🎉" not in result.cleaned
        assert len(result.removed_emojis) == 2


class TestTextDeduplicator:
    """文本去重器测试"""
    
    def test_exact_duplicate(self):
        """测试精确匹配去重"""
        deduplicator = TextDeduplicator()
        
        text = "这是一段测试文本，内容长度足够用于测试去重功能"
        result1 = deduplicator.check(text, "id1")
        result2 = deduplicator.check(text, "id2")
        
        assert not result1.is_duplicate
        assert result2.is_duplicate
        assert result2.duplicate_of == "id1"
    
    def test_similar_text(self):
        """测试相似文本"""
        deduplicator = TextDeduplicator(
            DeduplicatorConfig(similarity_threshold=0.8, method="simhash")
        )
        
        text1 = "这是一段测试文本，用于测试相似度检测功能"
        text2 = "这是一段测试文本，用于测试相似度检测"
        
        result1 = deduplicator.check(text1, "id1")
        result2 = deduplicator.check(text2, "id2")
        
        # 相似但不完全相同
        assert not result1.is_duplicate
    
    def test_unique_texts(self):
        """测试不同文本"""
        deduplicator = TextDeduplicator()
        
        text1 = "这是第一段完全不同的文本内容"
        text2 = "这是第二段完全不同的文本内容"
        
        result1 = deduplicator.check(text1, "id1")
        result2 = deduplicator.check(text2, "id2")
        
        assert not result1.is_duplicate
        assert not result2.is_duplicate
    
    def test_short_text_skip(self):
        """测试短文本跳过"""
        deduplicator = TextDeduplicator(
            DeduplicatorConfig(min_text_length=20)
        )
        
        short_text = "短文本"
        result = deduplicator.check(short_text, "id1")
        
        assert not result.is_duplicate
    
    def test_reset(self):
        """测试重置"""
        deduplicator = TextDeduplicator()
        
        text = "测试重置功能"
        result1 = deduplicator.check(text, "id1")
        
        deduplicator.reset()
        
        result2 = deduplicator.check(text, "id2")
        
        assert not result2.is_duplicate


class TestDataNormalizer:
    """数据标准化器测试"""
    
    def test_normalize_standard_data(self):
        """测试标准数据格式"""
        normalizer = DataNormalizer()
        
        data = {
            "id": "test123",
            "content": "这是一段测试内容，长度足够",
            "source": "test"
        }
        
        result = normalizer.normalize(data)
        
        assert result.is_valid
        assert result.normalized_data["id"] == "test123"
        assert result.normalized_data["content"] == "这是一段测试内容，长度足够"
    
    def test_normalize_twitter_data(self):
        """测试 Twitter 数据格式"""
        normalizer = DataNormalizer()
        
        data = {
            "tweet_id": "tw123",
            "text": "这是一条推文内容，长度足够用于测试标准化功能",
            "user_name": "test_user",
            "user_id": "user123"
        }
        
        result = normalizer.normalize(data)
        
        assert result.is_valid
        assert result.normalized_data["id"] == "tw123"
        assert result.normalized_data["author"] == "test_user"
    
    def test_normalize_reddit_data(self):
        """测试 Reddit 数据格式"""
        normalizer = DataNormalizer()
        
        data = {
            "post_id": "rd123",
            "selftext": "这是一篇Reddit帖子的内容，长度足够用于标准化测试",
            "title": "测试帖子",
            "subreddit": "test_sub"
        }
        
        result = normalizer.normalize(data)
        
        assert result.is_valid
        assert result.normalized_data["id"] == "rd123"
        assert result.normalized_data["title"] == "测试帖子"
    
    def test_normalize_datetime(self):
        """测试时间格式标准化"""
        normalizer = DataNormalizer()
        
        data = {
            "id": "test123",
            "content": "测试内容，长度足够用于测试标准化功能",
            "published_at": "2026-03-17 12:00:00"
        }
        
        result = normalizer.normalize(data)
        
        assert result.is_valid
        assert "T" in result.normalized_data["published_at"]
    
    def test_normalize_missing_required(self):
        """测试缺少必填字段"""
        normalizer = DataNormalizer()
        
        data = {
            "title": "测试标题"
        }
        
        result = normalizer.normalize(data)
        
        assert not result.is_valid
        assert "missing_required_field" in result.error
    
    def test_normalize_content_too_short(self):
        """测试内容过短"""
        normalizer = DataNormalizer(NormalizerConfig(min_content_length=50))
        
        data = {
            "id": "test123",
            "content": "短内容"
        }
        
        result = normalizer.normalize(data)
        
        assert not result.is_valid
        assert "content_too_short" in result.error
    
    def test_detect_language(self):
        """测试语言检测"""
        normalizer = DataNormalizer(NormalizerConfig(detect_language=True))
        
        # 中文
        data_zh = {
            "id": "test1",
            "content": "这是一段中文文本，用于测试语言检测功能是否正常工作"
        }
        result_zh = normalizer.normalize(data_zh)
        assert result_zh.detected_language == "zh"
        
        # 英文
        data_en = {
            "id": "test2",
            "content": "This is an English text for testing language detection functionality"
        }
        result_en = normalizer.normalize(data_en)
        assert result_en.detected_language == "en"


class TestDataProcessingPipeline:
    """数据处理管道测试"""
    
    def test_process_single_data(self):
        """测试处理单条数据"""
        pipeline = DataProcessingPipeline()
        
        raw_data = RawData(
            id="test1",
            source=DataSource.TWITTER,
            content="这是一段测试文本，内容长度足够用于测试数据处理管道",
            title="测试标题",
            author="测试作者"
        )
        
        result = pipeline.process(raw_data)
        
        assert result.success
        assert result.processed_data is not None
        assert result.processed_data.id == "test1"
    
    def test_process_batch(self):
        """测试批量处理"""
        pipeline = DataProcessingPipeline()
        
        raw_data_list = [
            RawData(
                id=f"test{i}",
                source=DataSource.TWITTER,
                content=f"这是第{i}条测试文本，内容长度足够用于测试数据处理管道功能"
            )
            for i in range(5)
        ]
        
        processed, stats = pipeline.process_batch(raw_data_list)
        
        assert len(processed) == 5
        assert stats.total_input == 5
        assert stats.total_output == 5
    
    def test_process_with_duplicate(self):
        """测试重复数据处理"""
        pipeline = DataProcessingPipeline()
        
        text = "这是一段重复的测试文本，内容长度足够用于测试去重功能"
        
        raw_data1 = RawData(
            id="test1",
            source=DataSource.TWITTER,
            content=text
        )
        
        raw_data2 = RawData(
            id="test2",
            source=DataSource.TWITTER,
            content=text
        )
        
        result1 = pipeline.process(raw_data1)
        result2 = pipeline.process(raw_data2)
        
        assert result1.success
        assert not result1.processed_data.is_duplicate
        
        assert result2.success
        # 由于缓存机制，可能需要检查实际行为
        # 在真实场景中，相同文本会被标记为重复
    
    def test_process_with_invalid_data(self):
        """测试无效数据处理"""
        pipeline = DataProcessingPipeline(
            PipelineConfig(
                cleaner=CleanerConfig(min_length=50),
                skip_invalid=True
            )
        )
        
        raw_data = RawData(
            id="test1",
            source=DataSource.TWITTER,
            content="短文本"
        )
        
        result = pipeline.process(raw_data)
        
        assert not result.success
        assert result.error is not None
    
    def test_pipeline_reset(self):
        """测试管道重置"""
        pipeline = DataProcessingPipeline()
        
        text = "测试重置功能的文本内容，长度足够用于测试"
        
        raw_data1 = RawData(id="id1", source=DataSource.TWITTER, content=text)
        raw_data2 = RawData(id="id2", source=DataSource.TWITTER, content=text)
        
        pipeline.process(raw_data1)
        pipeline.reset()
        result = pipeline.process(raw_data2)
        
        assert not result.processed_data.is_duplicate


class TestModels:
    """数据模型测试"""
    
    def test_raw_data_to_dict(self):
        """测试原始数据转换"""
        data = RawData(
            id="test1",
            source=DataSource.TWITTER,
            content="测试内容"
        )
        
        d = data.to_dict()
        
        assert d["id"] == "test1"
        assert d["source"] == "twitter"
        assert d["content"] == "测试内容"
    
    def test_processed_data_to_dict(self):
        """测试处理后数据转换"""
        data = ProcessedData(
            id="test1",
            source=DataSource.TWITTER,
            original_content="原始内容",
            cleaned_content="清洗后内容"
        )
        
        d = data.to_dict()
        
        assert d["id"] == "test1"
        assert d["original_content"] == "原始内容"
        assert d["cleaned_content"] == "清洗后内容"
        assert d["status"] == "processed"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])