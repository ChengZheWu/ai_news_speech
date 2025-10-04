import sqlite3
from datetime import datetime, timedelta

DB_FILE = "news.db"

def setup_database():
    """建立資料庫和 articles、summaries 表格 (如果不存在的話)。"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # 建立 articles 表格的完整指令
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            headline TEXT NOT NULL,
            url TEXT NOT NULL UNIQUE,
            publish_time_str TEXT,
            publish_datetime TEXT,
            content TEXT,
            scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 建立 summaries 表格的完整指令
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS summaries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            summary_text TEXT NOT NULL,
            source_article_count INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()
    print(f"資料庫 '{DB_FILE}' 已準備就緒。")

def add_article(article_data):
    # ... (此函數維持不變) ...
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT OR IGNORE INTO articles (headline, url, publish_time_str, publish_datetime, content)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            article_data['headline'],
            article_data['url'],
            article_data.get('time_str', 'N/A'),
            article_data.get('datetime').isoformat() if article_data.get('datetime') else None,
            article_data.get('content')
        ))
        inserted = cursor.rowcount > 0
        conn.commit()
    except sqlite3.Error as e:
        print(f"資料庫錯誤: {e}")
        inserted = False
    finally:
        conn.close()
    return inserted

def get_all_articles_for_analysis():
    """
    從資料庫讀取「所有」文章以供分析。
    不再進行時間篩選。
    """
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    # 移除了 WHERE 語句，直接選取所有文章
    cursor.execute("SELECT * FROM articles ORDER BY publish_datetime DESC")
    articles = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return articles

def add_summary(summary_text, source_article_count):
    """將一份新的 AI 分析報告存入資料庫"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO summaries (summary_text, source_article_count) VALUES (?, ?)",
            (summary_text, source_article_count)
        )
        conn.commit()
        print("一份新的 AI 分析報告已成功存入知識庫！")
    except sqlite3.Error as e:
        print(f"儲存分析報告時發生資料庫錯誤: {e}")
    finally:
        conn.close()

def get_latest_summary():
    """從資料庫讀取最新的一份分析報告"""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM summaries ORDER BY created_at DESC LIMIT 1")
    latest_summary = cursor.fetchone()
    conn.close()
    if latest_summary:
        return dict(latest_summary)
    return None

def clear_all_data():
    """清空 articles 和 summaries 表格中的所有資料，為下一次運行做準備。"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        # 使用 DELETE FROM 會清空表格內容，但保留表格結構
        cursor.execute("DELETE FROM articles")
        cursor.execute("DELETE FROM summaries")
        conn.commit()
        print(f"資料庫 '{DB_FILE}' 已清空，準備接收新情報。")
    except sqlite3.Error as e:
        print(f"清空資料庫時發生錯誤: {e}")
    finally:
        conn.close()