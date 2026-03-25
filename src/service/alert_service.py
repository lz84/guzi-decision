"""
预警服务 - 实时预警系统
"""

from datetime import datetime
from typing import Any, Optional, Callable
import uuid
import re

from ..storage.base import BaseStorage
from ..storage.models import StoredAlert, AlertLevel, StoredDocument


class AlertRule:
    """预警规则"""

    def __init__(
        self,
        name: str,
        condition: Callable[[dict[str, Any]], bool],
        level: AlertLevel,
        message_template: str,
    ):
        self.name = name
        self.condition = condition
        self.level = level
        self.message_template = message_template

    def evaluate(self, data: dict[str, Any]) -> Optional[str]:
        """评估规则，返回消息或 None"""
        if self.condition(data):
            return self.message_template.format(**data)
        return None


class AlertService:
    """预警服务"""

    def __init__(self, storage: BaseStorage):
        self.storage = storage
        self._rules: list[AlertRule] = []
        self._webhooks: list[str] = []
        self._notification_handlers: list[Callable[[StoredAlert], None]] = []

    async def initialize(self) -> None:
        """初始化预警规则"""
        # 默认规则
        self._add_default_rules()

    def _add_default_rules(self) -> None:
        """添加默认预警规则"""
        # 极度负面情感预警
        self.add_rule(AlertRule(
            name="极度负面情感",
            condition=lambda d: d.get("sentiment_score") is not None and d["sentiment_score"] < -0.8,
            level=AlertLevel.HIGH,
            message_template="检测到极度负面内容: {content_preview}",
        ))

        # 关键词预警
        critical_keywords = ["暴跌", "崩盘", "诈骗", "跑路", "爆雷"]
        self.add_rule(AlertRule(
            name="关键风险词",
            condition=lambda d: any(kw in d.get("content", "") for kw in critical_keywords),
            level=AlertLevel.CRITICAL,
            message_template="检测到关键风险词汇: {content_preview}",
        ))

        # 高影响力事件
        self.add_rule(AlertRule(
            name="高影响力事件",
            condition=lambda d: d.get("impact_score", 0) > 0.8,
            level=AlertLevel.HIGH,
            message_template="检测到高影响力事件: {title}",
        ))

    def add_rule(self, rule: AlertRule) -> None:
        """添加预警规则"""
        self._rules.append(rule)

    def add_webhook(self, url: str) -> None:
        """添加 Webhook 通知地址"""
        self._webhooks.append(url)

    def add_notification_handler(self, handler: Callable[[StoredAlert], None]) -> None:
        """添加通知处理器"""
        self._notification_handlers.append(handler)

    async def check_document(self, document: StoredDocument) -> list[StoredAlert]:
        """检查文档并生成预警"""
        alerts = []

        # 准备评估数据
        data = {
            "id": document.id,
            "source": document.source,
            "content": document.content,
            "content_preview": document.content[:200] + "..." if len(document.content) > 200 else document.content,
            "title": document.title,
            "sentiment_score": document.sentiment_score,
            "sentiment_label": document.sentiment_label,
            "entities": document.entities,
            "keywords": document.keywords,
            "impact_score": document.metadata.get("impact_score", 0),
        }

        # 评估所有规则
        for rule in self._rules:
            message = rule.evaluate(data)
            if message:
                alert = StoredAlert(
                    id=str(uuid.uuid4()),
                    level=rule.level,
                    title=rule.name,
                    message=message,
                    source=document.source,
                    document_id=document.id,
                    keywords=document.keywords,
                    sentiment_score=document.sentiment_score,
                    triggered_at=datetime.now(),
                )

                # 保存预警
                await self.storage.save_alert(alert)
                alerts.append(alert)

                # 发送通知
                await self._send_notification(alert)

        return alerts

    async def check_batch(self, documents: list[StoredDocument]) -> list[StoredAlert]:
        """批量检查文档"""
        all_alerts = []
        for doc in documents:
            alerts = await self.check_document(doc)
            all_alerts.extend(alerts)
        return all_alerts

    async def check_recent(self, hours: int = 1) -> list[StoredAlert]:
        """检查最近 N 小时的文档"""
        start_time = datetime.now() - __import__('datetime').timedelta(hours=hours)
        docs = await self.storage.query_documents(
            start_time=start_time,
            limit=1000,
        )
        return await self.check_batch(docs)

    async def _send_notification(self, alert: StoredAlert) -> None:
        """发送预警通知"""
        import aiohttp

        # 调用自定义处理器
        for handler in self._notification_handlers:
            try:
                handler(alert)
            except Exception as e:
                print(f"通知处理器执行失败: {e}")

        # 发送 Webhook
        for webhook_url in self._webhooks:
            try:
                async with aiohttp.ClientSession() as session:
                    await session.post(
                        webhook_url,
                        json=alert.to_dict(),
                        timeout=aiohttp.ClientTimeout(total=5),
                    )
            except Exception as e:
                print(f"Webhook 发送失败 {webhook_url}: {e}")

        # 标记已发送
        alert.notification_sent = True
        alert.notification_channels = self._webhooks.copy()
        await self.storage.save_alert(alert)

    async def get_active_alerts(self, limit: int = 100) -> list[StoredAlert]:
        """获取未确认的预警"""
        return await self.storage.query_alerts(
            acknowledged=False,
            limit=limit,
        )

    async def get_alerts_by_level(self, level: str, limit: int = 50) -> list[StoredAlert]:
        """按级别获取预警"""
        return await self.storage.query_alerts(
            level=level,
            limit=limit,
        )

    async def acknowledge_alert(self, alert_id: str, acknowledged_by: Optional[str] = None) -> bool:
        """确认预警"""
        return await self.storage.acknowledge_alert(alert_id, acknowledged_by)

    async def get_alert_stats(self) -> dict[str, Any]:
        """获取预警统计"""
        all_alerts = await self.storage.query_alerts(limit=10000)

        stats = {
            "total": len(all_alerts),
            "by_level": {},
            "by_acknowledged": {
                "acknowledged": 0,
                "pending": 0,
            },
        }

        for alert in all_alerts:
            level = alert.level.value
            stats["by_level"][level] = stats["by_level"].get(level, 0) + 1

            if alert.acknowledged:
                stats["by_acknowledged"]["acknowledged"] += 1
            else:
                stats["by_acknowledged"]["pending"] += 1

        return stats

    async def create_custom_alert(
        self,
        level: AlertLevel,
        title: str,
        message: str,
        source: Optional[str] = None,
        document_id: Optional[str] = None,
        keywords: Optional[list[str]] = None,
    ) -> StoredAlert:
        """创建自定义预警"""
        alert = StoredAlert(
            id=str(uuid.uuid4()),
            level=level,
            title=title,
            message=message,
            source=source,
            document_id=document_id,
            keywords=keywords or [],
            triggered_at=datetime.now(),
        )

        await self.storage.save_alert(alert)
        await self._send_notification(alert)

        return alert


# 预定义的预警规则工厂
class AlertRuleFactory:
    """预警规则工厂"""

    @staticmethod
    def sentiment_threshold(
        threshold: float = -0.5,
        level: AlertLevel = AlertLevel.MEDIUM,
    ) -> AlertRule:
        """情感阈值预警"""
        return AlertRule(
            name=f"情感低于{threshold}",
            condition=lambda d: d.get("sentiment_score") is not None and d["sentiment_score"] < threshold,
            level=level,
            message_template="情感分数低于阈值: {sentiment_score}",
        )

    @staticmethod
    def keyword_match(
        keywords: list[str],
        level: AlertLevel = AlertLevel.MEDIUM,
    ) -> AlertRule:
        """关键词匹配预警"""
        pattern = re.compile("|".join(keywords), re.IGNORECASE)
        return AlertRule(
            name=f"关键词匹配",
            condition=lambda d: bool(pattern.search(d.get("content", ""))),
            level=level,
            message_template="匹配到关键词: {content_preview}",
        )

    @staticmethod
    def entity_mention(
        entity_name: str,
        level: AlertLevel = AlertLevel.MEDIUM,
    ) -> AlertRule:
        """实体提及预警"""
        return AlertRule(
            name=f"实体提及: {entity_name}",
            condition=lambda d: any(
                e.get("text", "").lower() == entity_name.lower()
                for e in d.get("entities", [])
            ),
            level=level,
            message_template=f"检测到实体 {entity_name}: {{title}}",
        )