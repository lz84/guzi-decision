"""
采集服务 - 封装数据采集逻辑
"""

from datetime import datetime
from typing import Any, Optional
import uuid

from ..collector.base import BaseCollector
from ..collector.agent_reach import AgentReachCollector
from ..collector.tavily import TavilyCollector
from ..collector.models import RawData, CollectTask, CollectStatus, DataSource
from ..storage.base import BaseStorage
from ..storage.models import StoredDocument, DocumentStatus


class CollectorService:
    """采集服务"""

    def __init__(self, storage: BaseStorage):
        self.storage = storage
        self._collectors: dict[str, BaseCollector] = {}

    def register_collector(self, name: str, collector: BaseCollector) -> None:
        """注册采集器"""
        self._collectors[name] = collector

    async def initialize(self) -> None:
        """初始化服务"""
        # 注册默认采集器
        self._collectors["agent_reach"] = AgentReachCollector()
        self._collectors["tavily"] = TavilyCollector()

    async def collect(
        self,
        source: str,
        keywords: list[str],
        limit: int = 100,
        time_range: Optional[str] = None,
        options: Optional[dict[str, Any]] = None,
    ) -> CollectTask:
        """执行采集任务"""
        # 创建任务
        task = CollectTask(
            task_id=str(uuid.uuid4()),
            source=DataSource(source) if source in [e.value for e in DataSource] else DataSource.UNKNOWN,
            keywords=keywords,
            limit=limit,
            time_range=time_range,
            options=options or {},
        )

        # 更新状态
        task.status = CollectStatus.RUNNING
        task.started_at = datetime.now()

        try:
            # 获取采集器
            collector = self._collectors.get(source)
            if not collector:
                raise ValueError(f"未找到采集器: {source}")

            # 执行采集
            results = await collector.collect(
                keywords=keywords,
                limit=limit,
                time_range=time_range,
                **(options or {})
            )

            # 保存结果
            saved_count = 0
            for raw_data in results:
                doc = self._raw_to_document(raw_data)
                if await self.storage.save_document(doc):
                    saved_count += 1

            task.result_count = saved_count
            task.status = CollectStatus.COMPLETED

        except Exception as e:
            task.status = CollectStatus.FAILED
            task.error_message = str(e)

        finally:
            task.completed_at = datetime.now()

        return task

    async def collect_from_multiple_sources(
        self,
        sources: list[str],
        keywords: list[str],
        limit_per_source: int = 50,
        time_range: Optional[str] = None,
    ) -> list[CollectTask]:
        """从多个源采集数据"""
        tasks = []
        for source in sources:
            task = await self.collect(
                source=source,
                keywords=keywords,
                limit=limit_per_source,
                time_range=time_range,
            )
            tasks.append(task)
        return tasks

    async def get_collector_status(self) -> dict[str, Any]:
        """获取采集器状态"""
        return {
            name: {
                "available": collector.is_available() if hasattr(collector, 'is_available') else True,
                "type": type(collector).__name__,
            }
            for name, collector in self._collectors.items()
        }

    def _raw_to_document(self, raw_data: RawData) -> StoredDocument:
        """将原始数据转换为存储文档"""
        return StoredDocument(
            id=raw_data.id or str(uuid.uuid4()),
            source=raw_data.source.value if hasattr(raw_data.source, 'value') else str(raw_data.source),
            content=raw_data.content,
            title=raw_data.title,
            author=raw_data.author,
            url=raw_data.url,
            published_at=raw_data.published_at,
            collected_at=raw_data.collected_at or datetime.now(),
            status=DocumentStatus.RAW,
            language=raw_data.language,
            metadata=raw_data.metadata,
        )