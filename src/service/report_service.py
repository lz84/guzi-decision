"""
报告服务 - 日报生成服务
"""

from datetime import datetime, timedelta
from typing import Any, Optional
import uuid

from ..storage.base import BaseStorage
from ..storage.models import StoredReport, StoredDocument, ReportType, StoredAlert


class ReportService:
    """报告服务"""

    def __init__(self, storage: BaseStorage):
        self.storage = storage

    async def initialize(self) -> None:
        """初始化服务"""
        pass

    async def generate_daily_report(self, date: Optional[str] = None) -> StoredReport:
        """生成日报"""
        # 解析日期
        if date:
            report_date = datetime.fromisoformat(date)
        else:
            report_date = datetime.now()

        date_str = report_date.strftime("%Y-%m-%d")

        # 检查是否已存在
        existing = await self.storage.get_report_by_date("daily", date_str)
        if existing:
            return existing

        # 获取当天数据
        start_time = report_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_time = start_time + timedelta(days=1)

        docs = await self.storage.query_documents(
            start_time=start_time,
            end_time=end_time,
            limit=10000,
        )

        alerts = await self.storage.query_alerts(
            start_time=start_time,
            end_time=end_time,
            limit=1000,
        )

        # 统计数据
        sentiment_stats = await self.storage.get_sentiment_stats(start_time, end_time)
        keyword_stats = await self.storage.get_keyword_stats(start_time, end_time, limit=20)
        entity_stats = await self.storage.get_entity_stats(start_time, end_time, limit=20)

        # 生成报告内容
        content = self._generate_markdown_report(
            date_str=date_str,
            docs=docs,
            alerts=alerts,
            sentiment_stats=sentiment_stats,
            keyword_stats=keyword_stats,
            entity_stats=entity_stats,
        )

        # 生成摘要
        summary = self._generate_summary(docs, sentiment_stats, alerts)

        # 创建报告
        report = StoredReport(
            id=str(uuid.uuid4()),
            report_type=ReportType.DAILY,
            title=f"舆情日报 - {date_str}",
            content=content,
            summary=summary,
            date=date_str,
            total_documents=len(docs),
            sentiment_distribution=sentiment_stats,
            top_keywords=[k["keyword"] for k in keyword_stats[:10]],
            top_entities=[e["text"] for e in entity_stats[:10]],
            alerts_count=len(alerts),
            generated_at=datetime.now(),
        )

        await self.storage.save_report(report)
        return report

    async def generate_weekly_report(self, start_date: Optional[str] = None) -> StoredReport:
        """生成周报"""
        if start_date:
            report_start = datetime.fromisoformat(start_date)
        else:
            # 本周一
            today = datetime.now()
            report_start = today - timedelta(days=today.weekday())

        report_start = report_start.replace(hour=0, minute=0, second=0, microsecond=0)
        report_end = report_start + timedelta(days=7)
        date_str = report_start.strftime("%Y-%m-%d")

        # 获取一周数据
        docs = await self.storage.query_documents(
            start_time=report_start,
            end_time=report_end,
            limit=50000,
        )

        alerts = await self.storage.query_alerts(
            start_time=report_start,
            end_time=report_end,
            limit=5000,
        )

        # 统计
        sentiment_stats = await self.storage.get_sentiment_stats(report_start, report_end)
        keyword_stats = await self.storage.get_keyword_stats(report_start, report_end, limit=30)
        entity_stats = await self.storage.get_entity_stats(report_start, report_end, limit=30)

        # 每日趋势
        daily_trend = await self._get_daily_trend(report_start, report_end)

        # 生成报告
        content = self._generate_weekly_markdown(
            date_str=date_str,
            docs=docs,
            alerts=alerts,
            sentiment_stats=sentiment_stats,
            keyword_stats=keyword_stats,
            entity_stats=entity_stats,
            daily_trend=daily_trend,
        )

        summary = self._generate_summary(docs, sentiment_stats, alerts)

        report = StoredReport(
            id=str(uuid.uuid4()),
            report_type=ReportType.WEEKLY,
            title=f"舆情周报 - {date_str}",
            content=content,
            summary=summary,
            date=date_str,
            total_documents=len(docs),
            sentiment_distribution=sentiment_stats,
            top_keywords=[k["keyword"] for k in keyword_stats[:10]],
            top_entities=[e["text"] for e in entity_stats[:10]],
            alerts_count=len(alerts),
            generated_at=datetime.now(),
        )

        await self.storage.save_report(report)
        return report

    def _generate_markdown_report(
        self,
        date_str: str,
        docs: list[StoredDocument],
        alerts: list[StoredAlert],
        sentiment_stats: dict[str, int],
        keyword_stats: list[dict[str, Any]],
        entity_stats: list[dict[str, Any]],
    ) -> str:
        """生成 Markdown 格式报告"""
        lines = [
            f"# 舆情日报 - {date_str}",
            "",
            "## 概览",
            "",
            f"- **采集文档数**: {len(docs)}",
            f"- **预警数量**: {len(alerts)}",
            "",
            "## 情感分布",
            "",
        ]

        total = sum(sentiment_stats.values())
        for label, count in sentiment_stats.items():
            pct = round(count / total * 100, 1) if total > 0 else 0
            lines.append(f"- **{label}**: {count} ({pct}%)")

        lines.extend([
            "",
            "## 热门关键词",
            "",
            "| 关键词 | 出现次数 |",
            "|--------|----------|",
        ])
        for kw in keyword_stats[:10]:
            lines.append(f"| {kw['keyword']} | {kw['count']} |")

        lines.extend([
            "",
            "## 热门实体",
            "",
            "| 实体 | 类型 | 出现次数 |",
            "|------|------|----------|",
        ])
        for ent in entity_stats[:10]:
            lines.append(f"| {ent['text']} | {ent['type']} | {ent['count']} |")

        # 预警列表
        if alerts:
            lines.extend([
                "",
                "## 预警列表",
                "",
            ])
            for alert in alerts[:20]:
                lines.append(f"- **[{alert.level.value}]** {alert.title}: {alert.message}")

        # 典型内容
        lines.extend([
            "",
            "## 典型内容",
            "",
        ])

        # 负面内容
        negative_docs = [d for d in docs if d.sentiment_score and d.sentiment_score < -0.3][:3]
        if negative_docs:
            lines.append("### 负面内容")
            for doc in negative_docs:
                lines.append(f"- [{doc.source}] {doc.title or doc.content[:100]}...")

        # 正面内容
        positive_docs = [d for d in docs if d.sentiment_score and d.sentiment_score > 0.3][:3]
        if positive_docs:
            lines.append("")
            lines.append("### 正面内容")
            for doc in positive_docs:
                lines.append(f"- [{doc.source}] {doc.title or doc.content[:100]}...")

        return "\n".join(lines)

    def _generate_weekly_markdown(
        self,
        date_str: str,
        docs: list[StoredDocument],
        alerts: list[StoredAlert],
        sentiment_stats: dict[str, int],
        keyword_stats: list[dict[str, Any]],
        entity_stats: list[dict[str, Any]],
        daily_trend: list[dict[str, Any]],
    ) -> str:
        """生成周报 Markdown"""
        lines = [
            f"# 舆情周报 - {date_str}",
            "",
            "## 周度概览",
            "",
            f"- **本周采集文档数**: {len(docs)}",
            f"- **预警数量**: {len(alerts)}",
            f"- **日均文档数**: {round(len(docs) / 7, 1)}",
            "",
            "## 每日趋势",
            "",
            "| 日期 | 文档数 | 正面 | 负面 | 中性 |",
            "|------|--------|------|------|------|",
        ]

        for day in daily_trend:
            lines.append(
                f"| {day['date']} | {day['total']} | {day.get('positive', 0)} | {day.get('negative', 0)} | {day.get('neutral', 0)} |"
            )

        lines.extend([
            "",
            "## 情感分布",
            "",
        ])

        total = sum(sentiment_stats.values())
        for label, count in sentiment_stats.items():
            pct = round(count / total * 100, 1) if total > 0 else 0
            lines.append(f"- **{label}**: {count} ({pct}%)")

        lines.extend([
            "",
            "## 热门关键词 TOP 20",
            "",
            "| 关键词 | 出现次数 |",
            "|--------|----------|",
        ])
        for kw in keyword_stats[:20]:
            lines.append(f"| {kw['keyword']} | {kw['count']} |")

        lines.extend([
            "",
            "## 热门实体 TOP 20",
            "",
            "| 实体 | 类型 | 出现次数 |",
            "|------|------|----------|",
        ])
        for ent in entity_stats[:20]:
            lines.append(f"| {ent['text']} | {ent['type']} | {ent['count']} |")

        # 预警汇总
        if alerts:
            # 按级别统计
            level_counts = {}
            for alert in alerts:
                level = alert.level.value
                level_counts[level] = level_counts.get(level, 0) + 1

            lines.extend([
                "",
                "## 预警汇总",
                "",
            ])
            for level, count in sorted(level_counts.items(), key=lambda x: -x[1]):
                lines.append(f"- **{level}**: {count}")

        return "\n".join(lines)

    def _generate_summary(
        self,
        docs: list[StoredDocument],
        sentiment_stats: dict[str, int],
        alerts: list[StoredAlert],
    ) -> str:
        """生成报告摘要"""
        total = len(docs)
        if total == 0:
            return "今日无采集数据。"

        total_sentiment = sum(sentiment_stats.values())
        positive_ratio = sentiment_stats.get("positive", 0) / total_sentiment if total_sentiment > 0 else 0
        negative_ratio = sentiment_stats.get("negative", 0) / total_sentiment if total_sentiment > 0 else 0

        summary_parts = [
            f"共采集 {total} 条文档",
        ]

        if positive_ratio > 0.5:
            summary_parts.append("整体情感偏向正面")
        elif negative_ratio > 0.5:
            summary_parts.append("整体情感偏向负面")
        else:
            summary_parts.append("整体情感相对平衡")

        if alerts:
            unacknowledged = sum(1 for a in alerts if not a.acknowledged)
            if unacknowledged > 0:
                summary_parts.append(f"有 {unacknowledged} 条待处理预警")

        return "，".join(summary_parts) + "。"

    async def _get_daily_trend(
        self,
        start_time: datetime,
        end_time: datetime,
    ) -> list[dict[str, Any]]:
        """获取每日趋势"""
        trend = []
        current = start_time

        while current < end_time:
            next_day = current + timedelta(days=1)
            day_docs = await self.storage.query_documents(
                start_time=current,
                end_time=next_day,
                limit=10000,
            )

            # 按情感统计
            sentiment_counts = {"positive": 0, "negative": 0, "neutral": 0}
            for doc in day_docs:
                if doc.sentiment_label in sentiment_counts:
                    sentiment_counts[doc.sentiment_label] += 1

            trend.append({
                "date": current.strftime("%Y-%m-%d"),
                "total": len(day_docs),
                **sentiment_counts,
            })

            current = next_day

        return trend

    async def get_report(self, report_id: str) -> Optional[StoredReport]:
        """获取报告"""
        return await self.storage.get_report(report_id)

    async def get_latest_daily_report(self) -> Optional[StoredReport]:
        """获取最新日报"""
        reports = await self.storage.query_reports(
            report_type="daily",
            limit=1,
        )
        return reports[0] if reports else None

    async def list_reports(
        self,
        report_type: Optional[str] = None,
        limit: int = 30,
    ) -> list[StoredReport]:
        """列出报告"""
        return await self.storage.query_reports(
            report_type=report_type,
            limit=limit,
        )