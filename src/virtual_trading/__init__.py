"""
虚拟交易模块 - 谷子情报系统
提供资金管理、虚拟下注、结果记录、统计分析和数据展示功能
"""

import sqlite3
import os
import json
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, Any
import logging

class VirtualTradingManager:
    """虚拟交易管理器"""
    
    def __init__(self, db_path: str = "D:\\work\\research\\guzi-decision\\trading.db"):
        self.db_path = db_path
        self.init_database()
        self.logger = logging.getLogger(__name__)
        
    def init_database(self):
        """初始化数据库表结构"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 创建资金账户表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                balance REAL NOT NULL DEFAULT 10000.0,
                initial_balance REAL NOT NULL DEFAULT 10000.0,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 创建交易记录表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                direction TEXT NOT NULL CHECK(direction IN ('bullish', 'bearish')),
                amount REAL NOT NULL,
                expected_time TIMESTAMP NOT NULL,
                intelligence_source TEXT NOT NULL,
                reason TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending', 'completed', 'cancelled')),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP
            )
        ''')
        
        # 创建交易结果表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trade_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trade_id INTEGER NOT NULL,
                actual_direction TEXT NOT NULL CHECK(actual_direction IN ('up', 'down', 'unchanged')),
                profit_loss REAL NOT NULL,
                return_rate REAL NOT NULL,
                verified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (trade_id) REFERENCES trades (id) ON DELETE CASCADE
            )
        ''')
        
        # 初始化默认账户（如果不存在）
        cursor.execute('SELECT COUNT(*) FROM accounts')
        if cursor.fetchone()[0] == 0:
            cursor.execute('INSERT INTO accounts (balance, initial_balance) VALUES (10000.0, 10000.0)')
        
        conn.commit()
        conn.close()
    
    def get_account_balance(self) -> float:
        """获取当前账户余额"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT balance FROM accounts ORDER BY id DESC LIMIT 1')
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else 10000.0
    
    def reset_account(self, initial_balance: float = 10000.0) -> bool:
        """重置账户资金"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('INSERT INTO accounts (balance, initial_balance) VALUES (?, ?)', 
                         (initial_balance, initial_balance))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            self.logger.error(f"Failed to reset account: {e}")
            return False
    
    def add_funds(self, amount: float) -> bool:
        """充值资金"""
        if amount <= 0:
            return False
        
        try:
            current_balance = self.get_account_balance()
            new_balance = current_balance + amount
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('INSERT INTO accounts (balance, initial_balance) VALUES (?, ?)', 
                         (new_balance, self.get_initial_balance()))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            self.logger.error(f"Failed to add funds: {e}")
            return False
    
    def get_initial_balance(self) -> float:
        """获取初始资金"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT initial_balance FROM accounts ORDER BY id DESC LIMIT 1')
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else 10000.0
    
    def place_bet(self, symbol: str, direction: str, amount: float, 
                  expected_time: str, intelligence_source: str, reason: str) -> int:
        """放置虚拟下注"""
        if amount <= 0:
            raise ValueError("Amount must be positive")
        
        if direction not in ['bullish', 'bearish']:
            raise ValueError("Direction must be 'bullish' or 'bearish'")
        
        current_balance = self.get_account_balance()
        if amount > current_balance:
            raise ValueError("Insufficient funds")
        
        # 扣除资金
        new_balance = current_balance - amount
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('INSERT INTO accounts (balance, initial_balance) VALUES (?, ?)', 
                     (new_balance, self.get_initial_balance()))
        
        # 记录交易
        cursor.execute('''
            INSERT INTO trades (symbol, direction, amount, expected_time, intelligence_source, reason)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (symbol, direction, amount, expected_time, intelligence_source, reason))
        
        trade_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return trade_id
    
    def record_result(self, trade_id: int, actual_direction: str, 
                     profit_loss: float, return_rate: float) -> bool:
        """记录交易结果"""
        if actual_direction not in ['up', 'down', 'unchanged']:
            raise ValueError("Actual direction must be 'up', 'down', or 'unchanged'")
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 检查交易是否存在且状态为pending
            cursor.execute('SELECT amount, status FROM trades WHERE id = ?', (trade_id,))
            result = cursor.fetchone()
            if not result or result[1] != 'pending':
                conn.close()
                return False
            
            # 记录结果
            cursor.execute('''
                INSERT INTO trade_results (trade_id, actual_direction, profit_loss, return_rate)
                VALUES (?, ?, ?, ?)
            ''', (trade_id, actual_direction, profit_loss, return_rate))
            
            # 更新交易状态
            cursor.execute('UPDATE trades SET status = "completed", completed_at = CURRENT_TIMESTAMP WHERE id = ?', 
                         (trade_id,))
            
            # 更新账户余额
            current_balance = self.get_account_balance()
            new_balance = current_balance + profit_loss
            cursor.execute('INSERT INTO accounts (balance, initial_balance) VALUES (?, ?)', 
                         (new_balance, self.get_initial_balance()))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            self.logger.error(f"Failed to record result: {e}")
            return False
    
    def get_trade_history(self, limit: int = 100) -> List[Dict]:
        """获取交易历史"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT t.*, tr.actual_direction, tr.profit_loss, tr.return_rate, tr.verified_at
            FROM trades t
            LEFT JOIN trade_results tr ON t.id = tr.trade_id
            ORDER BY t.created_at DESC
            LIMIT ?
        ''', (limit,))
        
        columns = [description[0] for description in cursor.description]
        results = []
        for row in cursor.fetchall():
            trade_dict = dict(zip(columns, row))
            results.append(trade_dict)
        
        conn.close()
        return results
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计分析数据"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 总收益
        cursor.execute('SELECT SUM(profit_loss) FROM trade_results')
        total_profit = cursor.fetchone()[0] or 0.0
        
        # 总交易数
        cursor.execute('SELECT COUNT(*) FROM trades WHERE status = "completed"')
        total_trades = cursor.fetchone()[0] or 0
        
        # 胜率
        cursor.execute('''
            SELECT COUNT(*) 
            FROM trade_results tr
            JOIN trades t ON tr.trade_id = t.id
            WHERE 
                (t.direction = 'bullish' AND tr.actual_direction = 'up' AND tr.profit_loss > 0) OR
                (t.direction = 'bearish' AND tr.actual_direction = 'down' AND tr.profit_loss > 0)
        ''')
        winning_trades = cursor.fetchone()[0] or 0
        
        win_rate = winning_trades / total_trades if total_trades > 0 else 0.0
        
        # 平均收益率
        cursor.execute('SELECT AVG(return_rate) FROM trade_results')
        avg_return_rate = cursor.fetchone()[0] or 0.0
        
        # 按情报来源统计
        cursor.execute('''
            SELECT intelligence_source, COUNT(*) as count, AVG(return_rate) as avg_return
            FROM trades t
            JOIN trade_results tr ON t.id = tr.trade_id
            GROUP BY intelligence_source
        ''')
        source_stats = []
        for row in cursor.fetchall():
            source_stats.append({
                'source': row[0],
                'count': row[1],
                'avg_return': row[2] or 0.0
            })
        
        # 按标的统计
        cursor.execute('''
            SELECT symbol, COUNT(*) as count, AVG(return_rate) as avg_return
            FROM trades t
            JOIN trade_results tr ON t.id = tr.trade_id
            GROUP BY symbol
        ''')
        symbol_stats = []
        for row in cursor.fetchall():
            symbol_stats.append({
                'symbol': row[0],
                'count': row[1],
                'avg_return': row[2] or 0.0
            })
        
        conn.close()
        
        return {
            'total_profit': total_profit,
            'total_trades': total_trades,
            'win_rate': win_rate,
            'avg_return_rate': avg_return_rate,
            'source_statistics': source_stats,
            'symbol_statistics': symbol_stats,
            'current_balance': self.get_account_balance(),
            'initial_balance': self.get_initial_balance()
        }
    
    def get_pnl_curve_data(self) -> List[Dict]:
        """获取收益曲线数据"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 获取所有账户余额变化
        cursor.execute('''
            SELECT balance, last_updated
            FROM accounts
            ORDER BY last_updated
        ''')
        balance_data = []
        for row in cursor.fetchall():
            balance_data.append({
                'balance': row[0],
                'timestamp': row[1]
            })
        
        conn.close()
        return balance_data


# API接口函数
def create_virtual_trading_manager() -> VirtualTradingManager:
    """创建虚拟交易管理器实例"""
    return VirtualTradingManager()


def get_account_info() -> Dict[str, float]:
    """获取账户信息API"""
    manager = VirtualTradingManager()
    return {
        'current_balance': manager.get_account_balance(),
        'initial_balance': manager.get_initial_balance()
    }


def place_virtual_bet(symbol: str, direction: str, amount: float, 
                     expected_time: str, intelligence_source: str, reason: str, 
                     intelligence_id: Optional[int] = None) -> Dict:
    """放置虚拟下注API"""
    manager = VirtualTradingManager()
    try:
        # 如果提供了情报ID，在reason中包含它
        if intelligence_id is not None:
            reason_with_id = f"{reason} [INT:{intelligence_id}]"
        else:
            reason_with_id = reason
            
        trade_id = manager.place_bet(symbol, direction, amount, expected_time, intelligence_source, reason_with_id)
        return {
            'success': True,
            'trade_id': trade_id,
            'message': 'Bet placed successfully'
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


def record_trade_result(trade_id: int, actual_direction: str, 
                       profit_loss: float, return_rate: float) -> Dict:
    """记录交易结果API"""
    manager = VirtualTradingManager()
    success = manager.record_result(trade_id, actual_direction, profit_loss, return_rate)
    return {
        'success': success,
        'message': 'Result recorded successfully' if success else 'Failed to record result'
    }


def get_trading_statistics() -> Dict:
    """获取交易统计API"""
    manager = VirtualTradingManager()
    return manager.get_statistics()


def get_trading_history(limit: int = 100) -> List[Dict]:
    """获取交易历史API"""
    manager = VirtualTradingManager()
    return manager.get_trade_history(limit)


def reset_trading_account(initial_balance: float = 10000.0) -> Dict:
    """重置交易账户API"""
    manager = VirtualTradingManager()
    success = manager.reset_account(initial_balance)
    return {
        'success': success,
        'message': 'Account reset successfully' if success else 'Failed to reset account'
    }


def add_trading_funds(amount: float) -> Dict:
    """添加交易资金API"""
    manager = VirtualTradingManager()
    success = manager.add_funds(amount)
    return {
        'success': success,
        'message': 'Funds added successfully' if success else 'Failed to add funds'
    }


def get_pnl_curve() -> List[Dict]:
    """获取收益曲线API"""
    manager = VirtualTradingManager()
    return manager.get_pnl_curve_data()

# 导出 router
from .routes import router