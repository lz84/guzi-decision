"""
分析服务 - 封装文本分析逻辑
"""

from datetime import datetime
from typing import Any, Optional
import uuid

from ..analyzer.engine import AnalysisEngine
from ..analyzer.models import AnalysisResult, SentimentResult, Entity, Event
from ..storage.base import BaseStorage
from ..storage.models import StoredDocument, StoredAnalysis, DocumentStatus


class AnalyzerService:
    """分析服务"""

    def __init__(self, storage: BaseStorage):
        self.storage = storage
        self._engine: Optional[AnalysisEngine] = None

    async def initialize(self) -> None:
        """初始化服务"""
        self._engine = AnalysisEngine()
        await self._engine.initialize()

    async def analyze_document(self, document_id: str) -> Optional[StoredAnalysis]:
        """分析单个文档"""
        # 获取文档
        doc = await self.storage.get_document(document_id)
        if not doc:
            return None

        # 执行分析
        if not self._engine:
            raise RuntimeError("分析引擎未初始化")

        result = await self._engine.analyze(doc.content)

        # 存储分析结果
        analysis = StoredAnalysis(
            id=str(uuid.uuid4()),
            document_id=document_id,
            text=doc.content,
            sentiment_label=result.sentiment.label.value if result.sentiment else None,
            sentiment_score=result.sentiment.score if result.sentiment else None,
            confidence=result.sentiment.confidence if result.sentiment else 0.0,
            entities=[e.to_dict() for e in result.entities],
            events=[e.to_dict() for e in result.events],
            keywords=result.keywords,
            topics=result.topics,
            language=result.language,
            processing_time_ms=result.processing_time_ms,
        )

        await self.storage.save_analysis(analysis)

        # 更新文档状态
        await self.storage.update_document(document_id, {
            "status": DocumentStatus.ANALYZED.value,
            "sentiment_label": analysis.sentiment_label,
            "sentiment_score": analysis.sentiment_score,
            "entities": analysis.entities,
            "keywords": analysis.keywords,
            "processed_at": datetime.now().isoformat(),
        })

        return analysis

    async def analyze_text(self, text: str) -> AnalysisResult:
        """直接分析文本"""
        if not self._engine:
            raise RuntimeError("分析引擎未初始化")
        return await self._engine.analyze(text)

    async def batch_analyze(
        self,
        document_ids: list[str],
        limit: int = 100,
    ) -> list[StoredAnalysis]:
        """批量分析文档"""
        results = []
        for doc_id in document_ids[:limit]:
            analysis = await self.analyze_document(doc_id)
            if analysis:
                results.append(analysis)
        return results

    async def analyze_unprocessed(self, limit: int = 50) -> list[StoredAnalysis]:
        """分析未处理的文档"""
        # 查询未分析文档
        docs = await self.storage.query_documents(
            status=DocumentStatus.RAW.value,
            limit=limit,
        )

        results = []
        for doc in docs:
            analysis = await self.analyze_document(doc.id)
            if analysis:
                results.append(analysis)

        return results

    async def get_sentiment_summary(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> dict[str, Any]:
        """获取情感分析摘要"""
        stats = await self.storage.get_sentiment_stats(start_time, end_time)
        total = sum(stats.values())

        return {
            "distribution": stats,
            "total_analyzed": total,
            "positive_ratio": stats.get("positive", 0) / total if total > 0 else 0,
            "negative_ratio": stats.get("negative", 0) / total if total > 0 else 0,
            "neutral_ratio": stats.get("neutral", 0) / total if total > 0 else 0,
        }

    async def get_trending_entities(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """获取热门实体"""
        return await self.storage.get_entity_stats(start_time, end_time, limit)

    async def get_trending_keywords(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """获取热门关键词"""
        return await self.storage.get_keyword_stats(start_time, end_time, limit)