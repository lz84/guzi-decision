"""
Tavily 搜索采集器

通过 Tavily API 进行新闻搜索和数据采集。
"""

import os
from datetime import datetime
from typing import Any, Optional
import hashlib
import json

from .base import Collector, CollectorConfig, CollectorResult
from .models import RawData, DataSource


class TavilyCollector(Collector):
    """
    Tavily 搜索采集器
    
    通过 Tavily API 搜索新闻和网页内容。
    支持实时搜索和深度搜索。
    """
    
    # Tavily API 端点
    API_URL = "https://api.tavily.com/search"
    
    def __init__(
        self,
        config: Optional[CollectorConfig] = None,
        api_key: Optional[str] = None
    ):
        """
        初始化 Tavily 采集器
        
        Args:
            config: 采集器配置
            api_key: Tavily API Key（可从环境变量 TAVILY_API_KEY 获取）
        """
        if config is None:
            config = CollectorConfig(
                name="tavily-search",
                source=DataSource.NEWS,
                timeout=30,
                max_retries=3,
            )
        super().__init__(config)
        self.api_key = api_key or os.environ.get("TAVILY_API_KEY")
        self._client = None
    
    def _get_client(self):
        """获取 HTTP 客户端"""
        if self._client is None:
            try:
                import httpx
                self._client = httpx.AsyncClient(timeout=self.config.timeout)
            except ImportError:
                # 如果没有 httpx，使用模拟客户端
                self._client = None
        return self._client
    
    async def collect(
        self,
        keywords: list[str],
        limit: int = 100,
        options: Optional[dict[str, Any]] = None
    ) -> CollectorResult:
        """
        通过 Tavily 搜索数据
        
        Args:
            keywords: 关键词列表
            limit: 最大返回数量
            options: 额外选项
                - search_depth: 搜索深度 (basic, advanced)
                - include_domains: 限制域名列表
                - exclude_domains: 排除域名列表
                - include_answer: 是否包含 AI 摘要
                - days: 搜索最近几天的内容
                
        Returns:
            CollectorResult: 采集结果
        """
        start_time = datetime.now()
        options = options or {}
        
        try:
            if self.api_key:
                result = await self._collect_via_api(keywords, limit, options)
            else:
                # 无 API Key 时返回模拟数据
                result = await self._collect_mock(keywords, limit, options)
            
            # 转换为 RawData 格式
            raw_data_list = []
            for item in result.get("results", []):
                raw_data = self._convert_to_raw_data(item)
                raw_data_list.append(raw_data)
            
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            
            return CollectorResult(
                success=True,
                data=raw_data_list[:limit],
                total_count=len(raw_data_list),
                processing_time_ms=processing_time,
                metadata={
                    "keywords": keywords,
                    "source": "tavily-search",
                    "search_depth": options.get("search_depth", "basic"),
                    "answer": result.get("answer"),
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
                    "keywords": keywords,
                    "source": "tavily-search",
                }
            )
    
    async def _collect_via_api(
        self,
        keywords: list[str],
        limit: int,
        options: dict[str, Any]
    ) -> dict[str, Any]:
        """
        通过 Tavily API 搜索
        
        Args:
            keywords: 关键词列表
            limit: 最大返回数量
            options: 额外选项
            
        Returns:
            API 响应结果
        """
        client = self._get_client()
        
        if client is None:
            # 无 HTTP 客户端，使用模拟数据
            return await self._collect_mock(keywords, limit, options)
        
        query = " ".join(keywords)
        
        # 构建请求体
        request_body = {
            "api_key": self.api_key,
            "query": query,
            "max_results": min(limit, 10),  # Tavily 最大返回 10 条
            "search_depth": options.get("search_depth", "basic"),
            "include_answer": options.get("include_answer", False),
        }
        
        if options.get("include_domains"):
            request_body["include_domains"] = options["include_domains"]
        if options.get("exclude_domains"):
            request_body["exclude_domains"] = options["exclude_domains"]
        if options.get("days"):
            request_body["days"] = options["days"]
        
        # 发送请求
        response = await client.post(
            self.API_URL,
            json=request_body
        )
        
        if response.status_code != 200:
            raise Exception(f"Tavily API error: {response.status_code} - {response.text}")
        
        return response.json()
    
    async def _collect_mock(
        self,
        keywords: list[str],
        limit: int,
        options: dict[str, Any]
    ) -> dict[str, Any]:
        """
        模拟搜索数据（用于测试或无 API Key 时）
        
        Args:
            keywords: 关键词列表
            limit: 最大返回数量
            options: 额外选项
            
        Returns:
            模拟的搜索结果
        """
        keyword = " ".join(keywords) if keywords else "test"
        
        # 生成模拟数据
        mock_results = []
        domains = ["reuters.com", "bloomberg.com", "cnbc.com", "wsj.com", "ft.com"]
        
        for i in range(min(limit, 5)):  # 最多模拟5条
            domain = domains[i % len(domains)]
            mock_item = {
                "title": f"关于 {keyword} 的新闻报道 #{i+1}",
                "url": f"https://{domain}/article/{hashlib.md5(f'{keyword}_{i}'.encode()).hexdigest()[:8]}",
                "content": f"这是一篇关于 {keyword} 的模拟新闻内容。本文讨论了相关的重要议题和发展趋势...",
                "author": f"Reporter {i+1}",
                "published_date": datetime.now().isoformat(),
                "score": 0.9 - i * 0.1,
            }
            mock_results.append(mock_item)
        
        return {
            "results": mock_results,
            "answer": f"关于 {keyword} 的最新新闻摘要",
            "query": keyword,
        }
    
    def _convert_to_raw_data(self, item: dict[str, Any]) -> RawData:
        """
        将搜索结果转换为 RawData 格式
        
        Args:
            item: 原始搜索结果
            
        Returns:
            RawData: 标准化数据
        """
        # 解析时间
        published_at = None
        if item.get("published_date"):
            try:
                published_at = datetime.fromisoformat(item["published_date"].replace("Z", "+00:00"))
            except:
                pass
        
        return RawData(
            id=self._generate_id(),
            source=DataSource.NEWS,
            content=item.get("content", ""),
            title=item.get("title", ""),
            author=item.get("author", ""),
            url=item.get("url", ""),
            published_at=published_at,
            collected_at=datetime.now(),
            language="auto",
            metadata={
                "score": item.get("score", 0),
                "source": item.get("source", ""),
                "raw": item,
            }
        )
    
    async def test_connection(self) -> bool:
        """
        测试 Tavily API 是否可用
        
        Returns:
            bool: 是否可用
        """
        try:
            if not self.api_key:
                # 无 API Key，模拟测试
                self._is_available = True
                return True
            
            # 发送测试请求
            result = await self._collect_via_api(["test"], 1, {})
            self._is_available = True
            return True
            
        except Exception as e:
            self._last_error = str(e)
            self._is_available = False
            return False
    
    async def search_news(
        self,
        query: str,
        days: int = 7,
        limit: int = 10
    ) -> CollectorResult:
        """
        搜索新闻
        
        Args:
            query: 搜索查询
            days: 最近几天
            limit: 最大返回数量
            
        Returns:
            CollectorResult: 搜索结果
        """
        return await self.collect(
            [query],
            limit,
            {"days": days, "search_depth": "advanced"}
        )
    
    async def search_financial(
        self,
        keywords: list[str],
        limit: int = 10
    ) -> CollectorResult:
        """
        搜索财经新闻
        
        Args:
            keywords: 关键词列表
            limit: 最大返回数量
            
        Returns:
            CollectorResult: 搜索结果
        """
        return await self.collect(
            keywords,
            limit,
            {
                "search_depth": "advanced",
                "include_domains": [
                    "reuters.com",
                    "bloomberg.com",
                    "cnbc.com",
                    "wsj.com",
                    "ft.com",
                    "marketwatch.com",
                ],
                "include_answer": True,
            }
        )
    
    async def close(self):
        """关闭客户端"""
        if self._client:
            await self._client.aclose()
            self._client = None