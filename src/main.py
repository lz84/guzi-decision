"""
谷子情报分析系统 - 主入口
"""
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from pathlib import Path

from .storage import MongoStorage, FileStorage
from .service import CollectorService, AnalyzerService, ProcessorService, AlertService, ReportService
from .virtual_trading import router as trading_router


# 存储实例
storage = None
collector_service = None
analyzer_service = None
processor_service = None
alert_service = None
report_service = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    global storage, collector_service, analyzer_service, processor_service, alert_service, report_service

    # 初始化存储（优先使用 MongoDB，回退到文件存储）
    try:
        storage = MongoStorage()
        await storage.connect()
        print("MongoDB 存储已连接")
    except Exception as e:
        print(f"MongoDB 连接失败，使用文件存储: {e}")
        storage = FileStorage()
        await storage.connect()

    # 初始化服务
    collector_service = CollectorService(storage)
    await collector_service.initialize()

    analyzer_service = AnalyzerService(storage)
    await analyzer_service.initialize()

    processor_service = ProcessorService(storage)
    await processor_service.initialize()

    alert_service = AlertService(storage)
    await alert_service.initialize()

    report_service = ReportService(storage)
    await report_service.initialize()

    yield

    # 清理
    if storage:
        await storage.disconnect()


app = FastAPI(
    title="谷子情报分析系统",
    description="面向 Polymarket 预测市场的舆情情报收集与分析平台",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册虚拟交易路由
app.include_router(trading_router)


# ==================== 看板页面 ====================

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard():
    """情报虚拟交易看板页面"""
    dashboard_file = Path(__file__).parent.parent / "static" / "dashboard.html"
    if dashboard_file.exists():
        return HTMLResponse(content=dashboard_file.read_text(encoding='utf-8'))
    else:
        return HTMLResponse(content="<h1>Dashboard not found</h1><p>Please ensure static/dashboard.html exists.</p>")


@app.get("/api/dashboard/status")
async def dashboard_status():
    """看板状态汇总 API"""
    from .virtual_trading import get_trading_statistics, get_trading_history
    from .virtual_trading.intelligence_integration import IntelligenceTradingIntegration
    
    try:
        # 获取交易统计
        stats = get_trading_statistics()
        
        # 获取情报统计
        intel_manager = IntelligenceTradingIntegration()
        intel_stats = intel_manager.get_intelligence_statistics()
        
        # 获取最近交易
        recent_trades = get_trading_history(10)
        
        return {
            "trading": stats,
            "intelligence": intel_stats,
            "recent_trades": recent_trades
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/dashboard/performance")
async def performance_dashboard():
    """绩效看板 API - 增强版"""
    from .virtual_trading import get_trading_statistics, get_trading_history
    from .virtual_trading.intelligence_integration import IntelligenceTradingIntegration
    
    try:
        manager = IntelligenceTradingIntegration()
        
        # 获取交易统计
        trading_stats = get_trading_statistics()
        
        # 获取增强统计
        enhanced_stats = manager.get_enhanced_statistics()
        
        # 获取最近交易
        recent_trades = get_trading_history(10)
        
        # 获取情报源排名
        source_ranking = manager.get_best_sources(3)
        
        return {
            'trading': trading_stats,
            'enhanced': enhanced_stats,
            'recent_trades': recent_trades,
            'source_ranking': source_ranking,
            'generated_at': datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 请求/响应模型 ====================

class CollectRequest(BaseModel):
    """采集请求"""
    source: str = Field(..., description="数据源: twitter, reddit, news, tavily")
    keywords: list[str] = Field(..., description="关键词列表")
    limit: int = Field(default=100, ge=1, le=1000, description="采集数量限制")
    time_range: Optional[str] = Field(default=None, description="时间范围: 1h, 24h, 7d")


class AnalyzeRequest(BaseModel):
    """分析请求"""
    text: str = Field(..., description="待分析文本")
    language: Optional[str] = Field(default=None, description="语言代码")


class DocumentResponse(BaseModel):
    """文档响应"""
    id: str
    source: str
    title: Optional[str] = None
    author: Optional[str] = None
    content: str
    sentiment_label: Optional[str] = None
    sentiment_score: Optional[float] = None
    collected_at: Optional[str] = None
    url: Optional[str] = None


class AnalysisResponse(BaseModel):
    """分析响应"""
    id: str
    document_id: str
    sentiment_label: Optional[str] = None
    sentiment_score: Optional[float] = None
    confidence: float
    entities: list[dict[str, Any]] = []
    keywords: list[str] = []


class AlertResponse(BaseModel):
    """预警响应"""
    id: str
    level: str
    title: str
    message: str
    triggered_at: str
    acknowledged: bool


class ReportResponse(BaseModel):
    """报告响应"""
    id: str
    report_type: str
    title: str
    date: str
    summary: Optional[str] = None
    total_documents: int


# ==================== 基础路由 ====================

@app.get("/")
async def root():
    """根路由"""
    return {"message": "谷子情报分析系统运行中", "version": "0.1.0"}


@app.get("/health")
async def health():
    """健康检查"""
    db_health = await storage.health_check() if storage else False
    return {
        "status": "healthy" if db_health else "degraded",
        "storage": "connected" if db_health else "disconnected",
    }


# ==================== 数据采集 API ====================

@app.post("/api/collect", response_model=dict[str, Any])
async def collect_data(request: CollectRequest):
    """
    触发数据采集任务

    支持的数据源:
    - twitter: Twitter/X 数据
    - reddit: Reddit 讨论
    - news: 新闻数据
    - tavily: Tavily 搜索
    """
    if not collector_service:
        raise HTTPException(status_code=503, detail="采集服务未初始化")

    task = await collector_service.collect(
        source=request.source,
        keywords=request.keywords,
        limit=request.limit,
        time_range=request.time_range,
    )

    return {
        "task_id": task.task_id,
        "status": task.status.value,
        "result_count": task.result_count,
        "error": task.error_message,
    }


@app.get("/api/collectors", response_model=dict[str, Any])
async def get_collectors():
    """获取采集器状态"""
    if not collector_service:
        raise HTTPException(status_code=503, detail="采集服务未初始化")
    return await collector_service.get_collector_status()


# ==================== 数据分析 API ====================

@app.post("/api/analyze", response_model=AnalysisResponse)
async def analyze_text(request: AnalyzeRequest):
    """
    分析单条文本

    返回情感分析、实体识别、关键词提取结果
    """
    if not analyzer_service:
        raise HTTPException(status_code=503, detail="分析服务未初始化")

    result = await analyzer_service.analyze_text(request.text)

    return AnalysisResponse(
        id="inline",
        document_id="",
        sentiment_label=result.sentiment.label.value if result.sentiment else None,
        sentiment_score=result.sentiment.score if result.sentiment else None,
        confidence=result.sentiment.confidence if result.sentiment else 0,
        entities=[e.to_dict() for e in result.entities],
        keywords=result.keywords,
    )


@app.post("/api/analyze/{document_id}", response_model=AnalysisResponse)
async def analyze_document(document_id: str):
    """分析指定文档"""
    if not analyzer_service:
        raise HTTPException(status_code=503, detail="分析服务未初始化")

    analysis = await analyzer_service.analyze_document(document_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="文档不存在")

    return AnalysisResponse(
        id=analysis.id,
        document_id=analysis.document_id,
        sentiment_label=analysis.sentiment_label,
        sentiment_score=analysis.sentiment_score,
        confidence=analysis.confidence,
        entities=analysis.entities,
        keywords=analysis.keywords,
    )


@app.post("/api/analyze/batch", response_model=list[AnalysisResponse])
async def batch_analyze(document_ids: list[str] = Query(...)):
    """批量分析文档"""
    if not analyzer_service:
        raise HTTPException(status_code=503, detail="分析服务未初始化")

    results = await analyzer_service.batch_analyze(document_ids)
    return [
        AnalysisResponse(
            id=a.id,
            document_id=a.document_id,
            sentiment_label=a.sentiment_label,
            sentiment_score=a.sentiment_score,
            confidence=a.confidence,
            entities=a.entities,
            keywords=a.keywords,
        )
        for a in results
    ]


# ==================== 句子查询 API ====================

@app.get("/api/sentences", response_model=list[DocumentResponse])
async def query_sentences(
    source: Optional[str] = Query(None, description="数据源过滤"),
    sentiment: Optional[str] = Query(None, description="情感过滤: positive, negative, neutral"),
    keyword: Optional[str] = Query(None, description="关键词过滤"),
    start_date: Optional[str] = Query(None, description="开始日期 (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="结束日期 (YYYY-MM-DD)"),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    """
    查询句子/文档列表

    支持按来源、情感、关键词、时间范围过滤
    """
    if not storage:
        raise HTTPException(status_code=503, detail="存储服务未初始化")

    start_time = datetime.fromisoformat(start_date) if start_date else None
    end_time = datetime.fromisoformat(end_date) + timedelta(days=1) if end_date else None

    keywords = [keyword] if keyword else None

    docs = await storage.query_documents(
        source=source,
        sentiment_label=sentiment,
        start_time=start_time,
        end_time=end_time,
        keywords=keywords,
        limit=limit,
        offset=offset,
    )

    return [
        DocumentResponse(
            id=d.id,
            source=d.source,
            title=d.title,
            author=d.author,
            content=d.content[:500] + "..." if len(d.content) > 500 else d.content,
            sentiment_label=d.sentiment_label,
            sentiment_score=d.sentiment_score,
            collected_at=d.collected_at.isoformat() if d.collected_at else None,
            url=d.url,
        )
        for d in docs
    ]


@app.get("/api/sentences/{document_id}", response_model=DocumentResponse)
async def get_sentence(document_id: str):
    """获取单个句子/文档详情"""
    if not storage:
        raise HTTPException(status_code=503, detail="存储服务未初始化")

    doc = await storage.get_document(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")

    return DocumentResponse(
        id=doc.id,
        source=doc.source,
        title=doc.title,
        author=doc.author,
        content=doc.content,
        sentiment_label=doc.sentiment_label,
        sentiment_score=doc.sentiment_score,
        collected_at=doc.collected_at.isoformat() if doc.collected_at else None,
        url=doc.url,
    )


# ==================== 报告 API ====================

@app.get("/api/reports", response_model=list[ReportResponse])
async def get_reports(
    report_type: Optional[str] = Query(None, description="报告类型: daily, weekly"),
    start_date: Optional[str] = Query(None, description="开始日期"),
    end_date: Optional[str] = Query(None, description="结束日期"),
    limit: int = Query(default=30, ge=1, le=100),
):
    """获取报告列表"""
    if not storage:
        raise HTTPException(status_code=503, detail="存储服务未初始化")

    reports = await storage.query_reports(
        report_type=report_type,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
    )

    return [
        ReportResponse(
            id=r.id,
            report_type=r.report_type.value,
            title=r.title,
            date=r.date,
            summary=r.summary,
            total_documents=r.total_documents,
        )
        for r in reports
    ]


@app.get("/api/reports/{report_id}", response_model=dict[str, Any])
async def get_report(report_id: str):
    """获取报告详情"""
    if not storage:
        raise HTTPException(status_code=503, detail="存储服务未初始化")

    report = await storage.get_report(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="报告不存在")

    return report.to_dict()


@app.post("/api/reports/daily", response_model=ReportResponse)
async def generate_daily_report(
    date: Optional[str] = Query(None, description="日期 (YYYY-MM-DD)"),
):
    """生成日报"""
    if not report_service:
        raise HTTPException(status_code=503, detail="报告服务未初始化")

    report = await report_service.generate_daily_report(date)

    return ReportResponse(
        id=report.id,
        report_type=report.report_type.value,
        title=report.title,
        date=report.date,
        summary=report.summary,
        total_documents=report.total_documents,
    )


@app.post("/api/reports/weekly", response_model=ReportResponse)
async def generate_weekly_report(
    start_date: Optional[str] = Query(None, description="周起始日期 (YYYY-MM-DD)"),
):
    """生成周报"""
    if not report_service:
        raise HTTPException(status_code=503, detail="报告服务未初始化")

    report = await report_service.generate_weekly_report(start_date)

    return ReportResponse(
        id=report.id,
        report_type=report.report_type.value,
        title=report.title,
        date=report.date,
        summary=report.summary,
        total_documents=report.total_documents,
    )


@app.get("/api/reports/latest/daily", response_model=ReportResponse)
async def get_latest_daily_report():
    """获取最新日报"""
    if not report_service:
        raise HTTPException(status_code=503, detail="报告服务未初始化")

    report = await report_service.get_latest_daily_report()
    if not report:
        raise HTTPException(status_code=404, detail="暂无日报")

    return ReportResponse(
        id=report.id,
        report_type=report.report_type.value,
        title=report.title,
        date=report.date,
        summary=report.summary,
        total_documents=report.total_documents,
    )


# ==================== 统计 API ====================

@app.get("/api/stats/sentiment", response_model=dict[str, Any])
async def get_sentiment_stats(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
):
    """获取情感分布统计"""
    if not storage:
        raise HTTPException(status_code=503, detail="存储服务未初始化")

    start_time = datetime.fromisoformat(start_date) if start_date else None
    end_time = datetime.fromisoformat(end_date) + timedelta(days=1) if end_date else None

    stats = await storage.get_sentiment_stats(start_time, end_time)
    total = sum(stats.values())

    return {
        "distribution": stats,
        "total": total,
        "percentages": {
            k: round(v / total * 100, 2) if total > 0 else 0
            for k, v in stats.items()
        }
    }


@app.get("/api/stats/keywords", response_model=list[dict[str, Any]])
async def get_keyword_stats(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    limit: int = Query(default=20, ge=1, le=100),
):
    """获取热门关键词"""
    if not storage:
        raise HTTPException(status_code=503, detail="存储服务未初始化")

    start_time = datetime.fromisoformat(start_date) if start_date else None
    end_time = datetime.fromisoformat(end_date) + timedelta(days=1) if end_date else None

    return await storage.get_keyword_stats(start_time, end_time, limit)


@app.get("/api/stats/entities", response_model=list[dict[str, Any]])
async def get_entity_stats(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    limit: int = Query(default=20, ge=1, le=100),
):
    """获取热门实体"""
    if not storage:
        raise HTTPException(status_code=503, detail="存储服务未初始化")

    start_time = datetime.fromisoformat(start_date) if start_date else None
    end_time = datetime.fromisoformat(end_date) + timedelta(days=1) if end_date else None

    return await storage.get_entity_stats(start_time, end_time, limit)


# ==================== 预警 API ====================

@app.get("/api/alerts", response_model=list[AlertResponse])
async def get_alerts(
    level: Optional[str] = Query(None, description="预警级别: critical, high, medium, low"),
    acknowledged: Optional[bool] = Query(None, description="是否已确认"),
    limit: int = Query(default=50, ge=1, le=200),
):
    """获取预警列表"""
    if not storage:
        raise HTTPException(status_code=503, detail="存储服务未初始化")

    alerts = await storage.query_alerts(
        level=level,
        acknowledged=acknowledged,
        limit=limit,
    )

    return [
        AlertResponse(
            id=a.id,
            level=a.level.value,
            title=a.title,
            message=a.message,
            triggered_at=a.triggered_at.isoformat() if a.triggered_at else "",
            acknowledged=a.acknowledged,
        )
        for a in alerts
    ]


@app.post("/api/alerts/{alert_id}/acknowledge", response_model=dict[str, Any])
async def acknowledge_alert(alert_id: str):
    """确认预警"""
    if not storage:
        raise HTTPException(status_code=503, detail="存储服务未初始化")

    success = await storage.acknowledge_alert(alert_id)
    if not success:
        raise HTTPException(status_code=404, detail="预警不存在")

    return {"success": True, "alert_id": alert_id}


@app.post("/api/alerts/check", response_model=list[AlertResponse])
async def check_alerts(
    hours: int = Query(default=1, ge=1, le=24, description="检查最近 N 小时的数据"),
):
    """检查最近数据并生成预警"""
    if not alert_service:
        raise HTTPException(status_code=503, detail="预警服务未初始化")

    alerts = await alert_service.check_recent(hours)

    return [
        AlertResponse(
            id=a.id,
            level=a.level.value,
            title=a.title,
            message=a.message,
            triggered_at=a.triggered_at.isoformat() if a.triggered_at else "",
            acknowledged=a.acknowledged,
        )
        for a in alerts
    ]


@app.get("/api/alerts/stats", response_model=dict[str, Any])
async def get_alert_stats():
    """获取预警统计"""
    if not alert_service:
        raise HTTPException(status_code=503, detail="预警服务未初始化")

    return await alert_service.get_alert_stats()


def main():
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()