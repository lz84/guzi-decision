"""
情报集成模块 - 谷子情报分析系统
实现情报系统与虚拟交易的集成
"""

import sqlite3
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum
import logging

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.parent


class IntelligenceStatus(str, Enum):
    """情报状态"""
    NEW = "new"                    # 新建
    ANALYZED = "analyzed"          # 已分析
    TRADING = "trading"            # 交易中
    VERIFIED = "verified"          # 已验证
    EXPIRED = "expired"            # 已过期


class IntelligenceType(str, Enum):
    """情报类型"""
    MARKET = "market"              # 市场情报
    POLICY = "policy"              # 政策情报
    COMPANY = "company"            # 公司情报
    TECHNICAL = "technical"        # 技术分析
    SENTIMENT = "sentiment"        # 情绪分析
    NEWS = "news"                  # 新闻情报


@dataclass
class Intelligence:
    """情报数据结构"""
    id: Optional[int] = None
    title: str = ""
    content: str = ""
    source: str = ""
    source_type: IntelligenceType = IntelligenceType.NEWS
    confidence: float = 0.5  # 0-1, 情报置信度
    target_symbol: str = ""  # 相关标的
    direction: str = ""      # bullish/bearish/neutral
    expected_impact: str = ""  # high/medium/low
    time_horizon: str = ""   # short/medium/long
    status: IntelligenceStatus = IntelligenceStatus.NEW
    created_at: Optional[datetime] = None
    analyzed_at: Optional[datetime] = None
    verified_at: Optional[datetime] = None
    
    # 验证结果
    actual_outcome: str = ""  # correct/incorrect/partial
    accuracy_score: float = 0.0
    
    # 新增：关键信号和预测信息
    key_signals: List[str] = field(default_factory=list)  # 关键信号列表
    expected_direction: str = ""  # 预期方向
    expected_time: Optional[str] = None  # 预期时间
    expected_return: float = 0.0  # 预期收益率
    risk_level: str = "medium"  # 风险等级 low/medium/high


class IntelligenceTradingIntegration:
    """情报交易集成管理器"""
    
    def __init__(self, db_path: str = None):
        if db_path is None:
            self.db_path = str(PROJECT_ROOT / "trading.db")
        else:
            self.db_path = db_path
        self.init_intelligence_tables()
        self.logger = logging.getLogger(__name__)
        
        # 高置信度阈值
        self.auto_trade_threshold = 0.7  # 70% 以上置信度自动交易
        self.auto_trade_amount = 100.0   # 自动交易金额
    
    def init_intelligence_tables(self):
        """初始化情报相关表"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 创建情报表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS intelligences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                content TEXT,
                source TEXT NOT NULL,
                source_type TEXT DEFAULT 'news',
                confidence REAL DEFAULT 0.5,
                target_symbol TEXT,
                direction TEXT CHECK(direction IN ('bullish', 'bearish', 'neutral')),
                expected_impact TEXT CHECK(expected_impact IN ('high', 'medium', 'low')),
                time_horizon TEXT CHECK(time_horizon IN ('short', 'medium', 'long')),
                status TEXT DEFAULT 'new' CHECK(status IN ('new', 'analyzed', 'trading', 'verified', 'expired')),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                analyzed_at TIMESTAMP,
                verified_at TIMESTAMP,
                actual_outcome TEXT CHECK(actual_outcome IN ('correct', 'incorrect', 'partial')),
                accuracy_score REAL DEFAULT 0.0,
                key_signals TEXT,
                expected_direction TEXT,
                expected_time TIMESTAMP,
                expected_return REAL DEFAULT 0.0,
                risk_level TEXT DEFAULT 'medium',
                metadata TEXT
            )
        ''')
        
        # 为 trades 表添加新列（如果不存在）
        cursor.execute("PRAGMA table_info(trades)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'intelligence_id' not in columns:
            cursor.execute('ALTER TABLE trades ADD COLUMN intelligence_id INTEGER REFERENCES intelligences(id)')
        
        if 'expected_return' not in columns:
            cursor.execute('ALTER TABLE trades ADD COLUMN expected_return REAL DEFAULT 0.0')
        
        if 'risk_level' not in columns:
            cursor.execute('ALTER TABLE trades ADD COLUMN risk_level TEXT DEFAULT "medium"')
        
        if 'key_signals' not in columns:
            cursor.execute('ALTER TABLE trades ADD COLUMN key_signals TEXT')
        
        # 为 trade_results 表添加新列
        cursor.execute("PRAGMA table_info(trade_results)")
        result_columns = [col[1] for col in cursor.fetchall()]
        
        if 'success_reason' not in result_columns:
            cursor.execute('ALTER TABLE trade_results ADD COLUMN success_reason TEXT')
        
        if 'failure_reason' not in result_columns:
            cursor.execute('ALTER TABLE trade_results ADD COLUMN failure_reason TEXT')
        
        if 'improvement_suggestions' not in result_columns:
            cursor.execute('ALTER TABLE trade_results ADD COLUMN improvement_suggestions TEXT')
        
        if 'prediction_deviation' not in result_columns:
            cursor.execute('ALTER TABLE trade_results ADD COLUMN prediction_deviation REAL DEFAULT 0.0')
        
        # 创建情报源跟踪表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS source_tracking (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_name TEXT NOT NULL UNIQUE,
                total_intelligences INTEGER DEFAULT 0,
                correct_predictions INTEGER DEFAULT 0,
                incorrect_predictions INTEGER DEFAULT 0,
                partial_predictions INTEGER DEFAULT 0,
                avg_accuracy REAL DEFAULT 0.0,
                avg_return REAL DEFAULT 0.0,
                total_profit REAL DEFAULT 0.0,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
    
    # ==================== 情报管理 ====================
    
    def create_intelligence(self, intel: Intelligence) -> int:
        """创建情报记录"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO intelligences (
                title, content, source, source_type, confidence,
                target_symbol, direction, expected_impact, time_horizon, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            intel.title, intel.content, intel.source, intel.source_type.value,
            intel.confidence, intel.target_symbol, intel.direction,
            intel.expected_impact, intel.time_horizon, intel.status.value
        ))
        
        intel_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        self.logger.info(f"Created intelligence #{intel_id}: {intel.title}")
        return intel_id
    
    def get_intelligence(self, intel_id: int) -> Optional[Dict]:
        """获取情报详情"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM intelligences WHERE id = ?', (intel_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            columns = [desc[0] for desc in cursor.description]
            return dict(zip(columns, row))
        return None
    
    def list_intelligences(self, status: str = None, limit: int = 100) -> List[Dict]:
        """列出情报"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if status:
            cursor.execute('''
                SELECT * FROM intelligences 
                WHERE status = ? 
                ORDER BY created_at DESC 
                LIMIT ?
            ''', (status, limit))
        else:
            cursor.execute('''
                SELECT * FROM intelligences 
                ORDER BY created_at DESC 
                LIMIT ?
            ''', (limit,))
        
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        conn.close()
        
        return [dict(zip(columns, row)) for row in rows]
    
    def update_intelligence_status(self, intel_id: int, status: IntelligenceStatus, 
                                   actual_outcome: str = None, accuracy_score: float = None):
        """更新情报状态"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        updates = ['status = ?']
        params = [status.value]
        
        if status == IntelligenceStatus.ANALYZED:
            updates.append('analyzed_at = CURRENT_TIMESTAMP')
        elif status == IntelligenceStatus.VERIFIED:
            updates.append('verified_at = CURRENT_TIMESTAMP')
            if actual_outcome:
                updates.append('actual_outcome = ?')
                params.append(actual_outcome)
            if accuracy_score is not None:
                updates.append('accuracy_score = ?')
                params.append(accuracy_score)
        
        params.append(intel_id)
        
        cursor.execute(f'''
            UPDATE intelligences 
            SET {', '.join(updates)}
            WHERE id = ?
        ''', params)
        
        conn.commit()
        conn.close()
    
    # ==================== 情报->交易 ====================
    
    def place_trade_from_intelligence(self, intel_id: int, amount: float = None,
                                       expected_time: str = None) -> Dict:
        """从情报发起虚拟交易"""
        intel = self.get_intelligence(intel_id)
        if not intel:
            return {'success': False, 'error': 'Intelligence not found'}
        
        if intel['status'] in ['trading', 'verified', 'expired']:
            return {'success': False, 'error': f"Intelligence already {intel['status']}"}
        
        if not intel['target_symbol']:
            return {'success': False, 'error': 'Intelligence has no target symbol'}
        
        if not intel['direction'] or intel['direction'] == 'neutral':
            return {'success': False, 'error': 'Intelligence has no clear direction'}
        
        # 使用默认金额或传入金额
        trade_amount = amount or self.auto_trade_amount
        
        # 默认预期时间为24小时后
        if not expected_time:
            from datetime import timedelta
            expected_time = (datetime.now() + timedelta(hours=24)).isoformat()
        
        try:
            # 放置交易
            from src.virtual_trading.manager import VirtualTradingManager
            manager = VirtualTradingManager(self.db_path)
            
            trade_id = manager.place_bet(
                symbol=intel['target_symbol'],
                direction=intel['direction'],
                amount=trade_amount,
                expected_time=expected_time,
                intelligence_source=intel['source'],
                reason=f"Based on intelligence #{intel_id}: {intel['title']}"
            )
            
            # 关联情报ID
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('UPDATE trades SET intelligence_id = ? WHERE id = ?', (intel_id, trade_id))
            cursor.execute('UPDATE intelligences SET status = "trading" WHERE id = ?', (intel_id,))
            conn.commit()
            conn.close()
            
            self.logger.info(f"Placed trade #{trade_id} from intelligence #{intel_id}")
            
            return {
                'success': True,
                'trade_id': trade_id,
                'intelligence_id': intel_id,
                'symbol': intel['target_symbol'],
                'direction': intel['direction'],
                'amount': trade_amount
            }
            
        except Exception as e:
            self.logger.error(f"Failed to place trade from intelligence: {e}")
            return {'success': False, 'error': str(e)}
    
    def auto_trade_high_confidence(self) -> List[Dict]:
        """自动交易高置信度情报"""
        results = []
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 查找高置信度且未交易的情报
        cursor.execute('''
            SELECT id FROM intelligences 
            WHERE status = 'analyzed' 
            AND confidence >= ? 
            AND direction IN ('bullish', 'bearish')
            AND target_symbol IS NOT NULL
        ''', (self.auto_trade_threshold,))
        
        intel_ids = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        for intel_id in intel_ids:
            result = self.place_trade_from_intelligence(intel_id)
            results.append(result)
        
        self.logger.info(f"Auto-traded {len([r for r in results if r.get('success')])} high-confidence intelligences")
        return results
    
    # ==================== 统计分析 ====================
    
    def get_intelligence_statistics(self) -> Dict:
        """获取情报统计"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        stats = {}
        
        # 总情报数
        cursor.execute('SELECT COUNT(*) FROM intelligences')
        stats['total_intelligences'] = cursor.fetchone()[0]
        
        # 各状态数量
        cursor.execute('''
            SELECT status, COUNT(*) 
            FROM intelligences 
            GROUP BY status
        ''')
        stats['by_status'] = {row[0]: row[1] for row in cursor.fetchall()}
        
        # 按来源统计胜率
        cursor.execute('''
            SELECT i.source, 
                   COUNT(*) as total,
                   SUM(CASE WHEN i.actual_outcome = 'correct' THEN 1 ELSE 0 END) as correct,
                   AVG(i.accuracy_score) as avg_accuracy
            FROM intelligences i
            WHERE i.status = 'verified'
            GROUP BY i.source
            ORDER BY avg_accuracy DESC
        ''')
        stats['by_source'] = [
            {
                'source': row[0],
                'total': row[1],
                'correct': row[2],
                'win_rate': row[2] / row[1] * 100 if row[1] > 0 else 0,
                'avg_accuracy': row[3] or 0
            }
            for row in cursor.fetchall()
        ]
        
        # 按情报类型统计
        cursor.execute('''
            SELECT source_type, COUNT(*) 
            FROM intelligences 
            GROUP BY source_type
        ''')
        stats['by_type'] = {row[0]: row[1] for row in cursor.fetchall()}
        
        # 情报准确率排名
        cursor.execute('''
            SELECT source, AVG(accuracy_score) as avg_score, COUNT(*) as count
            FROM intelligences
            WHERE status = 'verified' AND accuracy_score > 0
            GROUP BY source
            HAVING count >= 3
            ORDER BY avg_score DESC
            LIMIT 10
        ''')
        stats['accuracy_ranking'] = [
            {'source': row[0], 'avg_accuracy': row[1], 'count': row[2]}
            for row in cursor.fetchall()
        ]
        
        # 关联交易统计
        cursor.execute('''
            SELECT 
                COUNT(DISTINCT t.intelligence_id) as traded_intelligences,
                COUNT(*) as total_trades,
                SUM(CASE WHEN tr.profit_loss > 0 THEN 1 ELSE 0 END) as profitable_trades
            FROM trades t
            LEFT JOIN trade_results tr ON t.id = tr.trade_id
            WHERE t.intelligence_id IS NOT NULL
        ''')
        row = cursor.fetchone()
        stats['trading'] = {
            'traded_intelligences': row[0],
            'total_trades': row[1],
            'profitable_trades': row[2],
            'win_rate': row[2] / row[1] * 100 if row[1] > 0 else 0
        }
        
        conn.close()
        return stats
    
    def get_best_sources(self, min_count: int = 3) -> List[Dict]:
        """获取最佳情报来源"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT i.source, 
                   COUNT(*) as total,
                   AVG(i.accuracy_score) as avg_accuracy,
                   SUM(CASE WHEN t.id IS NOT NULL THEN 1 ELSE 0 END) as traded,
                   AVG(tr.profit_loss) as avg_profit
            FROM intelligences i
            LEFT JOIN trades t ON t.intelligence_id = i.id
            LEFT JOIN trade_results tr ON tr.trade_id = t.id
            WHERE i.status = 'verified'
            GROUP BY i.source
            HAVING total >= ?
            ORDER BY avg_accuracy DESC, avg_profit DESC
        ''', (min_count,))
        
        results = [
            {
                'source': row[0],
                'total_intelligences': row[1],
                'avg_accuracy': row[2] or 0,
                'traded_count': row[3],
                'avg_profit': row[4] or 0
            }
            for row in cursor.fetchall()
        ]
        
        conn.close()
        return results
    
    def verify_intelligence(self, intel_id: int, actual_outcome: str, 
                           accuracy_score: float = None) -> Dict:
        """验证情报结果"""
        intel = self.get_intelligence(intel_id)
        if not intel:
            return {'success': False, 'error': 'Intelligence not found'}
        
        # 如果未提供准确度分数，根据结果计算
        if accuracy_score is None:
            if actual_outcome == 'correct':
                accuracy_score = 1.0
            elif actual_outcome == 'partial':
                accuracy_score = 0.5
            else:
                accuracy_score = 0.0
        
        self.update_intelligence_status(
            intel_id, 
            IntelligenceStatus.VERIFIED,
            actual_outcome,
            accuracy_score
        )
        
        # 更新情报源跟踪统计
        self._update_source_tracking(intel['source'], actual_outcome, accuracy_score)
        
        self.logger.info(f"Verified intelligence #{intel_id}: {actual_outcome} (accuracy: {accuracy_score})")
        
        return {
            'success': True,
            'intelligence_id': intel_id,
            'actual_outcome': actual_outcome,
            'accuracy_score': accuracy_score
        }
    
    def _update_source_tracking(self, source: str, outcome: str, accuracy: float):
        """更新情报源跟踪统计"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 检查是否存在该来源记录
        cursor.execute('SELECT id FROM source_tracking WHERE source_name = ?', (source,))
        exists = cursor.fetchone()
        
        if exists:
            # 更新现有记录
            if outcome == 'correct':
                cursor.execute('''
                    UPDATE source_tracking 
                    SET total_intelligences = total_intelligences + 1,
                        correct_predictions = correct_predictions + 1,
                        avg_accuracy = (avg_accuracy * total_intelligences + ?) / (total_intelligences + 1),
                        last_updated = CURRENT_TIMESTAMP
                    WHERE source_name = ?
                ''', (accuracy, source))
            elif outcome == 'incorrect':
                cursor.execute('''
                    UPDATE source_tracking 
                    SET total_intelligences = total_intelligences + 1,
                        incorrect_predictions = incorrect_predictions + 1,
                        avg_accuracy = (avg_accuracy * total_intelligences + ?) / (total_intelligences + 1),
                        last_updated = CURRENT_TIMESTAMP
                    WHERE source_name = ?
                ''', (accuracy, source))
            else:  # partial
                cursor.execute('''
                    UPDATE source_tracking 
                    SET total_intelligences = total_intelligences + 1,
                        partial_predictions = partial_predictions + 1,
                        avg_accuracy = (avg_accuracy * total_intelligences + ?) / (total_intelligences + 1),
                        last_updated = CURRENT_TIMESTAMP
                    WHERE source_name = ?
                ''', (accuracy, source))
        else:
            # 创建新记录
            cursor.execute('''
                INSERT INTO source_tracking (
                    source_name, total_intelligences, 
                    correct_predictions, incorrect_predictions, partial_predictions,
                    avg_accuracy
                ) VALUES (?, 1, ?, ?, ?, ?)
            ''', (
                source,
                1 if outcome == 'correct' else 0,
                1 if outcome == 'incorrect' else 0,
                1 if outcome == 'partial' else 0,
                accuracy
            ))
        
        conn.commit()
        conn.close()
    
    # ==================== 自动结算功能 ====================
    
    def auto_settle_expired_trades(self, hours: int = 24) -> List[Dict]:
        """自动结算过期的交易（超过预期时间未验证）"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 查找超时的待处理交易
        cutoff_time = datetime.now() - timedelta(hours=hours)
        cursor.execute('''
            SELECT t.id, t.symbol, t.direction, t.amount, t.intelligence_id,
                   t.expected_time
            FROM trades t
            WHERE t.status = 'pending'
            AND datetime(t.expected_time) < datetime(?)
        ''', (cutoff_time.isoformat(),))
        
        expired_trades = cursor.fetchall()
        results = []
        
        for trade in expired_trades:
            trade_id, symbol, direction, amount, intel_id, expected_time = trade
            
            # 默认结算：假设预测失败，损失本金的一定比例
            loss_rate = 0.5  # 默认损失50%
            profit_loss = -amount * loss_rate
            return_rate = -loss_rate
            
            # 记录结果
            cursor.execute('''
                INSERT INTO trade_results (
                    trade_id, actual_direction, profit_loss, return_rate,
                    failure_reason, prediction_deviation
                ) VALUES (?, 'unchanged', ?, ?, 'Auto-settled: expired without verification', 1.0)
            ''', (trade_id, profit_loss, return_rate))
            
            # 更新交易状态
            cursor.execute('UPDATE trades SET status = "completed", completed_at = CURRENT_TIMESTAMP WHERE id = ?', 
                         (trade_id,))
            
            # 如果关联了情报，更新情报状态
            if intel_id:
                cursor.execute('UPDATE intelligences SET status = "expired" WHERE id = ?', (intel_id,))
            
            results.append({
                'trade_id': trade_id,
                'status': 'auto_settled',
                'profit_loss': profit_loss,
                'return_rate': return_rate
            })
        
        conn.commit()
        conn.close()
        
        self.logger.info(f"Auto-settled {len(results)} expired trades")
        return results
    
    def settle_trade_with_verification(self, trade_id: int, actual_direction: str,
                                        actual_price_change: float = None,
                                        success_reason: str = None,
                                        failure_reason: str = None,
                                        improvement_suggestions: str = None) -> Dict:
        """结算交易并记录详细分析"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 获取交易信息
        cursor.execute('''
            SELECT t.id, t.amount, t.direction, t.intelligence_id
            FROM trades t
            WHERE t.id = ? AND t.status = 'pending'
        ''', (trade_id,))
        
        trade = cursor.fetchone()
        if not trade:
            conn.close()
            return {'success': False, 'error': 'Trade not found or already settled'}
        
        t_id, amount, direction, intel_id = trade
        
        # 计算收益
        if direction == 'bullish':
            if actual_direction == 'up':
                profit_loss = amount * abs(actual_price_change or 0.1)
                return_rate = abs(actual_price_change or 0.1)
            elif actual_direction == 'down':
                profit_loss = -amount * abs(actual_price_change or 0.1)
                return_rate = -abs(actual_price_change or 0.1)
            else:
                profit_loss = 0
                return_rate = 0
        else:  # bearish
            if actual_direction == 'down':
                profit_loss = amount * abs(actual_price_change or 0.1)
                return_rate = abs(actual_price_change or 0.1)
            elif actual_direction == 'up':
                profit_loss = -amount * abs(actual_price_change or 0.1)
                return_rate = -abs(actual_price_change or 0.1)
            else:
                profit_loss = 0
                return_rate = 0
        
        # 计算预测偏差（默认预期收益为10%）
        expected = 0.1
        prediction_deviation = abs(return_rate - expected)
        
        # 记录结果
        cursor.execute('''
            INSERT INTO trade_results (
                trade_id, actual_direction, profit_loss, return_rate,
                success_reason, failure_reason, improvement_suggestions, prediction_deviation
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (trade_id, actual_direction, profit_loss, return_rate,
              success_reason, failure_reason, improvement_suggestions, prediction_deviation))
        
        # 更新交易状态
        cursor.execute('UPDATE trades SET status = "completed", completed_at = CURRENT_TIMESTAMP WHERE id = ?', 
                     (trade_id,))
        
        # 更新账户余额
        cursor.execute('SELECT balance FROM accounts ORDER BY id DESC LIMIT 1')
        current_balance = cursor.fetchone()[0]
        new_balance = current_balance + profit_loss
        cursor.execute('INSERT INTO accounts (balance, initial_balance) VALUES (?, (SELECT initial_balance FROM accounts ORDER BY id DESC LIMIT 1))', 
                     (new_balance,))
        
        conn.commit()
        conn.close()
        
        return {
            'success': True,
            'trade_id': trade_id,
            'profit_loss': profit_loss,
            'return_rate': return_rate,
            'prediction_deviation': prediction_deviation
        }
    
    # ==================== 增强统计分析 ====================
    
    def get_enhanced_statistics(self) -> Dict[str, Any]:
        """获取增强统计数据（用于绩效看板）"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        stats = {}
        
        # 基础交易统计
        cursor.execute('SELECT COUNT(*) FROM trades WHERE status = "completed"')
        stats['total_completed_trades'] = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM trades WHERE status = "pending"')
        stats['pending_trades'] = cursor.fetchone()[0]
        
        cursor.execute('SELECT SUM(profit_loss) FROM trade_results')
        stats['total_pnl'] = cursor.fetchone()[0] or 0.0
        
        # 胜率统计
        cursor.execute('SELECT COUNT(*) FROM trade_results WHERE profit_loss > 0')
        wins = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM trade_results WHERE profit_loss < 0')
        losses = cursor.fetchone()[0]
        stats['winning_trades'] = wins
        stats['losing_trades'] = losses
        stats['win_rate'] = (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0
        
        # 平均收益
        cursor.execute('SELECT AVG(return_rate) FROM trade_results WHERE return_rate > 0')
        stats['avg_win_rate'] = cursor.fetchone()[0] or 0.0
        
        cursor.execute('SELECT AVG(return_rate) FROM trade_results WHERE return_rate < 0')
        stats['avg_loss_rate'] = cursor.fetchone()[0] or 0.0
        
        # 情报准确率统计
        cursor.execute('''
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN actual_outcome = 'correct' THEN 1 ELSE 0 END) as correct,
                AVG(accuracy_score) as avg_accuracy
            FROM intelligences
            WHERE status = 'verified'
        ''')
        row = cursor.fetchone()
        stats['intelligence'] = {
            'total_verified': row[0],
            'correct': row[1],
            'accuracy_rate': (row[1] / row[0] * 100) if row[0] > 0 else 0,
            'avg_accuracy_score': row[2] or 0.0
        }
        
        # 情报源排名
        cursor.execute('''
            SELECT source_name, total_intelligences, correct_predictions, 
                   avg_accuracy, avg_return, total_profit
            FROM source_tracking
            ORDER BY avg_accuracy DESC, total_profit DESC
            LIMIT 10
        ''')
        stats['source_ranking'] = [
            {
                'source': row[0],
                'total': row[1],
                'correct': row[2],
                'accuracy': row[3] or 0.0,
                'avg_return': row[4] or 0.0,
                'total_profit': row[5] or 0.0
            }
            for row in cursor.fetchall()
        ]
        
        # 最近表现（最近7天）
        cursor.execute('''
            SELECT DATE(created_at) as date, 
                   COUNT(*) as trades,
                   SUM(CASE WHEN profit_loss > 0 THEN 1 ELSE 0 END) as wins
            FROM trades t
            JOIN trade_results tr ON t.id = tr.trade_id
            WHERE t.created_at >= DATE('now', '-7 days')
            GROUP BY DATE(created_at)
            ORDER BY date DESC
        ''')
        stats['recent_performance'] = [
            {
                'date': row[0],
                'trades': row[1],
                'wins': row[2],
                'win_rate': (row[2] / row[1] * 100) if row[1] > 0 else 0
            }
            for row in cursor.fetchall()
        ]
        
        # 改进建议汇总
        cursor.execute('''
            SELECT improvement_suggestions, COUNT(*) as count
            FROM trade_results
            WHERE improvement_suggestions IS NOT NULL
            AND improvement_suggestions != ''
            GROUP BY improvement_suggestions
            ORDER BY count DESC
            LIMIT 5
        ''')
        stats['improvement_suggestions'] = [
            {'suggestion': row[0], 'count': row[1]}
            for row in cursor.fetchall()
        ]
        
        conn.close()
        return stats
    
    def get_source_detailed_stats(self, source: str = None) -> Dict:
        """获取情报源详细统计"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if source:
            cursor.execute('SELECT * FROM source_tracking WHERE source_name = ?', (source,))
            row = cursor.fetchone()
            if not row:
                conn.close()
                return {'error': 'Source not found'}
            
            columns = [desc[0] for desc in cursor.description]
            result = dict(zip(columns, row))
            conn.close()
            return result
        else:
            cursor.execute('SELECT * FROM source_tracking ORDER BY avg_accuracy DESC')
            rows = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]
            conn.close()
            return {
                'sources': [dict(zip(columns, row)) for row in rows],
                'total_sources': len(rows)
            }


# API函数
def create_intelligence_trading_manager() -> IntelligenceTradingIntegration:
    """创建集成管理器"""
    return IntelligenceTradingIntegration()


def create_intelligence(title: str, content: str, source: str, 
                        target_symbol: str = "", direction: str = "",
                        confidence: float = 0.5, **kwargs) -> Dict:
    """创建情报API"""
    manager = IntelligenceTradingIntegration()
    intel = Intelligence(
        title=title,
        content=content,
        source=source,
        target_symbol=target_symbol,
        direction=direction,
        confidence=confidence,
        **kwargs
    )
    intel_id = manager.create_intelligence(intel)
    return {'success': True, 'intelligence_id': intel_id}


def trade_from_intelligence(intel_id: int, amount: float = None) -> Dict:
    """从情报发起交易API"""
    manager = IntelligenceTradingIntegration()
    return manager.place_trade_from_intelligence(intel_id, amount)


def get_intelligence_statistics() -> Dict:
    """获取情报统计API"""
    manager = IntelligenceTradingIntegration()
    return manager.get_intelligence_statistics()


def get_best_intelligence_sources(min_count: int = 3) -> List[Dict]:
    """获取最佳情报来源API"""
    manager = IntelligenceTradingIntegration()
    return manager.get_best_sources(min_count)