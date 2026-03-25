"""
复盘系统 - 谷子情报分析系统
实现交易结果分析、情报源评分和复盘看板功能
"""

import sqlite3
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum
import json
import logging

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.parent


class ReviewStatus(str, Enum):
    """复盘状态"""
    PENDING = "pending"      # 待复盘
    ANALYZED = "analyzed"    # 已分析
    REVIEWED = "reviewed"    # 已人工复盘


class TradeOutcome(str, Enum):
    """交易结果"""
    WIN = "win"              # 盈利
    LOSS = "loss"            # 亏损
    BREAKEVEN = "breakeven"  # 持平


@dataclass
class ReviewRecord:
    """复盘记录"""
    id: Optional[int] = None
    trade_id: int = 0
    intelligence_id: Optional[int] = None
    
    # 情报关联信息
    intelligence_source: str = ""
    intelligence_confidence: float = 0.0
    key_signals: str = ""  # JSON 字符串
    
    # 预测信息
    predicted_direction: str = ""
    predicted_time: str = ""
    predicted_profit: float = 0.0
    
    # 实际结果
    actual_direction: str = ""
    actual_profit: float = 0.0
    actual_time: str = ""
    
    # 偏差分析
    direction_match: bool = False
    time_deviation_hours: float = 0.0
    profit_deviation: float = 0.0
    accuracy_score: float = 0.0
    
    # 复盘字段
    outcome: TradeOutcome = TradeOutcome.BREAKEVEN
    success_reason: str = ""
    failure_reason: str = ""
    improvement_suggestions: str = ""
    
    # 元数据
    status: ReviewStatus = ReviewStatus.PENDING
    reviewed_at: Optional[datetime] = None
    reviewer_notes: str = ""
    
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class IntelligenceSourceScoring:
    """情报源评分系统"""
    
    def __init__(self, db_path: str = None):
        if db_path is None:
            self.db_path = str(PROJECT_ROOT / "trading.db")
        else:
            self.db_path = db_path
        self.init_scoring_tables()
        self.logger = logging.getLogger(__name__)
    
    def init_scoring_tables(self):
        """初始化评分表"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 情报源评分表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS source_scores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_name TEXT NOT NULL UNIQUE,
                total_intelligences INTEGER DEFAULT 0,
                correct_predictions INTEGER DEFAULT 0,
                incorrect_predictions INTEGER DEFAULT 0,
                partial_predictions INTEGER DEFAULT 0,
                total_trades INTEGER DEFAULT 0,
                winning_trades INTEGER DEFAULT 0,
                total_profit REAL DEFAULT 0.0,
                avg_accuracy REAL DEFAULT 0.0,
                avg_profit REAL DEFAULT 0.0,
                weight REAL DEFAULT 1.0,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 情报源历史记录（用于动态调整权重）
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS source_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_name TEXT NOT NULL,
                date DATE NOT NULL,
                intelligences_count INTEGER DEFAULT 0,
                accuracy REAL DEFAULT 0.0,
                profit REAL DEFAULT 0.0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(source_name, date)
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def update_source_score(self, source_name: str):
        """更新情报源评分"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 从 intelligences 表计算统计数据
        cursor.execute('''
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN actual_outcome = 'correct' THEN 1 ELSE 0 END) as correct,
                SUM(CASE WHEN actual_outcome = 'incorrect' THEN 1 ELSE 0 END) as incorrect,
                SUM(CASE WHEN actual_outcome = 'partial' THEN 1 ELSE 0 END) as partial,
                AVG(accuracy_score) as avg_accuracy
            FROM intelligences
            WHERE source = ? AND status = 'verified'
        ''', (source_name,))
        
        intel_stats = cursor.fetchone()
        
        # 从 trades 表计算交易统计
        cursor.execute('''
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN tr.profit_loss > 0 THEN 1 ELSE 0 END) as wins,
                SUM(tr.profit_loss) as total_profit,
                AVG(tr.profit_loss) as avg_profit
            FROM trades t
            JOIN trade_results tr ON t.id = tr.trade_id
            WHERE t.intelligence_source = ?
        ''', (source_name,))
        
        trade_stats = cursor.fetchone()
        
        # Upsert 情报源评分
        cursor.execute('''
            INSERT INTO source_scores (
                source_name, total_intelligences, correct_predictions, 
                incorrect_predictions, partial_predictions,
                total_trades, winning_trades, total_profit, 
                avg_accuracy, avg_profit, last_updated
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(source_name) DO UPDATE SET
                total_intelligences = excluded.total_intelligences,
                correct_predictions = excluded.correct_predictions,
                incorrect_predictions = excluded.incorrect_predictions,
                partial_predictions = excluded.partial_predictions,
                total_trades = excluded.total_trades,
                winning_trades = excluded.winning_trades,
                total_profit = excluded.total_profit,
                avg_accuracy = excluded.avg_accuracy,
                avg_profit = excluded.avg_profit,
                last_updated = CURRENT_TIMESTAMP
        ''', (
            source_name,
            intel_stats[0] or 0,
            intel_stats[1] or 0,
            intel_stats[2] or 0,
            intel_stats[3] or 0,
            trade_stats[0] or 0,
            trade_stats[1] or 0,
            trade_stats[2] or 0.0,
            intel_stats[4] or 0.0,
            trade_stats[3] or 0.0
        ))
        
        conn.commit()
        conn.close()
        
        # 动态调整权重
        self._adjust_source_weight(source_name)
    
    def _adjust_source_weight(self, source_name: str):
        """动态调整情报源权重"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT avg_accuracy, avg_profit, total_intelligences
            FROM source_scores
            WHERE source_name = ?
        ''', (source_name,))
        
        row = cursor.fetchone()
        if not row:
            conn.close()
            return
        
        avg_accuracy, avg_profit, total = row
        
        # 权重计算公式：
        # 基础权重 = 准确率 * 0.6 + 归一化收益 * 0.4
        # 样本数加成 = min(1.0, total / 10)  # 10个样本后达到满加成
        # 最终权重 = 基础权重 * (0.5 + 0.5 * 样本数加成)
        
        normalized_profit = max(-1, min(1, (avg_profit or 0) / 100))  # 归一化到 [-1, 1]
        base_weight = (avg_accuracy or 0) * 0.6 + (normalized_profit + 1) / 2 * 0.4
        sample_bonus = min(1.0, (total or 0) / 10)
        final_weight = base_weight * (0.5 + 0.5 * sample_bonus)
        
        # 确保权重在合理范围内
        final_weight = max(0.1, min(2.0, final_weight))
        
        cursor.execute('''
            UPDATE source_scores SET weight = ? WHERE source_name = ?
        ''', (final_weight, source_name))
        
        conn.commit()
        conn.close()
    
    def get_source_ranking(self, limit: int = 20) -> List[Dict]:
        """获取情报源排名"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT 
                source_name,
                total_intelligences,
                correct_predictions,
                incorrect_predictions,
                partial_predictions,
                total_trades,
                winning_trades,
                total_profit,
                avg_accuracy,
                avg_profit,
                weight,
                last_updated
            FROM source_scores
            WHERE total_intelligences > 0 OR total_trades > 0
            ORDER BY weight DESC, avg_profit DESC
            LIMIT ?
        ''', (limit,))
        
        results = []
        for row in cursor.fetchall():
            total = row[1] or 0
            correct = row[2] or 0
            win_rate = (correct / total * 100) if total > 0 else 0
            
            results.append({
                'source_name': row[0],
                'total_intelligences': total,
                'correct_predictions': correct,
                'incorrect_predictions': row[3] or 0,
                'partial_predictions': row[4] or 0,
                'accuracy_rate': round(win_rate, 2),
                'total_trades': row[5] or 0,
                'winning_trades': row[6] or 0,
                'total_profit': round(row[7] or 0, 2),
                'avg_accuracy': round(row[8] or 0, 4),
                'avg_profit': round(row[9] or 0, 2),
                'weight': round(row[10] or 1.0, 4),
                'last_updated': row[11]
            })
        
        conn.close()
        return results
    
    def record_daily_stats(self):
        """记录每日统计（用于趋势分析）"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        today = datetime.now().date().isoformat()
        
        # 获取所有情报源
        cursor.execute('SELECT DISTINCT source FROM intelligences')
        sources = [row[0] for row in cursor.fetchall()]
        
        for source in sources:
            # 计算今日统计
            cursor.execute('''
                SELECT 
                    COUNT(*) as count,
                    AVG(accuracy_score) as accuracy
                FROM intelligences
                WHERE source = ? 
                AND date(verified_at) = ?
                AND status = 'verified'
            ''', (source, today))
            
            intel_row = cursor.fetchone()
            
            # 今日交易收益
            cursor.execute('''
                SELECT SUM(tr.profit_loss) as profit
                FROM trades t
                JOIN trade_results tr ON t.id = tr.trade_id
                WHERE t.intelligence_source = ?
                AND date(tr.verified_at) = ?
            ''', (source, today))
            
            profit_row = cursor.fetchone()
            
            # Upsert 历史记录
            cursor.execute('''
                INSERT INTO source_history (source_name, date, intelligences_count, accuracy, profit)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(source_name, date) DO UPDATE SET
                    intelligences_count = excluded.intelligences_count,
                    accuracy = excluded.accuracy,
                    profit = excluded.profit
            ''', (source, today, intel_row[0] or 0, intel_row[1] or 0, profit_row[0] or 0))
        
        conn.commit()
        conn.close()


class ReviewManager:
    """复盘管理器"""
    
    def __init__(self, db_path: str = None):
        if db_path is None:
            self.db_path = str(PROJECT_ROOT / "trading.db")
        else:
            self.db_path = db_path
        self.init_review_tables()
        self.source_scoring = IntelligenceSourceScoring(self.db_path)
        self.logger = logging.getLogger(__name__)
    
    def init_review_tables(self):
        """初始化复盘表"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 复盘记录表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trade_reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trade_id INTEGER NOT NULL UNIQUE,
                intelligence_id INTEGER,
                
                -- 情报关联信息
                intelligence_source TEXT,
                intelligence_confidence REAL DEFAULT 0.5,
                key_signals TEXT,
                
                -- 预测信息
                predicted_direction TEXT,
                predicted_time TEXT,
                predicted_profit REAL DEFAULT 0.0,
                
                -- 实际结果
                actual_direction TEXT,
                actual_profit REAL DEFAULT 0.0,
                actual_time TEXT,
                
                -- 偏差分析
                direction_match INTEGER DEFAULT 0,
                time_deviation_hours REAL DEFAULT 0.0,
                profit_deviation REAL DEFAULT 0.0,
                accuracy_score REAL DEFAULT 0.0,
                
                -- 复盘字段
                outcome TEXT DEFAULT 'breakeven',
                success_reason TEXT,
                failure_reason TEXT,
                improvement_suggestions TEXT,
                
                -- 状态
                status TEXT DEFAULT 'pending',
                reviewed_at TIMESTAMP,
                reviewer_notes TEXT,
                
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                
                FOREIGN KEY (trade_id) REFERENCES trades (id) ON DELETE CASCADE,
                FOREIGN KEY (intelligence_id) REFERENCES intelligences (id) ON DELETE SET NULL
            )
        ''')
        
        # 为 trades 表添加复盘相关字段（如果不存在）
        cursor.execute("PRAGMA table_info(trades)")
        columns = [col[1] for col in cursor.fetchall()]
        
        new_columns = {
            'predicted_profit': 'REAL DEFAULT 0.0',
            'key_signals': 'TEXT',
            'success_reason': 'TEXT',
            'failure_reason': 'TEXT',
            'improvement_suggestions': 'TEXT'
        }
        
        for col_name, col_type in new_columns.items():
            if col_name not in columns:
                try:
                    cursor.execute(f'ALTER TABLE trades ADD COLUMN {col_name} {col_type}')
                except Exception as e:
                    self.logger.warning(f"Column {col_name} might already exist: {e}")
        
        conn.commit()
        conn.close()
    
    def create_review_from_trade(self, trade_id: int) -> Optional[int]:
        """从交易创建复盘记录"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 获取交易信息
        cursor.execute('''
            SELECT t.id, t.symbol, t.direction, t.amount, t.expected_time, 
                   t.intelligence_source, t.intelligence_id, t.reason,
                   tr.actual_direction, tr.profit_loss, tr.verified_at
            FROM trades t
            LEFT JOIN trade_results tr ON t.id = tr.trade_id
            WHERE t.id = ? AND t.status = 'completed'
        ''', (trade_id,))
        
        trade = cursor.fetchone()
        if not trade:
            conn.close()
            return None
        
        # 获取情报信息
        intel_confidence = 0.5
        key_signals = "[]"
        
        if trade[6]:  # intelligence_id
            cursor.execute('''
                SELECT confidence, content, direction
                FROM intelligences
                WHERE id = ?
            ''', (trade[6],))
            intel = cursor.fetchone()
            if intel:
                intel_confidence = intel[0] or 0.5
                # 提取关键信号（简化版）
                key_signals = json.dumps([intel[1][:100] if intel[1] else ""])
        
        # 判断结果
        profit_loss = trade[9] or 0
        if profit_loss > 0:
            outcome = 'win'
        elif profit_loss < 0:
            outcome = 'loss'
        else:
            outcome = 'breakeven'
        
        # 计算方向匹配
        trade_direction = trade[2]  # bullish/bearish
        actual_direction = trade[8]  # up/down/unchanged
        direction_match = 0
        
        if trade_direction == 'bullish' and actual_direction == 'up':
            direction_match = 1
        elif trade_direction == 'bearish' and actual_direction == 'down':
            direction_match = 1
        
        # 计算时间偏差
        time_deviation = 0.0
        if trade[4] and trade[10]:
            try:
                expected = datetime.fromisoformat(trade[4].replace('Z', '+00:00'))
                actual = datetime.fromisoformat(trade[10].replace('Z', '+00:00'))
                time_deviation = abs((actual - expected).total_seconds() / 3600)
            except:
                pass
        
        # 计算准确度分数
        accuracy_score = self._calculate_accuracy_score(
            direction_match, profit_loss, trade[3], time_deviation
        )
        
        # 创建复盘记录
        cursor.execute('''
            INSERT INTO trade_reviews (
                trade_id, intelligence_id, intelligence_source, intelligence_confidence,
                key_signals, predicted_direction, predicted_time, predicted_profit,
                actual_direction, actual_profit, actual_time,
                direction_match, time_deviation_hours, profit_deviation, accuracy_score,
                outcome, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'analyzed')
        ''', (
            trade_id, trade[6], trade[5], intel_confidence,
            key_signals, trade[2], trade[4], 0.0,  # predicted_profit 默认为0
            trade[8], profit_loss, trade[10],
            direction_match, time_deviation, 0.0, accuracy_score,
            outcome
        ))
        
        review_id = cursor.lastrowid
        
        # 更新交易表的复盘字段
        self._update_trade_review_fields(cursor, trade_id, outcome, accuracy_score)
        
        # 更新情报源评分
        if trade[5]:
            self.source_scoring.update_source_score(trade[5])
        
        conn.commit()
        conn.close()
        
        self.logger.info(f"Created review #{review_id} for trade #{trade_id}")
        return review_id
    
    def _calculate_accuracy_score(self, direction_match: int, profit_loss: float, 
                                  amount: float, time_deviation: float) -> float:
        """计算准确度分数"""
        score = 0.0
        
        # 方向正确性 (40%)
        score += direction_match * 0.4
        
        # 收益率 (40%)
        if amount > 0:
            return_rate = profit_loss / amount
            normalized_return = max(0, min(1, (return_rate + 1) / 2))  # 归一化到 [0, 1]
            score += normalized_return * 0.4
        
        # 时间准确性 (20%)
        if time_deviation <= 24:
            time_score = 1.0
        elif time_deviation <= 48:
            time_score = 0.7
        elif time_deviation <= 72:
            time_score = 0.4
        else:
            time_score = 0.1
        score += time_score * 0.2
        
        return round(score, 4)
    
    def _update_trade_review_fields(self, cursor, trade_id: int, outcome: str, accuracy: float):
        """更新交易表的复盘字段"""
        # 生成改进建议
        suggestions = self._generate_improvement_suggestions(outcome, accuracy)
        
        cursor.execute('''
            UPDATE trades SET
                success_reason = CASE WHEN ? = 'win' THEN '预测正确，方向匹配' ELSE NULL END,
                failure_reason = CASE WHEN ? = 'loss' THEN '预测错误或时机不佳' ELSE NULL END,
                improvement_suggestions = ?
            WHERE id = ?
        ''', (outcome, outcome, suggestions, trade_id))
    
    def _generate_improvement_suggestions(self, outcome: str, accuracy: float) -> str:
        """生成改进建议"""
        suggestions = []
        
        if outcome == 'win':
            if accuracy >= 0.8:
                suggestions.append("保持当前策略，继续使用该情报源")
            else:
                suggestions.append("虽然盈利，但可优化入场时机")
        elif outcome == 'loss':
            if accuracy < 0.3:
                suggestions.append("重新评估该情报源的可信度")
                suggestions.append("考虑降低该类型情报的仓位")
            else:
                suggestions.append("方向正确但时机不佳，优化入场时间")
        else:
            suggestions.append("分析盈亏平衡原因，寻找优化空间")
        
        return "; ".join(suggestions)
    
    def get_review(self, review_id: int) -> Optional[Dict]:
        """获取复盘详情"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM trade_reviews WHERE id = ?', (review_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            columns = [desc[0] for desc in cursor.description]
            return dict(zip(columns, row))
        return None
    
    def list_reviews(self, status: str = None, limit: int = 100) -> List[Dict]:
        """列出复盘记录"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if status:
            cursor.execute('''
                SELECT * FROM trade_reviews 
                WHERE status = ? 
                ORDER BY created_at DESC 
                LIMIT ?
            ''', (status, limit))
        else:
            cursor.execute('''
                SELECT * FROM trade_reviews 
                ORDER BY created_at DESC 
                LIMIT ?
            ''', (limit,))
        
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        conn.close()
        
        return [dict(zip(columns, row)) for row in rows]
    
    def update_review(self, review_id: int, success_reason: str = None,
                     failure_reason: str = None, improvement_suggestions: str = None,
                     reviewer_notes: str = None) -> bool:
        """更新复盘记录（人工复盘）"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        updates = ['status = "reviewed"', 'reviewed_at = CURRENT_TIMESTAMP', 'updated_at = CURRENT_TIMESTAMP']
        params = []
        
        if success_reason is not None:
            updates.append('success_reason = ?')
            params.append(success_reason)
        if failure_reason is not None:
            updates.append('failure_reason = ?')
            params.append(failure_reason)
        if improvement_suggestions is not None:
            updates.append('improvement_suggestions = ?')
            params.append(improvement_suggestions)
        if reviewer_notes is not None:
            updates.append('reviewer_notes = ?')
            params.append(reviewer_notes)
        
        params.append(review_id)
        
        cursor.execute(f'''
            UPDATE trade_reviews 
            SET {', '.join(updates)}
            WHERE id = ?
        ''', params)
        
        # 同步更新 trades 表
        cursor.execute('''
            UPDATE trades SET
                success_reason = (SELECT success_reason FROM trade_reviews WHERE id = ?),
                failure_reason = (SELECT failure_reason FROM trade_reviews WHERE id = ?),
                improvement_suggestions = (SELECT improvement_suggestions FROM trade_reviews WHERE id = ?)
            WHERE id = (SELECT trade_id FROM trade_reviews WHERE id = ?)
        ''', (review_id, review_id, review_id, review_id))
        
        conn.commit()
        conn.close()
        
        return True
    
    def auto_review_all_pending(self) -> int:
        """自动复盘所有待复盘的交易"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 查找已完成的交易但未复盘的
        cursor.execute('''
            SELECT t.id FROM trades t
            LEFT JOIN trade_reviews tr ON t.id = tr.trade_id
            WHERE t.status = 'completed' AND tr.id IS NULL
        ''')
        
        trade_ids = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        review_count = 0
        for trade_id in trade_ids:
            try:
                self.create_review_from_trade(trade_id)
                review_count += 1
            except Exception as e:
                self.logger.error(f"Failed to create review for trade {trade_id}: {e}")
        
        return review_count


class ReviewDashboard:
    """复盘看板"""
    
    def __init__(self, db_path: str = None):
        if db_path is None:
            self.db_path = str(PROJECT_ROOT / "trading.db")
        else:
            self.db_path = db_path
        self.review_manager = ReviewManager(self.db_path)
        self.source_scoring = IntelligenceSourceScoring(self.db_path)
        self.logger = logging.getLogger(__name__)
    
    def get_overall_performance(self) -> Dict:
        """获取总体表现"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 基本统计
        cursor.execute('SELECT COUNT(*) FROM trade_reviews')
        total_reviews = cursor.fetchone()[0]
        
        cursor.execute('''
            SELECT COUNT(*) FROM trade_reviews 
            WHERE outcome = 'win'
        ''')
        wins = cursor.fetchone()[0]
        
        cursor.execute('''
            SELECT COUNT(*) FROM trade_reviews 
            WHERE outcome = 'loss'
        ''')
        losses = cursor.fetchone()[0]
        
        win_rate = (wins / total_reviews * 100) if total_reviews > 0 else 0
        
        # 收益统计
        cursor.execute('SELECT SUM(actual_profit) FROM trade_reviews')
        total_profit = cursor.fetchone()[0] or 0
        
        cursor.execute('SELECT AVG(actual_profit) FROM trade_reviews')
        avg_profit = cursor.fetchone()[0] or 0
        
        # 最大回撤
        cursor.execute('''
            SELECT actual_profit FROM trade_reviews 
            ORDER BY created_at
        ''')
        profits = [row[0] for row in cursor.fetchall()]
        
        max_drawdown = 0
        peak = 0
        cumulative = 0
        
        for profit in profits:
            cumulative += profit
            if cumulative > peak:
                peak = cumulative
            drawdown = peak - cumulative
            if drawdown > max_drawdown:
                max_drawdown = drawdown
        
        # 平均准确度
        cursor.execute('SELECT AVG(accuracy_score) FROM trade_reviews')
        avg_accuracy = cursor.fetchone()[0] or 0
        
        # 方向预测准确率
        cursor.execute('''
            SELECT AVG(direction_match) FROM trade_reviews
        ''')
        direction_accuracy = cursor.fetchone()[0] or 0
        
        conn.close()
        
        return {
            'total_reviews': total_reviews,
            'wins': wins,
            'losses': losses,
            'breakevens': total_reviews - wins - losses,
            'win_rate': round(win_rate, 2),
            'total_profit': round(total_profit, 2),
            'avg_profit': round(avg_profit, 2),
            'max_drawdown': round(max_drawdown, 2),
            'avg_accuracy': round(avg_accuracy, 4),
            'direction_accuracy': round(direction_accuracy * 100, 2)
        }
    
    def get_source_ranking(self, limit: int = 10) -> List[Dict]:
        """获取情报源排名"""
        return self.source_scoring.get_source_ranking(limit)
    
    def get_recent_reviews(self, limit: int = 20) -> List[Dict]:
        """获取最近复盘"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT 
                tr.id, tr.trade_id, tr.intelligence_source, tr.intelligence_confidence,
                tr.predicted_direction, tr.actual_direction, tr.actual_profit,
                tr.outcome, tr.accuracy_score, tr.improvement_suggestions,
                tr.created_at, t.symbol, t.amount
            FROM trade_reviews tr
            LEFT JOIN trades t ON tr.trade_id = t.id
            ORDER BY tr.created_at DESC
            LIMIT ?
        ''', (limit,))
        
        results = []
        for row in cursor.fetchall():
            results.append({
                'id': row[0],
                'trade_id': row[1],
                'source': row[2],
                'confidence': row[3],
                'predicted_direction': row[4],
                'actual_direction': row[5],
                'profit': row[6],
                'outcome': row[7],
                'accuracy': row[8],
                'suggestions': row[9],
                'created_at': row[10],
                'symbol': row[11],
                'amount': row[12]
            })
        
        conn.close()
        return results
    
    def get_improvement_insights(self) -> List[str]:
        """获取改进建议汇总"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        insights = []
        
        # 分析失败的共同原因
        cursor.execute('''
            SELECT intelligence_source, COUNT(*) as cnt
            FROM trade_reviews
            WHERE outcome = 'loss'
            GROUP BY intelligence_source
            ORDER BY cnt DESC
            LIMIT 3
        ''')
        
        loss_sources = cursor.fetchall()
        if loss_sources:
            sources = [s[0] for s in loss_sources]
            insights.append(f"亏损较多的情报源: {', '.join(sources)}，建议降低权重")
        
        # 分析时间偏差
        cursor.execute('''
            SELECT AVG(time_deviation_hours) FROM trade_reviews
            WHERE outcome = 'loss'
        ''')
        avg_time_dev = cursor.fetchone()[0]
        if avg_time_dev and avg_time_dev > 24:
            insights.append(f"失败交易平均时间偏差 {round(avg_time_dev, 1)} 小时，建议优化入场时机")
        
        # 分析置信度与准确度的关系
        cursor.execute('''
            SELECT AVG(accuracy_score) FROM trade_reviews
            WHERE intelligence_confidence >= 0.7
        ''')
        high_conf_accuracy = cursor.fetchone()[0] or 0
        
        cursor.execute('''
            SELECT AVG(accuracy_score) FROM trade_reviews
            WHERE intelligence_confidence < 0.7
        ''')
        low_conf_accuracy = cursor.fetchone()[0] or 0
        
        if high_conf_accuracy < low_conf_accuracy:
            insights.append("高置信度情报表现反而较差，建议重新校准置信度模型")
        
        # 分析方向预测
        cursor.execute('''
            SELECT predicted_direction, 
                   SUM(direction_match) as correct,
                   COUNT(*) as total
            FROM trade_reviews
            GROUP BY predicted_direction
        ''')
        
        dir_stats = cursor.fetchall()
        for stat in dir_stats:
            direction = stat[0]
            correct = stat[1]
            total = stat[2]
            if total > 0:
                rate = correct / total * 100
                if rate < 50:
                    insights.append(f"{direction} 方向预测准确率仅 {round(rate, 1)}%，需要改进")
        
        conn.close()
        
        if not insights:
            insights.append("当前表现良好，继续保持现有策略")
        
        return insights
    
    def get_dashboard_data(self) -> Dict:
        """获取完整看板数据"""
        return {
            'performance': self.get_overall_performance(),
            'source_ranking': self.get_source_ranking(),
            'recent_reviews': self.get_recent_reviews(),
            'insights': self.get_improvement_insights()
        }


# API 函数
def create_review_system_manager() -> ReviewManager:
    """创建复盘管理器"""
    return ReviewManager()


def create_dashboard() -> ReviewDashboard:
    """创建复盘看板"""
    return ReviewDashboard()


def auto_review_pending_trades() -> Dict:
    """自动复盘待处理交易 API"""
    manager = ReviewManager()
    count = manager.auto_review_all_pending()
    return {
        'success': True,
        'reviewed_count': count,
        'message': f'Automatically reviewed {count} pending trades'
    }


def get_review_dashboard() -> Dict:
    """获取复盘看板数据 API"""
    dashboard = ReviewDashboard()
    return dashboard.get_dashboard_data()


def get_review_list(status: str = None, limit: int = 100) -> List[Dict]:
    """获取复盘列表 API"""
    manager = ReviewManager()
    return manager.list_reviews(status, limit)


def update_review_record(review_id: int, **kwargs) -> Dict:
    """更新复盘记录 API"""
    manager = ReviewManager()
    success = manager.update_review(review_id, **kwargs)
    return {
        'success': success,
        'message': 'Review updated successfully' if success else 'Failed to update review'
    }