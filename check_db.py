import sqlite3
conn = sqlite3.connect('trading.db')
cursor = conn.cursor()

# 检查表
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
print('Tables:', [r[0] for r in cursor.fetchall()])

# 检查交易数
cursor.execute("SELECT COUNT(*) FROM trades")
print('Total trades:', cursor.fetchone()[0])

cursor.execute("SELECT COUNT(*) FROM trades WHERE status='completed'")
print('Completed trades:', cursor.fetchone()[0])

# 检查复盘数
try:
    cursor.execute("SELECT COUNT(*) FROM trade_reviews")
    print('Total reviews:', cursor.fetchone()[0])
except Exception as e:
    print(f'trade_reviews error: {e}')

conn.close()