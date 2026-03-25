"""
每日复盘任务脚本
由 OpenClaw cron 定时触发
"""

import sys
import os
from datetime import datetime
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

from virtual_trading.review_system import (
    auto_review_pending_trades,
    get_review_dashboard,
    IntelligenceSourceScoring
)

def generate_daily_report():
    """生成每日复盘报告"""
    now = datetime.now()
    report_date = now.strftime("%Y-%m-%d")
    
    # 自动复盘待处理交易
    review_result = auto_review_pending_trades()
    print(f"自动复盘: {review_result}")
    
    # 获取看板数据
    dashboard = get_review_dashboard()
    performance = dashboard.get("performance", {})
    source_ranking = dashboard.get("source_ranking", [])
    insights = dashboard.get("insights", [])
    
    # 生成 Markdown 报告
    report = f"""# 每日复盘报告

**日期**: {report_date}

## 总体表现

| 指标 | 数值 |
|------|------|
| 总复盘数 | {performance.get("total_reviews", 0)} |
| 盈利次数 | {performance.get("wins", 0)} |
| 亏损次数 | {performance.get("losses", 0)} |
| 胜率 | {performance.get("win_rate", 0):.2f}% |
| 总收益 | ${performance.get("total_profit", 0):.2f} |
| 平均收益 | ${performance.get("avg_profit", 0):.2f} |
| 平均准确度 | {performance.get("avg_accuracy", 0):.4f} |
| 方向准确率 | {performance.get("direction_accuracy", 0):.2f}% |

## 情报源排名

| 排名 | 情报源 | 准确率 | 收益 | 权重 |
|------|--------|--------|------|------|
"""
    
    for i, source in enumerate(source_ranking[:10], 1):
        report += f"| {i} | {source.get('source_name', 'Unknown')} | {source.get('accuracy_rate', 0):.2f}% | ${source.get('total_profit', 0):.2f} | {source.get('weight', 1):.4f} |\n"
    
    report += "\n## 改进建议\n\n"
    for insight in insights:
        report += f"- {insight}\n"
    
    report += f"\n---\n\n*报告生成时间: {now.strftime('%Y-%m-%d %H:%M:%S')}*\n"
    
    # 保存报告
    report_dir = Path(__file__).parent / "reports"
    report_dir.mkdir(exist_ok=True)
    report_path = report_dir / f"review_{report_date}.md"
    
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    
    print(f"报告已保存: {report_path}")
    
    # 更新情报源评分
    scoring = IntelligenceSourceScoring()
    scoring.record_daily_stats()
    print("情报源评分已更新")
    
    return {
        "report_path": str(report_path),
        "reviewed_count": review_result.get("reviewed_count", 0)
    }

if __name__ == "__main__":
    result = generate_daily_report()
    print(f"每日复盘完成: {result}")
