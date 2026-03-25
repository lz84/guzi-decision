"""
虚拟交易模块 FastAPI 路由
"""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
import json

# 导入虚拟交易模块
from . import (
    get_account_info, place_virtual_bet, record_trade_result,
    get_trading_statistics, get_trading_history, reset_trading_account,
    add_trading_funds, get_pnl_curve
)

router = APIRouter(prefix="/api/trading", tags=["trading"])

class PlaceBetRequest(BaseModel):
    symbol: str
    direction: str  # bullish or bearish
    amount: float
    expected_time: str
    intelligence_source: str
    reason: str
    intelligence_id: Optional[int] = None

class RecordResultRequest(BaseModel):
    trade_id: int
    actual_direction: str  # up, down, or unchanged
    profit_loss: float
    return_rate: float

class ResetAccountRequest(BaseModel):
    initial_balance: Optional[float] = 10000.0

class AddFundsRequest(BaseModel):
    amount: float

@router.get("/account")
async def get_account():
    """获取账户信息"""
    try:
        info = get_account_info()
        return info
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/place-bet")
async def place_bet(request: PlaceBetRequest):
    """放置虚拟下注"""
    try:
        result = place_virtual_bet(
            request.symbol,
            request.direction,
            request.amount,
            request.expected_time,
            request.intelligence_source,
            request.reason,
            request.intelligence_id
        )
        
        if result['success']:
            return result
        else:
            raise HTTPException(status_code=400, detail=result['error'])
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/record-result")
async def record_result(request: RecordResultRequest):
    """记录交易结果"""
    try:
        result = record_trade_result(
            request.trade_id,
            request.actual_direction,
            request.profit_loss,
            request.return_rate
        )
        
        if result['success']:
            return result
        else:
            raise HTTPException(status_code=400, detail=result['message'])
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/statistics")
async def get_statistics():
    """获取交易统计"""
    try:
        stats = get_trading_statistics()
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/history")
async def get_history(limit: int = 100):
    """获取交易历史"""
    try:
        history_data = get_trading_history(limit)
        return history_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/reset-account")
async def reset_account(request: ResetAccountRequest):
    """重置交易账户"""
    try:
        result = reset_trading_account(request.initial_balance)
        
        if result['success']:
            return result
        else:
            raise HTTPException(status_code=400, detail=result['message'])
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/add-funds")
async def add_funds(request: AddFundsRequest):
    """添加资金"""
    try:
        result = add_trading_funds(request.amount)
        
        if result['success']:
            return result
        else:
            raise HTTPException(status_code=400, detail=result['message'])
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/pnl-curve")
async def get_pnl_curve_endpoint():
    """获取收益曲线数据"""
    try:
        curve_data = get_pnl_curve()
        return curve_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/status")
async def get_trading_status():
    """获取交易系统完整状态（用于仪表盘）"""
    try:
        import sqlite3
        from pathlib import Path
        
        PROJECT_ROOT = Path(__file__).parent.parent
        trading_db = PROJECT_ROOT / "trading.db"
        
        result = {
            "accounts": [],
            "total_trades": 0,
            "completed_trades": 0,
            "pending_trades": 0,
            "total_pnl": 0,
            "win_rate": 0,
            "recent_trades": []
        }
        
        if trading_db.exists() and trading_db.stat().st_size > 0:
            conn = sqlite3.connect(str(trading_db))
            cursor = conn.cursor()
            
            # Get accounts
            cursor.execute("SELECT id, balance, initial_balance FROM accounts")
            accounts = cursor.fetchall()
            result["accounts"] = [
                {"id": acc[0], "balance": acc[1], "initial_balance": acc[2]}
                for acc in accounts
            ]
            
            # Get trade counts
            cursor.execute("SELECT COUNT(*) FROM trades")
            result["total_trades"] = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM trades WHERE status = 'completed'")
            result["completed_trades"] = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM trades WHERE status = 'pending'")
            result["pending_trades"] = cursor.fetchone()[0]
            
            # Get PnL and win rate
            cursor.execute("SELECT SUM(profit_loss) FROM trade_results")
            total_pnl = cursor.fetchone()[0] or 0
            result["total_pnl"] = total_pnl
            
            cursor.execute("SELECT COUNT(*) FROM trade_results WHERE profit_loss > 0")
            wins = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM trade_results WHERE profit_loss < 0")
            losses = cursor.fetchone()[0]
            if wins + losses > 0:
                result["win_rate"] = (wins / (wins + losses)) * 100
            
            # Get recent trades
            cursor.execute("""
                SELECT t.id, t.symbol, t.direction, t.amount, t.status, t.created_at,
                       tr.profit_loss
                FROM trades t
                LEFT JOIN trade_results tr ON t.id = tr.trade_id
                ORDER BY t.created_at DESC
                LIMIT 10
            """)
            trades = cursor.fetchall()
            result["recent_trades"] = [
                {
                    "id": t[0],
                    "symbol": t[1],
                    "direction": t[2],
                    "amount": t[3],
                    "status": t[4],
                    "created_at": t[5],
                    "profit_loss": t[6]
                }
                for t in trades
            ]
            
            conn.close()
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 情报集成路由 ====================
# 注意：固定路径必须放在参数化路径（如 {intel_id}）之前

from .intelligence_integration import (
    IntelligenceTradingIntegration, Intelligence, IntelligenceType, IntelligenceStatus
)

class CreateIntelligenceRequest(BaseModel):
    title: str
    content: Optional[str] = ""
    source: str
    target_symbol: Optional[str] = ""
    direction: Optional[str] = "neutral"
    confidence: Optional[float] = 0.5
    source_type: Optional[str] = "news"
    expected_impact: Optional[str] = "medium"
    time_horizon: Optional[str] = "short"

class TradeFromIntelligenceRequest(BaseModel):
    intelligence_id: int
    amount: Optional[float] = None
    expected_time: Optional[str] = None

class VerifyIntelligenceRequest(BaseModel):
    intelligence_id: int
    actual_outcome: str  # correct, incorrect, partial
    accuracy_score: Optional[float] = None

@router.post("/intelligence/create")
async def create_intelligence(request: CreateIntelligenceRequest):
    """创建情报"""
    try:
        manager = IntelligenceTradingIntegration()
        intel = Intelligence(
            title=request.title,
            content=request.content,
            source=request.source,
            target_symbol=request.target_symbol,
            direction=request.direction,
            confidence=request.confidence,
            source_type=IntelligenceType(request.source_type),
            expected_impact=request.expected_impact,
            time_horizon=request.time_horizon
        )
        intel_id = manager.create_intelligence(intel)
        return {'success': True, 'intelligence_id': intel_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/intelligence/list")
async def list_intelligences(status: str = None, limit: int = 100):
    """列出情报"""
    try:
        manager = IntelligenceTradingIntegration()
        intelligences = manager.list_intelligences(status, limit)
        return {'intelligences': intelligences, 'count': len(intelligences)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/intelligence/trade")
async def trade_from_intelligence(request: TradeFromIntelligenceRequest):
    """从情报发起虚拟交易"""
    try:
        manager = IntelligenceTradingIntegration()
        result = manager.place_trade_from_intelligence(
            request.intelligence_id,
            request.amount,
            request.expected_time
        )
        if result['success']:
            return result
        else:
            raise HTTPException(status_code=400, detail=result['error'])
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/intelligence/verify")
async def verify_intelligence(request: VerifyIntelligenceRequest):
    """验证情报结果"""
    try:
        manager = IntelligenceTradingIntegration()
        result = manager.verify_intelligence(
            request.intelligence_id,
            request.actual_outcome,
            request.accuracy_score
        )
        if result['success']:
            return result
        else:
            raise HTTPException(status_code=400, detail=result['error'])
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/intelligence/auto-trade")
async def auto_trade_high_confidence():
    """自动交易高置信度情报"""
    try:
        manager = IntelligenceTradingIntegration()
        results = manager.auto_trade_high_confidence()
        return {'success': True, 'trades': results, 'count': len(results)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/intelligence/statistics")
async def get_intelligence_statistics():
    """获取情报统计"""
    try:
        manager = IntelligenceTradingIntegration()
        stats = manager.get_intelligence_statistics()
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/intelligence/best-sources")
async def get_best_intelligence_sources(min_count: int = 3):
    """获取最佳情报来源"""
    try:
        manager = IntelligenceTradingIntegration()
        sources = manager.get_best_sources(min_count)
        return {'sources': sources, 'count': len(sources)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 增强功能路由 ====================

class SettleTradeRequest(BaseModel):
    trade_id: int
    actual_direction: str
    actual_price_change: Optional[float] = None
    success_reason: Optional[str] = None
    failure_reason: Optional[str] = None
    improvement_suggestions: Optional[str] = None

class AutoSettleRequest(BaseModel):
    hours: Optional[int] = 24

@router.post("/settle-trade")
async def settle_trade_with_verification(request: SettleTradeRequest):
    """结算交易并记录详细分析"""
    try:
        manager = IntelligenceTradingIntegration()
        result = manager.settle_trade_with_verification(
            request.trade_id,
            request.actual_direction,
            request.actual_price_change,
            request.success_reason,
            request.failure_reason,
            request.improvement_suggestions
        )
        if result['success']:
            return result
        else:
            raise HTTPException(status_code=400, detail=result['error'])
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/auto-settle")
async def auto_settle_expired_trades(request: AutoSettleRequest):
    """自动结算过期交易"""
    try:
        manager = IntelligenceTradingIntegration()
        results = manager.auto_settle_expired_trades(request.hours)
        return {'success': True, 'settled_trades': results, 'count': len(results)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/enhanced-statistics")
async def get_enhanced_statistics():
    """获取增强统计数据（绩效看板）"""
    try:
        manager = IntelligenceTradingIntegration()
        stats = manager.get_enhanced_statistics()
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/source-stats/{source}")
async def get_source_detailed_stats(source: str):
    """获取情报源详细统计"""
    try:
        manager = IntelligenceTradingIntegration()
        stats = manager.get_source_detailed_stats(source)
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/source-stats")
async def get_all_source_stats():
    """获取所有情报源统计"""
    try:
        manager = IntelligenceTradingIntegration()
        stats = manager.get_source_detailed_stats()
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/performance-dashboard")
async def get_performance_dashboard():
    """获取绩效看板完整数据"""
    try:
        from . import get_trading_statistics, get_trading_history
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

# 参数化路由必须放在最后
@router.get("/intelligence/{intel_id}")
async def get_intelligence(intel_id: int):
    """获取情报详情"""
    try:
        manager = IntelligenceTradingIntegration()
        intel = manager.get_intelligence(intel_id)
        if not intel:
            raise HTTPException(status_code=404, detail="Intelligence not found")
        return intel
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 复盘系统路由 ====================
from .review_system import (
    ReviewManager, ReviewDashboard, IntelligenceSourceScoring,
    auto_review_pending_trades, get_review_dashboard, get_review_list, update_review_record
)

class UpdateReviewRequest(BaseModel):
    success_reason: Optional[str] = None
    failure_reason: Optional[str] = None
    improvement_suggestions: Optional[str] = None
    reviewer_notes: Optional[str] = None

@router.post("/review/auto")
async def auto_review_trades():
    """自动复盘所有待复盘交易"""
    try:
        result = auto_review_pending_trades()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/review/dashboard")
async def get_dashboard():
    """获取复盘看板数据"""
    try:
        dashboard = get_review_dashboard()
        return dashboard
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/review/list")
async def list_reviews(status: str = None, limit: int = 100):
    """获取复盘列表"""
    try:
        reviews = get_review_list(status, limit)
        return {'reviews': reviews, 'count': len(reviews)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.patch("/review/{review_id}")
async def update_review(review_id: int, request: UpdateReviewRequest):
    """更新复盘记录（人工复盘）"""
    try:
        result = update_review_record(
            review_id,
            success_reason=request.success_reason,
            failure_reason=request.failure_reason,
            improvement_suggestions=request.improvement_suggestions,
            reviewer_notes=request.reviewer_notes
        )
        if result['success']:
            return result
        else:
            raise HTTPException(status_code=400, detail=result['message'])
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/review/create/{trade_id}")
async def create_review_for_trade(trade_id: int):
    """为指定交易创建复盘记录"""
    try:
        manager = ReviewManager()
        review_id = manager.create_review_from_trade(trade_id)
        if review_id:
            return {'success': True, 'review_id': review_id}
        else:
            raise HTTPException(status_code=400, detail="Trade not found or not completed")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/review/performance")
async def get_performance():
    """获取总体表现统计"""
    try:
        dashboard = ReviewDashboard()
        performance = dashboard.get_overall_performance()
        return performance
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/review/sources")
async def get_source_ranking(limit: int = 20):
    """获取情报源排名"""
    try:
        scoring = IntelligenceSourceScoring()
        ranking = scoring.get_source_ranking(limit)
        return {'sources': ranking, 'count': len(ranking)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/review/insights")
async def get_improvement_insights():
    """获取改进建议"""
    try:
        dashboard = ReviewDashboard()
        insights = dashboard.get_improvement_insights()
        return {'insights': insights}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))