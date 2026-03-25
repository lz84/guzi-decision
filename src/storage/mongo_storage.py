"""
存储模块 - MongoDB 实现
"""

from datetime import datetime
from typing import Any, Optional

try:
    from motor.motor_asyncio import AsyncIOMotorClient
    from motor.motor_asyncio import AsyncIOMotorDatabase
    MOTOR_AVAILABLE = True
except ImportError:
    MOTOR_AVAILABLE = False

from .base import BaseStorage
from .models import StoredDocument, StoredAnalysis, StoredAlert, StoredReport


class MongoStorage(BaseStorage):
    """MongoDB 存储实现"""

    def __init__(
        self,
        connection_string: str = "mongodb://localhost:27017",
        database_name: str = "guzi_decision",
    ):
        self.connection_string = connection_string
        self.database_name = database_name
        self.client: Optional[AsyncIOMotorClient] = None
        self.db: Optional[AsyncIOMotorDatabase] = None

    async def connect(self) -> None:
        """连接 MongoDB"""
        if not MOTOR_AVAILABLE:
            raise RuntimeError("motor 库未安装，请运行: pip install motor")

        self.client = AsyncIOMotorClient(self.connection_string)
        self.db = self.client[self.database_name]

        # 创建索引
        await self._create_indexes()

    async def disconnect(self) -> None:
        """断开连接"""
        if self.client:
            self.client.close()
            self.client = None
            self.db = None

    async def health_check(self) -> bool:
        """健康检查"""
        if self.client is None:
            return False
        try:
            await self.client.admin.command("ping")
            return True
        except Exception:
            return False

    async def _create_indexes(self) -> None:
        """创建索引"""
        if not self.db:
            return

        # 文档索引
        await self.db.documents.create_index("id", unique=True)
        await self.db.documents.create_index("source")
        await self.db.documents.create_index("status")
        await self.db.documents.create_index("sentiment_label")
        await self.db.documents.create_index("collected_at")
        await self.db.documents.create_index("keywords")

        # 分析结果索引
        await self.db.analyses.create_index("id", unique=True)
        await self.db.analyses.create_index("document_id", unique=True)
        await self.db.analyses.create_index("sentiment_label")
        await self.db.analyses.create_index("created_at")

        # 预警索引
        await self.db.alerts.create_index("id", unique=True)
        await self.db.alerts.create_index("level")
        await self.db.alerts.create_index("acknowledged")
        await self.db.alerts.create_index("triggered_at")

        # 报告索引
        await self.db.reports.create_index("id", unique=True)
        await self.db.reports.create_index([("report_type", 1), ("date", 1)], unique=True)
        await self.db.reports.create_index("generated_at")

    # ==================== 文档操作 ====================

    async def save_document(self, document: StoredDocument) -> bool:
        """保存文档"""
        if not self.db:
            return False
        try:
            doc_dict = document.to_dict()
            await self.db.documents.update_one(
                {"id": document.id},
                {"$set": doc_dict},
                upsert=True
            )
            return True
        except Exception as e:
            print(f"保存文档失败: {e}")
            return False

    async def get_document(self, doc_id: str) -> Optional[StoredDocument]:
        """获取文档"""
        if not self.db:
            return None
        doc = await self.db.documents.find_one({"id": doc_id})
        if doc:
            doc.pop("_id", None)
            return StoredDocument.from_dict(doc)
        return None

    async def update_document(self, doc_id: str, updates: dict[str, Any]) -> bool:
        """更新文档"""
        if not self.db:
            return False
        updates["updated_at"] = datetime.now().isoformat()
        result = await self.db.documents.update_one(
            {"id": doc_id},
            {"$set": updates}
        )
        return result.modified_count > 0

    async def delete_document(self, doc_id: str) -> bool:
        """删除文档"""
        if not self.db:
            return False
        result = await self.db.documents.delete_one({"id": doc_id})
        return result.deleted_count > 0

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
        if not self.db:
            return []

        query: dict[str, Any] = {}
        if source:
            query["source"] = source
        if status:
            query["status"] = status
        if sentiment_label:
            query["sentiment_label"] = sentiment_label
        if start_time or end_time:
            query["collected_at"] = {}
            if start_time:
                query["collected_at"]["$gte"] = start_time.isoformat()
            if end_time:
                query["collected_at"]["$lte"] = end_time.isoformat()
        if keywords:
            query["keywords"] = {"$in": keywords}

        cursor = self.db.documents.find(query).skip(offset).limit(limit).sort("collected_at", -1)
        docs = await cursor.to_list(length=limit)

        result = []
        for doc in docs:
            doc.pop("_id", None)
            result.append(StoredDocument.from_dict(doc))
        return result

    async def count_documents(
        self,
        source: Optional[str] = None,
        status: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> int:
        """统计文档数量"""
        if not self.db:
            return 0

        query: dict[str, Any] = {}
        if source:
            query["source"] = source
        if status:
            query["status"] = status
        if start_time or end_time:
            query["collected_at"] = {}
            if start_time:
                query["collected_at"]["$gte"] = start_time.isoformat()
            if end_time:
                query["collected_at"]["$lte"] = end_time.isoformat()

        return await self.db.documents.count_documents(query)

    # ==================== 分析结果操作 ====================

    async def save_analysis(self, analysis: StoredAnalysis) -> bool:
        """保存分析结果"""
        if not self.db:
            return False
        try:
            analysis_dict = analysis.to_dict()
            await self.db.analyses.update_one(
                {"id": analysis.id},
                {"$set": analysis_dict},
                upsert=True
            )
            return True
        except Exception as e:
            print(f"保存分析结果失败: {e}")
            return False

    async def get_analysis(self, analysis_id: str) -> Optional[StoredAnalysis]:
        """获取分析结果"""
        if not self.db:
            return None
        doc = await self.db.analyses.find_one({"id": analysis_id})
        if doc:
            doc.pop("_id", None)
            return StoredAnalysis.from_dict(doc)
        return None

    async def get_analysis_by_document(self, document_id: str) -> Optional[StoredAnalysis]:
        """根据文档ID获取分析结果"""
        if not self.db:
            return None
        doc = await self.db.analyses.find_one({"document_id": document_id})
        if doc:
            doc.pop("_id", None)
            return StoredAnalysis.from_dict(doc)
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
        if not self.db:
            return []

        query: dict[str, Any] = {}
        if sentiment_label:
            query["sentiment_label"] = sentiment_label
        if start_time or end_time:
            query["created_at"] = {}
            if start_time:
                query["created_at"]["$gte"] = start_time.isoformat()
            if end_time:
                query["created_at"]["$lte"] = end_time.isoformat()

        cursor = self.db.analyses.find(query).skip(offset).limit(limit).sort("created_at", -1)
        docs = await cursor.to_list(length=limit)

        result = []
        for doc in docs:
            doc.pop("_id", None)
            result.append(StoredAnalysis.from_dict(doc))
        return result

    # ==================== 预警操作 ====================

    async def save_alert(self, alert: StoredAlert) -> bool:
        """保存预警"""
        if not self.db:
            return False
        try:
            alert_dict = alert.to_dict()
            await self.db.alerts.update_one(
                {"id": alert.id},
                {"$set": alert_dict},
                upsert=True
            )
            return True
        except Exception as e:
            print(f"保存预警失败: {e}")
            return False

    async def get_alert(self, alert_id: str) -> Optional[StoredAlert]:
        """获取预警"""
        if not self.db:
            return None
        doc = await self.db.alerts.find_one({"id": alert_id})
        if doc:
            doc.pop("_id", None)
            return StoredAlert.from_dict(doc)
        return None

    async def acknowledge_alert(self, alert_id: str, acknowledged_by: Optional[str] = None) -> bool:
        """确认预警"""
        if not self.db:
            return False
        result = await self.db.alerts.update_one(
            {"id": alert_id},
            {
                "$set": {
                    "acknowledged": True,
                    "acknowledged_at": datetime.now().isoformat(),
                    "acknowledged_by": acknowledged_by,
                }
            }
        )
        return result.modified_count > 0

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
        if not self.db:
            return []

        query: dict[str, Any] = {}
        if level:
            query["level"] = level
        if acknowledged is not None:
            query["acknowledged"] = acknowledged
        if start_time or end_time:
            query["triggered_at"] = {}
            if start_time:
                query["triggered_at"]["$gte"] = start_time.isoformat()
            if end_time:
                query["triggered_at"]["$lte"] = end_time.isoformat()

        cursor = self.db.alerts.find(query).skip(offset).limit(limit).sort("triggered_at", -1)
        docs = await cursor.to_list(length=limit)

        result = []
        for doc in docs:
            doc.pop("_id", None)
            result.append(StoredAlert.from_dict(doc))
        return result

    # ==================== 报告操作 ====================

    async def save_report(self, report: StoredReport) -> bool:
        """保存报告"""
        if not self.db:
            return False
        try:
            report_dict = report.to_dict()
            await self.db.reports.update_one(
                {"id": report.id},
                {"$set": report_dict},
                upsert=True
            )
            return True
        except Exception as e:
            print(f"保存报告失败: {e}")
            return False

    async def get_report(self, report_id: str) -> Optional[StoredReport]:
        """获取报告"""
        if not self.db:
            return None
        doc = await self.db.reports.find_one({"id": report_id})
        if doc:
            doc.pop("_id", None)
            return StoredReport.from_dict(doc)
        return None

    async def get_report_by_date(self, report_type: str, date: str) -> Optional[StoredReport]:
        """根据日期获取报告"""
        if not self.db:
            return None
        doc = await self.db.reports.find_one({
            "report_type": report_type,
            "date": date
        })
        if doc:
            doc.pop("_id", None)
            return StoredReport.from_dict(doc)
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
        if not self.db:
            return []

        query: dict[str, Any] = {}
        if report_type:
            query["report_type"] = report_type
        if start_date or end_date:
            query["date"] = {}
            if start_date:
                query["date"]["$gte"] = start_date
            if end_date:
                query["date"]["$lte"] = end_date

        cursor = self.db.reports.find(query).skip(offset).limit(limit).sort("date", -1)
        docs = await cursor.to_list(length=limit)

        result = []
        for doc in docs:
            doc.pop("_id", None)
            result.append(StoredReport.from_dict(doc))
        return result

    # ==================== 统计操作 ====================

    async def get_sentiment_stats(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> dict[str, int]:
        """获取情感分布统计"""
        if not self.db:
            return {}

        match_stage: dict[str, Any] = {}
        if start_time or end_time:
            match_stage["collected_at"] = {}
            if start_time:
                match_stage["collected_at"]["$gte"] = start_time.isoformat()
            if end_time:
                match_stage["collected_at"]["$lte"] = end_time.isoformat()

        pipeline = []
        if match_stage:
            pipeline.append({"$match": match_stage})
        pipeline.append({
            "$group": {
                "_id": "$sentiment_label",
                "count": {"$sum": 1}
            }
        })

        result = {}
        async for doc in self.db.documents.aggregate(pipeline):
            label = doc["_id"] or "unknown"
            result[label] = doc["count"]

        return result

    async def get_keyword_stats(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """获取关键词统计"""
        if not self.db:
            return []

        match_stage: dict[str, Any] = {}
        if start_time or end_time:
            match_stage["collected_at"] = {}
            if start_time:
                match_stage["collected_at"]["$gte"] = start_time.isoformat()
            if end_time:
                match_stage["collected_at"]["$lte"] = end_time.isoformat()

        pipeline = []
        if match_stage:
            pipeline.append({"$match": match_stage})
        pipeline.append({"$unwind": "$keywords"})
        pipeline.append({
            "$group": {
                "_id": "$keywords",
                "count": {"$sum": 1}
            }
        })
        pipeline.append({"$sort": {"count": -1}})
        pipeline.append({"$limit": limit})

        result = []
        async for doc in self.db.documents.aggregate(pipeline):
            result.append({
                "keyword": doc["_id"],
                "count": doc["count"]
            })

        return result

    async def get_entity_stats(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """获取实体统计"""
        if not self.db:
            return []

        match_stage: dict[str, Any] = {}
        if start_time or end_time:
            match_stage["collected_at"] = {}
            if start_time:
                match_stage["collected_at"]["$gte"] = start_time.isoformat()
            if end_time:
                match_stage["collected_at"]["$lte"] = end_time.isoformat()

        pipeline = []
        if match_stage:
            pipeline.append({"$match": match_stage})
        pipeline.append({"$unwind": "$entities"})
        pipeline.append({
            "$group": {
                "_id": {
                    "text": "$entities.text",
                    "type": "$entities.type"
                },
                "count": {"$sum": 1}
            }
        })
        pipeline.append({"$sort": {"count": -1}})
        pipeline.append({"$limit": limit})

        result = []
        async for doc in self.db.documents.aggregate(pipeline):
            result.append({
                "text": doc["_id"]["text"],
                "type": doc["_id"]["type"],
                "count": doc["count"]
            })

        return result