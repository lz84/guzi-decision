"""
采集管道

协调多个采集器，支持并行采集和数据汇总。
"""

import asyncio
from datetime import datetime
from typing import Any, Optional
import uuid

from .base import Collector, CollectorConfig, CollectorResult
from .models import RawData, DataSource, CollectTask, CollectStatus, CollectStats


class CollectionPipeline:
    """
    采集管道
    
    管理多个采集器，支持并行采集、数据汇总和统计。
    """
    
    def __init__(self):
        self.collectors: dict[str, Collector] = {}
        self.tasks: dict[str, CollectTask] = {}
        self._stats = CollectStats()
    
    def register_collector(self, collector: Collector) -> None:
        """
        注册采集器
        
        Args:
            collector: 采集器实例
        """
        self.collectors[collector.name] = collector
    
    def unregister_collector(self, name: str) -> None:
        """
        注销采集器
        
        Args:
            name: 采集器名称
        """
        if name in self.collectors:
            del self.collectors[name]
    
    def get_collector(self, name: str) -> Optional[Collector]:
        """
        获取采集器
        
        Args:
            name: 采集器名称
            
        Returns:
            Collector: 采集器实例
        """
        return self.collectors.get(name)
    
    def list_collectors(self) -> list[dict[str, Any]]:
        """
        列出所有采集器
        
        Returns:
            list: 采集器列表
        """
        return [
            {
                "name": c.name,
                "source": c.source.value,
                "available": c.is_available,
            }
            for c in self.collectors.values()
        ]
    
    async def collect(
        self,
        keywords: list[str],
        sources: Optional[list[str]] = None,
        limit: int = 100,
        options: Optional[dict[str, Any]] = None
    ) -> dict[str, Any]:
        """
        执行采集
        
        Args:
            keywords: 关键词列表
            sources: 指定数据源列表（None 表示使用所有可用源）
            limit: 每个数据源的最大数量
            options: 额外选项
            
        Returns:
            dict: 采集结果
        """
        start_time = datetime.now()
        options = options or {}
        
        # 确定要使用的采集器
        if sources:
            collectors_to_use = [
                self.collectors[s] for s in sources
                if s in self.collectors
            ]
        else:
            collectors_to_use = [
                c for c in self.collectors.values()
                if c.is_available
            ]
        
        if not collectors_to_use:
            return {
                "success": False,
                "data": [],
                "total_count": 0,
                "error": "No available collectors",
                "processing_time_ms": (datetime.now() - start_time).total_seconds() * 1000,
            }
        
        # 并行采集
        tasks = [
            collector.collect(keywords, limit, options)
            for collector in collectors_to_use
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 汇总结果
        all_data: list[RawData] = []
        errors: list[dict[str, Any]] = []
        
        for collector, result in zip(collectors_to_use, results):
            if isinstance(result, Exception):
                errors.append({
                    "collector": collector.name,
                    "error": str(result),
                })
            elif result.success:
                all_data.extend(result.data)
            else:
                errors.append({
                    "collector": collector.name,
                    "error": result.error_message,
                })
        
        processing_time = (datetime.now() - start_time).total_seconds() * 1000
        
        # 更新统计
        self._stats.total_tasks += 1
        if errors:
            self._stats.failed_tasks += 1
            self._stats.errors.extend(errors)
        else:
            self._stats.completed_tasks += 1
        self._stats.total_items += len(all_data)
        
        return {
            "success": len(all_data) > 0,
            "data": [item.to_dict() for item in all_data],
            "total_count": len(all_data),
            "sources_used": [c.name for c in collectors_to_use],
            "errors": errors,
            "processing_time_ms": processing_time,
        }
    
    async def collect_task(
        self,
        task: CollectTask
    ) -> CollectTask:
        """
        执行采集任务
        
        Args:
            task: 采集任务
            
        Returns:
            CollectTask: 更新后的任务
        """
        task.status = CollectStatus.RUNNING
        task.started_at = datetime.now()
        self.tasks[task.task_id] = task
        
        try:
            result = await self.collect(
                keywords=task.keywords,
                sources=[task.source.value] if task.source != DataSource.UNKNOWN else None,
                limit=task.limit,
                options=task.options
            )
            
            task.status = CollectStatus.COMPLETED
            task.completed_at = datetime.now()
            task.result_count = result.get("total_count", 0)
            
        except Exception as e:
            task.status = CollectStatus.FAILED
            task.completed_at = datetime.now()
            task.error_message = str(e)
        
        self.tasks[task.task_id] = task
        return task
    
    def create_task(
        self,
        source: DataSource,
        keywords: list[str],
        limit: int = 100,
        options: Optional[dict[str, Any]] = None
    ) -> CollectTask:
        """
        创建采集任务
        
        Args:
            source: 数据源
            keywords: 关键词列表
            limit: 最大数量
            options: 额外选项
            
        Returns:
            CollectTask: 采集任务
        """
        task = CollectTask(
            task_id=f"task_{uuid.uuid4().hex[:12]}",
            source=source,
            keywords=keywords,
            limit=limit,
            options=options or {},
        )
        self.tasks[task.task_id] = task
        return task
    
    def get_task(self, task_id: str) -> Optional[CollectTask]:
        """
        获取任务
        
        Args:
            task_id: 任务ID
            
        Returns:
            CollectTask: 任务
        """
        return self.tasks.get(task_id)
    
    def get_task_status(self, task_id: str) -> Optional[dict[str, Any]]:
        """
        获取任务状态
        
        Args:
            task_id: 任务ID
            
        Returns:
            dict: 任务状态
        """
        task = self.tasks.get(task_id)
        if task:
            return task.to_dict()
        return None
    
    async def health_check(self) -> dict[str, Any]:
        """
        健康检查所有采集器
        
        Returns:
            dict: 健康状态
        """
        results = await asyncio.gather(
            *[c.health_check() for c in self.collectors.values()],
            return_exceptions=True
        )
        
        collectors_status = []
        for collector, result in zip(self.collectors.values(), results):
            if isinstance(result, Exception):
                collectors_status.append({
                    "name": collector.name,
                    "available": False,
                    "error": str(result),
                })
            else:
                collectors_status.append(result)
        
        available_count = sum(1 for s in collectors_status if s.get("available"))
        
        return {
            "total_collectors": len(self.collectors),
            "available_collectors": available_count,
            "collectors": collectors_status,
            "overall_available": available_count > 0,
        }
    
    def get_stats(self) -> dict[str, Any]:
        """
        获取统计信息
        
        Returns:
            dict: 统计信息
        """
        if self._stats.completed_tasks > 0:
            self._stats.avg_items_per_task = (
                self._stats.total_items / self._stats.completed_tasks
            )
        
        return self._stats.to_dict()
    
    def clear_stats(self) -> None:
        """清空统计"""
        self._stats = CollectStats()
    
    async def collect_twitter(
        self,
        keywords: list[str],
        limit: int = 100
    ) -> dict[str, Any]:
        """
        采集 Twitter 数据
        
        Args:
            keywords: 关键词列表
            limit: 最大数量
            
        Returns:
            dict: 采集结果
        """
        return await self.collect(
            keywords=keywords,
            sources=["agent-reach"],
            limit=limit,
            options={"platform": "twitter"}
        )
    
    async def collect_reddit(
        self,
        keywords: list[str],
        limit: int = 100,
        subreddit: Optional[str] = None
    ) -> dict[str, Any]:
        """
        采集 Reddit 数据
        
        Args:
            keywords: 关键词列表
            limit: 最大数量
            subreddit: 子版块
            
        Returns:
            dict: 采集结果
        """
        options = {"platform": "reddit"}
        if subreddit:
            options["subreddit"] = subreddit
        
        return await self.collect(
            keywords=keywords,
            sources=["agent-reach"],
            limit=limit,
            options=options
        )
    
    async def collect_news(
        self,
        keywords: list[str],
        limit: int = 50
    ) -> dict[str, Any]:
        """
        采集新闻数据
        
        Args:
            keywords: 关键词列表
            limit: 最大数量
            
        Returns:
            dict: 采集结果
        """
        return await self.collect(
            keywords=keywords,
            sources=["tavily-search"],
            limit=limit
        )
    
    async def collect_all(
        self,
        keywords: list[str],
        limit: int = 50
    ) -> dict[str, Any]:
        """
        从所有可用源采集数据
        
        Args:
            keywords: 关键词列表
            limit: 每个源的最大数量
            
        Returns:
            dict: 采集结果
        """
        return await self.collect(
            keywords=keywords,
            sources=None,  # 使用所有可用源
            limit=limit
        )