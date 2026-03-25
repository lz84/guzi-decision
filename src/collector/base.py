"""
采集器基类

定义采集器的标准接口和通用功能。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
import asyncio
import uuid

from .models import RawData, DataSource, CollectTask, CollectStatus


@dataclass
class CollectorConfig:
    """采集器配置"""
    # 采集器名称
    name: str
    # 数据源
    source: DataSource
    # 是否启用
    enabled: bool = True
    # 请求超时（秒）
    timeout: int = 30
    # 最大重试次数
    max_retries: int = 3
    # 重试间隔（秒）
    retry_delay: float = 1.0
    # 每分钟请求限制
    rate_limit: int = 100
    # 批量大小
    batch_size: int = 50
    # 额外配置
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class CollectorResult:
    """采集结果"""
    success: bool
    data: list[RawData] = field(default_factory=list)
    total_count: int = 0
    error_message: Optional[str] = None
    processing_time_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "success": self.success,
            "data": [item.to_dict() for item in self.data],
            "total_count": self.total_count,
            "error_message": self.error_message,
            "processing_time_ms": self.processing_time_ms,
            "metadata": self.metadata,
        }


class Collector(ABC):
    """
    采集器抽象基类
    
    所有数据采集器都需要继承此类并实现以下方法：
    - collect(): 执行数据采集
    - test_connection(): 测试连接是否正常
    """
    
    def __init__(self, config: CollectorConfig):
        self.config = config
        self._is_available = False
        self._last_error: Optional[str] = None
        self._request_count = 0
        self._last_request_time: Optional[datetime] = None
    
    @abstractmethod
    async def collect(
        self,
        keywords: list[str],
        limit: int = 100,
        options: Optional[dict[str, Any]] = None
    ) -> CollectorResult:
        """
        采集数据
        
        Args:
            keywords: 关键词列表
            limit: 最大返回数量
            options: 额外选项
            
        Returns:
            CollectorResult: 采集结果
        """
        pass
    
    @abstractmethod
    async def test_connection(self) -> bool:
        """
        测试连接
        
        Returns:
            bool: 连接是否成功
        """
        pass
    
    @property
    def name(self) -> str:
        """采集器名称"""
        return self.config.name
    
    @property
    def source(self) -> DataSource:
        """数据源"""
        return self.config.source
    
    @property
    def is_available(self) -> bool:
        """是否可用"""
        return self._is_available and self.config.enabled
    
    @property
    def last_error(self) -> Optional[str]:
        """最后一次错误"""
        return self._last_error
    
    async def health_check(self) -> dict[str, Any]:
        """
        健康检查
        
        Returns:
            dict: 健康状态
        """
        try:
            is_connected = await self.test_connection()
            self._is_available = is_connected
            
            return {
                "name": self.name,
                "source": self.source.value,
                "available": is_connected,
                "enabled": self.config.enabled,
                "last_error": self._last_error,
                "last_check": datetime.now().isoformat(),
            }
        except Exception as e:
            self._last_error = str(e)
            return {
                "name": self.name,
                "source": self.source.value,
                "available": False,
                "enabled": self.config.enabled,
                "last_error": str(e),
                "last_check": datetime.now().isoformat(),
            }
    
    def _generate_id(self) -> str:
        """生成唯一ID"""
        return f"{self.source.value}_{uuid.uuid4().hex[:12]}"
    
    async def _execute_with_retry(
        self,
        func,
        *args,
        **kwargs
    ) -> Any:
        """
        带重试的执行
        
        Args:
            func: 要执行的异步函数
            args: 位置参数
            kwargs: 关键字参数
            
        Returns:
            执行结果
        """
        last_error = None
        
        for attempt in range(self.config.max_retries):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                last_error = e
                self._last_error = str(e)
                
                if attempt < self.config.max_retries - 1:
                    # 指数退避
                    delay = self.config.retry_delay * (2 ** attempt)
                    await asyncio.sleep(delay)
        
        raise last_error
    
    def _update_rate_limit(self):
        """更新请求计数"""
        now = datetime.now()
        if self._last_request_time:
            # 如果超过1分钟，重置计数
            elapsed = (now - self._last_request_time).total_seconds()
            if elapsed >= 60:
                self._request_count = 0
        
        self._request_count += 1
        self._last_request_time = now
    
    def _check_rate_limit(self) -> bool:
        """检查是否超过速率限制"""
        if self._last_request_time:
            elapsed = (datetime.now() - self._last_request_time).total_seconds()
            if elapsed >= 60:
                return True
            if self._request_count >= self.config.rate_limit:
                return False
        return True
    
    async def wait_for_rate_limit(self):
        """等待速率限制"""
        while not self._check_rate_limit():
            await asyncio.sleep(1)
    
    def get_stats(self) -> dict[str, Any]:
        """获取统计信息"""
        return {
            "name": self.name,
            "source": self.source.value,
            "available": self._is_available,
            "enabled": self.config.enabled,
            "request_count": self._request_count,
            "last_request_time": self._last_request_time.isoformat() if self._last_request_time else None,
            "last_error": self._last_error,
        }


# 别名，保持向后兼容
BaseCollector = Collector