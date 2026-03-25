"""
Agent-Reach 数据采集器

通过 agent-reach 技能采集社交媒体数据。
支持 Twitter, Reddit, 微博等平台。
"""

import json
from datetime import datetime
from typing import Any, Optional
import hashlib

from .base import Collector, CollectorConfig, CollectorResult
from .models import RawData, DataSource


class AgentReachCollector(Collector):
    """
    Agent-Reach 采集器
    
    通过 OpenClaw 的 agent-reach 技能采集社交媒体数据。
    支持的平台：Twitter, Reddit, 微博等。
    """
    
    # 平台映射
    PLATFORM_MAPPING = {
        "twitter": DataSource.TWITTER,
        "x": DataSource.TWITTER,
        "reddit": DataSource.REDDIT,
        "weibo": DataSource.WEIBO,
        "youtube": DataSource.YOUTUBE,
        "wechat": DataSource.WECHAT,
    }
    
    def __init__(
        self,
        config: Optional[CollectorConfig] = None,
        skill_executor: Optional[Any] = None
    ):
        """
        初始化 Agent-Reach 采集器
        
        Args:
            config: 采集器配置
            skill_executor: 技能执行器（用于调用 agent-reach 技能）
        """
        if config is None:
            config = CollectorConfig(
                name="agent-reach",
                source=DataSource.TWITTER,
                timeout=60,
                max_retries=3,
            )
        super().__init__(config)
        self.skill_executor = skill_executor
    
    async def collect(
        self,
        keywords: list[str],
        limit: int = 100,
        options: Optional[dict[str, Any]] = None
    ) -> CollectorResult:
        """
        通过 agent-reach 采集数据
        
        Args:
            keywords: 关键词列表
            limit: 最大返回数量
            options: 额外选项
                - platform: 平台名称 (twitter, reddit, weibo, youtube)
                - time_range: 时间范围
                - language: 语言过滤
                
        Returns:
            CollectorResult: 采集结果
        """
        start_time = datetime.now()
        options = options or {}
        platform = options.get("platform", "twitter")
        
        try:
            # 调用 agent-reach 技能
            if self.skill_executor:
                result = await self._collect_via_skill(keywords, limit, options)
            else:
                # 无技能执行器时返回模拟数据
                result = await self._collect_mock(keywords, limit, options)
            
            # 转换为 RawData 格式
            raw_data_list = []
            for item in result.get("data", []):
                raw_data = self._convert_to_raw_data(item, platform)
                raw_data_list.append(raw_data)
            
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            
            return CollectorResult(
                success=True,
                data=raw_data_list[:limit],
                total_count=len(raw_data_list),
                processing_time_ms=processing_time,
                metadata={
                    "platform": platform,
                    "keywords": keywords,
                    "source": "agent-reach",
                }
            )
            
        except Exception as e:
            self._last_error = str(e)
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            
            return CollectorResult(
                success=False,
                data=[],
                total_count=0,
                error_message=str(e),
                processing_time_ms=processing_time,
                metadata={
                    "platform": platform,
                    "keywords": keywords,
                    "source": "agent-reach",
                }
            )
    
    async def _collect_via_skill(
        self,
        keywords: list[str],
        limit: int,
        options: dict[str, Any]
    ) -> dict[str, Any]:
        """
        通过技能执行器采集数据
        
        Args:
            keywords: 关键词列表
            limit: 最大返回数量
            options: 额外选项
            
        Returns:
            采集结果
        """
        platform = options.get("platform", "twitter")
        time_range = options.get("time_range")
        language = options.get("language")
        
        # 构建技能调用参数
        skill_params = {
            "platform": platform,
            "keywords": keywords,
            "limit": limit,
        }
        
        if time_range:
            skill_params["time_range"] = time_range
        if language:
            skill_params["language"] = language
        
        # 执行技能
        result = await self.skill_executor.execute(
            skill_name="agent-reach",
            params=skill_params
        )
        
        return result
    
    async def _collect_mock(
        self,
        keywords: list[str],
        limit: int,
        options: dict[str, Any]
    ) -> dict[str, Any]:
        """
        模拟采集数据（用于测试或无技能执行器时）
        
        Args:
            keywords: 关键词列表
            limit: 最大返回数量
            options: 额外选项
            
        Returns:
            模拟的采集结果
        """
        platform = options.get("platform", "twitter")
        
        # 生成模拟数据
        mock_data = []
        for i in range(min(limit, 10)):  # 最多模拟10条
            keyword = keywords[0] if keywords else "test"
            mock_item = {
                "id": f"{platform}_{hashlib.md5(f'{keyword}_{i}'.encode()).hexdigest()[:12]}",
                "content": f"这是一条关于 {keyword} 的模拟帖子内容 #{i+1}",
                "author": f"user_{i+1}",
                "url": f"https://{platform}.com/post/{i+1}",
                "created_at": datetime.now().isoformat(),
                "platform": platform,
                "metrics": {
                    "likes": 100 - i * 5,
                    "shares": 50 - i * 3,
                    "comments": 20 - i,
                }
            }
            mock_data.append(mock_item)
        
        return {
            "success": True,
            "data": mock_data,
            "total": len(mock_data),
        }
    
    def _convert_to_raw_data(
        self,
        item: dict[str, Any],
        platform: str
    ) -> RawData:
        """
        将采集结果转换为 RawData 格式
        
        Args:
            item: 原始采集数据
            platform: 平台名称
            
        Returns:
            RawData: 标准化数据
        """
        # 确定数据源
        source = self.PLATFORM_MAPPING.get(platform.lower(), DataSource.UNKNOWN)
        
        # 解析时间
        published_at = None
        if item.get("created_at"):
            try:
                published_at = datetime.fromisoformat(item["created_at"].replace("Z", "+00:00"))
            except:
                pass
        if item.get("published_at"):
            try:
                published_at = datetime.fromisoformat(item["published_at"].replace("Z", "+00:00"))
            except:
                pass
        
        return RawData(
            id=item.get("id", self._generate_id()),
            source=source,
            content=item.get("content", item.get("text", "")),
            title=item.get("title"),
            author=item.get("author", item.get("user", item.get("username", ""))),
            url=item.get("url", ""),
            published_at=published_at,
            collected_at=datetime.now(),
            language=item.get("language"),
            metadata={
                "platform": platform,
                "metrics": item.get("metrics", {}),
                "tags": item.get("tags", []),
                "raw": item,
            }
        )
    
    async def test_connection(self) -> bool:
        """
        测试 agent-reach 技能是否可用
        
        Returns:
            bool: 是否可用
        """
        try:
            if self.skill_executor:
                result = await self.skill_executor.test_skill("agent-reach")
                self._is_available = result.get("available", False)
            else:
                # 无技能执行器时，模拟测试
                self._is_available = True
            
            return self._is_available
            
        except Exception as e:
            self._last_error = str(e)
            self._is_available = False
            return False
    
    async def collect_twitter(
        self,
        keywords: list[str],
        limit: int = 100
    ) -> CollectorResult:
        """
        采集 Twitter 数据
        
        Args:
            keywords: 关键词列表
            limit: 最大返回数量
            
        Returns:
            CollectorResult: 采集结果
        """
        return await self.collect(keywords, limit, {"platform": "twitter"})
    
    async def collect_reddit(
        self,
        keywords: list[str],
        limit: int = 100,
        subreddit: Optional[str] = None
    ) -> CollectorResult:
        """
        采集 Reddit 数据
        
        Args:
            keywords: 关键词列表
            limit: 最大返回数量
            subreddit: 子版块名称
            
        Returns:
            CollectorResult: 采集结果
        """
        options = {"platform": "reddit"}
        if subreddit:
            options["subreddit"] = subreddit
        return await self.collect(keywords, limit, options)
    
    async def collect_weibo(
        self,
        keywords: list[str],
        limit: int = 100
    ) -> CollectorResult:
        """
        采集微博数据
        
        Args:
            keywords: 关键词列表
            limit: 最大返回数量
            
        Returns:
            CollectorResult: 采集结果
        """
        return await self.collect(keywords, limit, {"platform": "weibo"})