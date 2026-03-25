"""
存储模块 - 基类定义
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Optional

from .models import StoredDocument, StoredAnalysis, StoredAlert, StoredReport


class BaseStorage(ABC):
    """存储基类"""

    @abstractmethod
    async def connect(self) -> None:
        """连接存储"""
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """断开连接"""
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """健康检查"""
        pass

    # ==================== 文档操作 ====================

    @abstractmethod
    async def save_document(self, document: StoredDocument) -> bool:
        """保存文档"""
        pass

    @abstractmethod
    async def get_document(self, doc_id: str) -> Optional[StoredDocument]:
        """获取文档"""
        pass

    @abstractmethod
    async def update_document(self, doc_id: str, updates: dict[str, Any]) -> bool:
        """更新文档"""
        pass

    @abstractmethod
    async def delete_document(self, doc_id: str) -> bool:
        """删除文档"""
        pass

    @abstractmethod
    async def query_documents(
        self,
        source: Optional[str] = None,
        status: Optional[str] = None,
        sentiment_label: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        keywords: Optional[list[str]] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[StoredDocument]:
        """查询文档"""
        pass

    @abstractmethod
    async def count_documents(
        self,
        source: Optional[str] = None,
        status: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> int:
        """统计文档数量"""
        pass

    # ==================== 分析结果操作 ====================

    @abstractmethod
    async def save_analysis(self, analysis: StoredAnalysis) -> bool:
        """保存分析结果"""
        pass

    @abstractmethod
    async def get_analysis(self, analysis_id: str) -> Optional[StoredAnalysis]:
        """获取分析结果"""
        pass

    @abstractmethod
    async def get_analysis_by_document(self, document_id: str) -> Optional[StoredAnalysis]:
        """根据文档ID获取分析结果"""
        pass

    @abstractmethod
    async def query_analyses(
        self,
        sentiment_label: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[StoredAnalysis]:
        """查询分析结果"""
        pass

    # ==================== 预警操作 ====================

    @abstractmethod
    async def save_alert(self, alert: StoredAlert) -> bool:
        """保存预警"""
        pass

    @abstractmethod
    async def get_alert(self, alert_id: str) -> Optional[StoredAlert]:
        """获取预警"""
        pass

    @abstractmethod
    async def acknowledge_alert(self, alert_id: str, acknowledged_by: Optional[str] = None) -> bool:
        """确认预警"""
        pass

    @abstractmethod
    async def query_alerts(
        self,
        level: Optional[str] = None,
        acknowledged: Optional[bool] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[StoredAlert]:
        """查询预警"""
        pass

    # ==================== 报告操作 ====================

    @abstractmethod
    async def save_report(self, report: StoredReport) -> bool:
        """保存报告"""
        pass

    @abstractmethod
    async def get_report(self, report_id: str) -> Optional[StoredReport]:
        """获取报告"""
        pass

    @abstractmethod
    async def get_report_by_date(self, report_type: str, date: str) -> Optional[StoredReport]:
        """根据日期获取报告"""
        pass

    @abstractmethod
    async def query_reports(
        self,
        report_type: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[StoredReport]:
        """查询报告"""
        pass

    # ==================== 统计操作 ====================

    @abstractmethod
    async def get_sentiment_stats(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> dict[str, int]:
        """获取情感分布统计"""
        pass

    @abstractmethod
    async def get_keyword_stats(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """获取关键词统计"""
        pass

    @abstractmethod
    async def get_entity_stats(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """获取实体统计"""
        pass