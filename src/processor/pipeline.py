"""
数据处理管道

整合清洗、去重、标准化模块，提供完整的数据处理流程。
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from .cleaner import DataCleaner, CleanerConfig, CleaningResult
from .deduplicator import TextDeduplicator, DeduplicatorConfig, DeduplicationResult
from .normalizer import DataNormalizer, NormalizerConfig, NormalizationResult
from .models import RawData, ProcessedData, ProcessingStats, DataSource


@dataclass
class PipelineConfig:
    """管道配置"""
    cleaner: CleanerConfig = field(default_factory=CleanerConfig)
    deduplicator: DeduplicatorConfig = field(default_factory=DeduplicatorConfig)
    normalizer: NormalizerConfig = field(default_factory=NormalizerConfig)
    
    # 是否启用各阶段
    enable_cleaning: bool = True
    enable_deduplication: bool = True
    enable_normalization: bool = True
    
    # 是否跳过无效数据
    skip_invalid: bool = True


@dataclass
class PipelineResult:
    """管道处理结果"""
    success: bool
    processed_data: Optional[ProcessedData] = None
    cleaning_result: Optional[CleaningResult] = None
    deduplication_result: Optional[DeduplicationResult] = None
    normalization_result: Optional[NormalizationResult] = None
    error: Optional[str] = None
    processing_time_ms: float = 0.0


class DataProcessingPipeline:
    """数据处理管道"""
    
    def __init__(self, config: Optional[PipelineConfig] = None):
        self.config = config or PipelineConfig()
        
        # 初始化各处理器
        self.cleaner = DataCleaner(self.config.cleaner)
        self.deduplicator = TextDeduplicator(self.config.deduplicator)
        self.normalizer = DataNormalizer(self.config.normalizer)
    
    async def initialize(self) -> None:
        """初始化管道（兼容性方法）"""
        pass
    
    def process(self, raw_data: RawData) -> PipelineResult:
        """
        处理单条数据
        
        Args:
            raw_data: 原始数据
            
        Returns:
            PipelineResult: 处理结果
        """
        start_time = datetime.now()
        
        try:
            current_content = raw_data.content
            cleaning_result = None
            deduplication_result = None
            normalization_result = None
            
            # 1. 数据清洗
            if self.config.enable_cleaning:
                cleaning_result = self.cleaner.clean(current_content)
                
                if not cleaning_result.is_valid and self.config.skip_invalid:
                    return PipelineResult(
                        success=False,
                        cleaning_result=cleaning_result,
                        error=f"cleaning_failed: {cleaning_result.invalid_reason}",
                        processing_time_ms=self._get_elapsed_ms(start_time)
                    )
                
                current_content = cleaning_result.cleaned
            
            # 2. 文本去重
            is_duplicate = False
            duplicate_of = None
            
            if self.config.enable_deduplication:
                deduplication_result = self.deduplicator.check(
                    current_content, 
                    raw_data.id
                )
                is_duplicate = deduplication_result.is_duplicate
                duplicate_of = deduplication_result.duplicate_of
            
            # 3. 数据标准化
            normalized_data = {}
            
            if self.config.enable_normalization:
                data_dict = {
                    "id": raw_data.id,
                    "content": current_content,
                    "source": raw_data.source.value,
                    "title": raw_data.title,
                    "author": raw_data.author,
                    "url": raw_data.url,
                    "published_at": raw_data.published_at.isoformat() if raw_data.published_at else None,
                    "collected_at": raw_data.collected_at.isoformat() if raw_data.collected_at else None,
                    **raw_data.metadata
                }
                
                normalization_result = self.normalizer.normalize(data_dict)
                
                if normalization_result.is_valid:
                    normalized_data = normalization_result.normalized_data
                elif self.config.skip_invalid:
                    return PipelineResult(
                        success=False,
                        cleaning_result=cleaning_result,
                        deduplication_result=deduplication_result,
                        normalization_result=normalization_result,
                        error=f"normalization_failed: {normalization_result.error}",
                        processing_time_ms=self._get_elapsed_ms(start_time)
                    )
            
            # 4. 构建处理结果
            quality_score = 1.0
            if normalization_result and normalization_result.is_valid:
                quality_score = normalization_result.quality_score
            
            processed_data = ProcessedData(
                id=raw_data.id,
                source=raw_data.source,
                original_content=raw_data.content,
                cleaned_content=current_content,
                title=raw_data.title,
                author=raw_data.author,
                url=raw_data.url,
                published_at=raw_data.published_at,
                collected_at=raw_data.collected_at,
                is_duplicate=is_duplicate,
                duplicate_of=duplicate_of,
                quality_score=quality_score,
                metadata=normalized_data.get("metadata", raw_data.metadata)
            )
            
            return PipelineResult(
                success=True,
                processed_data=processed_data,
                cleaning_result=cleaning_result,
                deduplication_result=deduplication_result,
                normalization_result=normalization_result,
                processing_time_ms=self._get_elapsed_ms(start_time)
            )
            
        except Exception as e:
            return PipelineResult(
                success=False,
                error=f"pipeline_error: {str(e)}",
                processing_time_ms=self._get_elapsed_ms(start_time)
            )
    
    def process_batch(self, raw_data_list: list[RawData]) -> tuple[list[ProcessedData], ProcessingStats]:
        """
        批量处理数据
        
        Args:
            raw_data_list: 原始数据列表
            
        Returns:
            (处理后的数据列表, 处理统计)
        """
        start_time = datetime.now()
        
        results = []
        processed = []
        duplicates = 0
        invalid = 0
        
        for raw_data in raw_data_list:
            result = self.process(raw_data)
            results.append(result)
            
            if result.success and result.processed_data:
                if result.processed_data.is_duplicate:
                    duplicates += 1
                processed.append(result.processed_data)
            else:
                invalid += 1
        
        stats = ProcessingStats(
            total_input=len(raw_data_list),
            total_output=len(processed),
            duplicates_removed=duplicates,
            invalid_removed=invalid,
            processing_time_ms=self._get_elapsed_ms(start_time)
        )
        
        return processed, stats
    
    def _get_elapsed_ms(self, start_time: datetime) -> float:
        """计算耗时（毫秒）"""
        elapsed = datetime.now() - start_time
        return elapsed.total_seconds() * 1000
    
    def reset(self):
        """重置管道状态（主要是去重器索引）"""
        self.deduplicator.reset()
    
    def get_stats(self, results: list[PipelineResult]) -> dict:
        """获取处理统计"""
        total = len(results)
        success = sum(1 for r in results if r.success)
        failed = total - success
        
        duplicates = sum(
            1 for r in results 
            if r.success and r.processed_data and r.processed_data.is_duplicate
        )
        
        avg_quality = 0.0
        quality_count = 0
        
        for r in results:
            if r.success and r.processed_data:
                avg_quality += r.processed_data.quality_score
                quality_count += 1
        
        return {
            "total": total,
            "success": success,
            "failed": failed,
            "success_rate": success / total if total > 0 else 0,
            "duplicates": duplicates,
            "avg_quality_score": avg_quality / quality_count if quality_count > 0 else 0,
            "avg_processing_time_ms": sum(r.processing_time_ms for r in results) / total if total > 0 else 0
        }


# 别名，保持向后兼容
ProcessingPipeline = DataProcessingPipeline