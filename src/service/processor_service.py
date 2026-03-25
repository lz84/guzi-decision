"""
处理服务 - 封装数据处理逻辑
"""

from datetime import datetime
from typing import Any, Optional

from ..processor.pipeline import ProcessingPipeline
from ..processor.models import ProcessedData, ProcessingStats
from ..storage.base import BaseStorage
from ..storage.models import StoredDocument, DocumentStatus


class ProcessorService:
    """处理服务"""

    def __init__(self, storage: BaseStorage):
        self.storage = storage
        self._pipeline: Optional[ProcessingPipeline] = None

    async def initialize(self) -> None:
        """初始化服务"""
        self._pipeline = ProcessingPipeline()
        await self._pipeline.initialize()

    async def process_document(self, document_id: str) -> Optional[StoredDocument]:
        """处理单个文档"""
        # 获取文档
        doc = await self.storage.get_document(document_id)
        if not doc:
            return None

        # 执行处理
        if not self._pipeline:
            raise RuntimeError("处理管道未初始化")

        processed = await self._pipeline.process(doc.content)

        # 更新文档
        updates = {
            "content": processed.cleaned_content,
            "status": DocumentStatus.PROCESSING.value,
            "quality_score": processed.quality_score,
            "processed_at": datetime.now().isoformat(),
        }

        # 更新元数据
        metadata = doc.metadata.copy()
        metadata["original_content"] = processed.original_content
        metadata["is_duplicate"] = processed.is_duplicate
        metadata["duplicate_of"] = processed.duplicate_of
        updates["metadata"] = metadata

        await self.storage.update_document(document_id, updates)

        return await self.storage.get_document(document_id)

    async def process_batch(
        self,
        document_ids: list[str],
        limit: int = 100,
    ) -> ProcessingStats:
        """批量处理文档"""
        stats = ProcessingStats()

        for doc_id in document_ids[:limit]:
            stats.total_input += 1
            result = await self.process_document(doc_id)
            if result:
                stats.total_output += 1
                if result.metadata.get("is_duplicate"):
                    stats.duplicates_removed += 1

        return stats

    async def process_unprocessed(self, limit: int = 50) -> ProcessingStats:
        """处理未处理的文档"""
        # 查询原始文档
        docs = await self.storage.query_documents(
            status=DocumentStatus.RAW.value,
            limit=limit,
        )

        return await self.process_batch([d.id for d in docs])

    async def clean_document(self, document_id: str) -> Optional[StoredDocument]:
        """清洗文档"""
        doc = await self.storage.get_document(document_id)
        if not doc:
            return None

        if not self._pipeline:
            raise RuntimeError("处理管道未初始化")

        cleaned_content = await self._pipeline.clean(doc.content)

        await self.storage.update_document(document_id, {
            "content": cleaned_content,
            "status": DocumentStatus.PROCESSING.value,
        })

        return await self.storage.get_document(document_id)

    async def deduplicate_documents(
        self,
        document_ids: list[str],
    ) -> dict[str, Any]:
        """文档去重"""
        if not self._pipeline:
            raise RuntimeError("处理管道未初始化")

        # 收集所有文档内容
        contents = []
        docs = []
        for doc_id in document_ids:
            doc = await self.storage.get_document(doc_id)
            if doc:
                contents.append(doc.content)
                docs.append(doc)

        # 执行去重
        duplicates = await self._pipeline.deduplicate(contents)

        # 更新重复文档状态
        duplicate_count = 0
        for i, dup_info in enumerate(duplicates):
            if dup_info.get("is_duplicate"):
                doc = docs[i]
                await self.storage.update_document(doc.id, {
                    "metadata": {
                        **doc.metadata,
                        "is_duplicate": True,
                        "duplicate_of": dup_info.get("duplicate_of"),
                    }
                })
                duplicate_count += 1

        return {
            "total_processed": len(docs),
            "duplicates_found": duplicate_count,
        }

    async def get_processing_stats(self) -> dict[str, Any]:
        """获取处理统计"""
        raw_count = await self.storage.count_documents(status=DocumentStatus.RAW.value)
        processed_count = await self.storage.count_documents(status=DocumentStatus.ANALYZED.value)

        return {
            "raw_documents": raw_count,
            "processed_documents": processed_count,
            "pending_processing": raw_count,
        }