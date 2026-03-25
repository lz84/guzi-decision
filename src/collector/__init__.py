"""
数据采集模块

负责从多个数据源采集舆情数据，统一输出为标准化格式。

模块结构:
- base: 采集器基类
- agent_reach: agent-reach 数据采集
- tavily: Tavily 搜索采集
- models: 数据模型
- pipeline: 采集管道
"""

from .base import Collector, CollectorConfig, CollectorResult
from .models import (
    RawData,
    DataSource,
    CollectTask,
    CollectStatus,
)
from .agent_reach import AgentReachCollector
from .tavily import TavilyCollector
from .pipeline import CollectionPipeline

__all__ = [
    # 基类
    "Collector",
    "CollectorConfig",
    "CollectorResult",
    # 采集器
    "AgentReachCollector",
    "TavilyCollector",
    # 管道
    "CollectionPipeline",
    # 数据模型
    "RawData",
    "DataSource",
    "CollectTask",
    "CollectStatus",
]