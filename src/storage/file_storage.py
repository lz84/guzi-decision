"""
存储模块 - 文件存储实现（备选方案）
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from .base import BaseStorage
from .models import StoredDocument, StoredAnalysis, StoredAlert, StoredReport


class FileStorage(BaseStorage):
    """文件存储实现（备选方案，用于无 MongoDB 环境）"""

    def __init__(self, base_path: str = "./data"):
        self.base_path = Path(base_path)
        self.documents_path = self.base_path / "documents"
        self.analyses_path = self.base_path / "analyses"
        self.alerts_path = self.base_path / "alerts"
        self.reports_path = self.base_path / "reports"
        self.index_path = self.base_path / "index"

        # 内存索引
        self._document_index: dict[str, dict[str, Any]] = {}
        self._analysis_index: dict[str, dict[str, Any]] = {}
        self._alert_index: dict[str, dict[str, Any]] = {}
        self._report_index: dict[str, dict[str, Any]] = {}

    async def connect(self) -> None:
        """初始化存储目录"""
        self.documents_path.mkdir(parents=True, exist_ok=True)
        self.analyses_path.mkdir(parents=True, exist_ok=True)
        self.alerts_path.mkdir(parents=True, exist_ok=True)
        self.reports_path.mkdir(parents=True, exist_ok=True)
        self.index_path.mkdir(parents=True, exist_ok=True)

        # 加载索引
        await self._load_indexes()

    async def disconnect(self) -> None:
        """保存索引并断开连接"""
        await self._save_indexes()

    async def health_check(self) -> bool:
        """健康检查"""
        return self.base_path.exists()

    async def _load_indexes(self) -> None:
        """加载索引"""
        index_file = self.index_path / "indexes.json"
        if index_file.exists():
            try:
                with open(index_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._document_index = data.get("documents", {})
                self._analysis_index = data.get("analyses", {})
                self._alert_index = data.get("alerts", {})
                self._report_index = data.get("reports", {})
            except Exception:
                pass

    async def _save_indexes(self) -> None:
        """保存索引"""
        index_file = self.index_path / "indexes.json"
        data = {
            "documents": self._document_index,
            "analyses": self._analysis_index,
            "alerts": self._alert_index,
            "reports": self._report_index,
        }
        with open(index_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _get_file_path(self, path: Path, item_id: str) -> Path:
        """获取文件路径"""
        return path / f"{item_id}.json"

    # ==================== 文档操作 ====================

    async def save_document(self, document: StoredDocument) -> bool:
        """保存文档"""
        try:
            file_path = self._get_file_path(self.documents_path, document.id)
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(document.to_dict(), f, ensure_ascii=False, indent=2)
            self._document_index[document.id] = {
                "source": document.source,
                "status": document.status.value,
                "sentiment_label": document.sentiment_label,
                "collected_at": document.collected_at.isoformat() if document.collected_at else None,
                "keywords": document.keywords,
            }
            return True
        except Exception as e:
            print(f"保存文档失败: {e}")
            return False

    async def get_document(self, doc_id: str) -> Optional[StoredDocument]:
        """获取文档"""
        file_path = self._get_file_path(self.documents_path, doc_id)
        if not file_path.exists():
            return None
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return StoredDocument.from_dict(data)
        except Exception:
            return None

    async def update_document(self, doc_id: str, updates: dict[str, Any]) -> bool:
        """更新文档"""
        doc = await self.get_document(doc_id)
        if not doc:
            return False

        # 更新字段
        for key, value in updates.items():
            if hasattr(doc, key):
                setattr(doc, key, value)
        doc.updated_at = datetime.now()

        return await self.save_document(doc)

    async def delete_document(self, doc_id: str) -> bool:
        """删除文档"""
        file_path = self._get_file_path(self.documents_path, doc_id)
        if file_path.exists():
            os.remove(file_path)
            self._document_index.pop(doc_id, None)
            return True
        return False

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
        results = []

        for doc_id, index_data in self._document_index.items():
            # 过滤条件
            if source and index_data.get("source") != source:
                continue
            if status and index_data.get("status") != status:
                continue
            if sentiment_label and index_data.get("sentiment_label") != sentiment_label:
                continue
            if start_time or end_time:
                collected_at_str = index_data.get("collected_at")
                if collected_at_str:
                    collected_at = datetime.fromisoformat(collected_at_str)
                    if start_time and collected_at < start_time:
                        continue
                    if end_time and collected_at > end_time:
                        continue
            if keywords:
                doc_keywords = index_data.get("keywords", [])
                if not any(k in doc_keywords for k in keywords):
                    continue

            doc = await self.get_document(doc_id)
            if doc:
                results.append(doc)

        # 排序和分页
        results.sort(key=lambda x: x.collected_at, reverse=True)
        return results[offset:offset + limit]

    async def count_documents(
        self,
        source: Optional[str] = None,
        status: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> int:
        """统计文档数量"""
        results = await self.query_documents(
            source=source,
            status=status,
            start_time=start_time,
            end_time=end_time,
            limit=100000,
        )
        return len(results)

    # ==================== 分析结果操作 ====================

    async def save_analysis(self, analysis: StoredAnalysis) -> bool:
        """保存分析结果"""
        try:
            file_path = self._get_file_path(self.analyses_path, analysis.id)
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(analysis.to_dict(), f, ensure_ascii=False, indent=2)
            self._analysis_index[analysis.id] = {
                "document_id": analysis.document_id,
                "sentiment_label": analysis.sentiment_label,
                "sentiment_score": analysis.sentiment_score,
                "created_at": analysis.created_at.isoformat() if analysis.created_at else None,
            }
            return True
        except Exception as e:
            print(f"保存分析结果失败: {e}")
            return False

    async def get_analysis(self, analysis_id: str) -> Optional[StoredAnalysis]:
        """获取分析结果"""
        file_path = self._get_file_path(self.analyses_path, analysis_id)
        if not file_path.exists():
            return None
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return StoredAnalysis.from_dict(data)
        except Exception:
            return None

    async def get_analysis_by_document(self, document_id: str) -> Optional[StoredAnalysis]:
        """根据文档ID获取分析结果"""
        for analysis_id, index_data in self._analysis_index.items():
            if index_data.get("document_id") == document_id:
                return await self.get_analysis(analysis_id)
        return None

    async def query_analyses(
        self,
        sentiment_label: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[StoredAnalysis]:
        """查询分析结果"""
        results = []

        for analysis_id, index_data in self._analysis_index.items():
            if sentiment_label and index_data.get("sentiment_label") != sentiment_label:
                continue
            if start_time or end_time:
                created_at_str = index_data.get("created_at")
                if created_at_str:
                    created_at = datetime.fromisoformat(created_at_str)
                    if start_time and created_at < start_time:
                        continue
                    if end_time and created_at > end_time:
                        continue

            analysis = await self.get_analysis(analysis_id)
            if analysis:
                results.append(analysis)

        results.sort(key=lambda x: x.created_at, reverse=True)
        return results[offset:offset + limit]

    # ==================== 预警操作 ====================

    async def save_alert(self, alert: StoredAlert) -> bool:
        """保存预警"""
        try:
            file_path = self._get_file_path(self.alerts_path, alert.id)
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(alert.to_dict(), f, ensure_ascii=False, indent=2)
            self._alert_index[alert.id] = {
                "level": alert.level.value,
                "acknowledged": alert.acknowledged,
                "triggered_at": alert.triggered_at.isoformat() if alert.triggered_at else None,
            }
            return True
        except Exception as e:
            print(f"保存预警失败: {e}")
            return False

    async def get_alert(self, alert_id: str) -> Optional[StoredAlert]:
        """获取预警"""
        file_path = self._get_file_path(self.alerts_path, alert_id)
        if not file_path.exists():
            return None
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return StoredAlert.from_dict(data)
        except Exception:
            return None

    async def acknowledge_alert(self, alert_id: str, acknowledged_by: Optional[str] = None) -> bool:
        """确认预警"""
        alert = await self.get_alert(alert_id)
        if not alert:
            return False

        alert.acknowledged = True
        alert.acknowledged_at = datetime.now()
        alert.acknowledged_by = acknowledged_by

        return await self.save_alert(alert)

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
        results = []

        for alert_id, index_data in self._alert_index.items():
            if level and index_data.get("level") != level:
                continue
            if acknowledged is not None and index_data.get("acknowledged") != acknowledged:
                continue
            if start_time or end_time:
                triggered_at_str = index_data.get("triggered_at")
                if triggered_at_str:
                    triggered_at = datetime.fromisoformat(triggered_at_str)
                    if start_time and triggered_at < start_time:
                        continue
                    if end_time and triggered_at > end_time:
                        continue

            alert = await self.get_alert(alert_id)
            if alert:
                results.append(alert)

        results.sort(key=lambda x: x.triggered_at, reverse=True)
        return results[offset:offset + limit]

    # ==================== 报告操作 ====================

    async def save_report(self, report: StoredReport) -> bool:
        """保存报告"""
        try:
            file_path = self._get_file_path(self.reports_path, report.id)
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(report.to_dict(), f, ensure_ascii=False, indent=2)
            self._report_index[report.id] = {
                "report_type": report.report_type.value,
                "date": report.date,
                "generated_at": report.generated_at.isoformat() if report.generated_at else None,
            }
            return True
        except Exception as e:
            print(f"保存报告失败: {e}")
            return False

    async def get_report(self, report_id: str) -> Optional[StoredReport]:
        """获取报告"""
        file_path = self._get_file_path(self.reports_path, report_id)
        if not file_path.exists():
            return None
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return StoredReport.from_dict(data)
        except Exception:
            return None

    async def get_report_by_date(self, report_type: str, date: str) -> Optional[StoredReport]:
        """根据日期获取报告"""
        for report_id, index_data in self._report_index.items():
            if (index_data.get("report_type") == report_type and
                index_data.get("date") == date):
                return await self.get_report(report_id)
        return None

    async def query_reports(
        self,
        report_type: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[StoredReport]:
        """查询报告"""
        results = []

        for report_id, index_data in self._report_index.items():
            if report_type and index_data.get("report_type") != report_type:
                continue
            if start_date or end_date:
                report_date = index_data.get("date", "")
                if start_date and report_date < start_date:
                    continue
                if end_date and report_date > end_date:
                    continue

            report = await self.get_report(report_id)
            if report:
                results.append(report)

        results.sort(key=lambda x: x.date, reverse=True)
        return results[offset:offset + limit]

    # ==================== 统计操作 ====================

    async def get_sentiment_stats(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> dict[str, int]:
        """获取情感分布统计"""
        stats: dict[str, int] = {}
        docs = await self.query_documents(
            start_time=start_time,
            end_time=end_time,
            limit=100000,
        )
        for doc in docs:
            label = doc.sentiment_label or "unknown"
            stats[label] = stats.get(label, 0) + 1
        return stats

    async def get_keyword_stats(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """获取关键词统计"""
        keyword_counts: dict[str, int] = {}
        docs = await self.query_documents(
            start_time=start_time,
            end_time=end_time,
            limit=100000,
        )
        for doc in docs:
            for keyword in doc.keywords:
                keyword_counts[keyword] = keyword_counts.get(keyword, 0) + 1

        sorted_keywords = sorted(keyword_counts.items(), key=lambda x: x[1], reverse=True)
        return [{"keyword": k, "count": c} for k, c in sorted_keywords[:limit]]

    async def get_entity_stats(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """获取实体统计"""
        entity_counts: dict[tuple[str, str], int] = {}
        docs = await self.query_documents(
            start_time=start_time,
            end_time=end_time,
            limit=100000,
        )
        for doc in docs:
            for entity in doc.entities:
                key = (entity.get("text", ""), entity.get("type", "unknown"))
                entity_counts[key] = entity_counts.get(key, 0) + 1

        sorted_entities = sorted(entity_counts.items(), key=lambda x: x[1], reverse=True)
        return [
            {"text": k[0], "type": k[1], "count": c}
            for k, c in sorted_entities[:limit]
        ]