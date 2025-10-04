# 導入我們自己的 database 模組
import database

# 導入其他必要的函式庫
from selenium import webdriver
import time
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, timezone
import re
import requests

# --- [全域常數] ---
HOURS_TO_FETCH = 12

# --- [函數定義區] ---

def parse_yahoo_time(time_str, time_now):
    """
    解析 Yahoo 的相對時間字串。
    [注意] 此函數現在只在「智慧滾動」時用來做快速、概略的時間判斷。
    """
    if '前' in time_str:
        match = re.search(r'\d+', time_str)
        if not match:
            return time_now
        num = int(match.group(0))
        if '天' in time_str:
            return time_now - timedelta(days=num)
        if '小時' in time_str:
            return time_now - timedelta(hours=num)
        if '分鐘' in time_str:
            return time_now - timedelta(minutes=num)
    if '昨天' in time_str:
        return time_now - timedelta(days=1)
    return None

def scrape_article_details(url):
    """
    技能升級！潛入新聞頁面，抓取精確時間和內文。
    返回一個包含 (datetime 物件, 內文) 的元組 (tuple)。
    """
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36'}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        publish_time = None
        content = "內文抓取失敗或格式不符。"

        # 1. 抓取精確時間 (通常在 <time> 標籤的 datetime 屬性中)
        time_tag = soup.select_one('time[datetime]')
        if time_tag:
            iso_timestamp = time_tag['datetime']
            # fromisoformat 會直接把標準 ISO 格式轉成有時區的 datetime 物件
            # Z 代表 UTC+0，我們把它轉成 +00:00 讓 Python 能解析
            publish_time = datetime.fromisoformat(iso_timestamp.replace('Z', '+00:00'))

        # 2. 抓取內文
        article_body = soup.select_one('div.caas-body')
        if article_body:
            paragraphs = [p.text for p in article_body.find_all('p')]
            content = "\n".join(paragraphs)
            
        return publish_time, content

    except requests.exceptions.RequestException as e:
        print(f"  [錯誤] 抓取頁面失敗: {url}, 原因: {e}")
        return None, None

def main():
    """主執行函數 (統一時區版)"""
    database.setup_database()

    # 清空上一次運行的所有舊資料
    database.clear_all_data()

    print(f"啟動情報員，目標鎖定過去 {HOURS_TO_FETCH} 小時的新聞...")
    try:
        driver = webdriver.Chrome()
    except Exception as e:
        print(f"啟動 Selenium 失敗: {e}")
        return

    # --- [核心修正點] ---
    # 在程式一開始，就定義一個統一的、帶有時區的「現在時間」基準點
    now_utc = datetime.now(timezone.utc)
    print(f"目前統一時間基準 (UTC): {now_utc.strftime('%Y-%m-%d %H:%M:%S')}")
    # --- 修正完畢 ---

    url = 'https://tw.stock.yahoo.com/tw-market'
    driver.get(url)
    time.sleep(3)

    # 2. 智慧滾動邏輯 (現在也使用 UTC 基準)
    print("開始智慧滾動...")
    # 滾動用的時間窗口，也從 now_utc 計算
    time_window = now_utc - timedelta(hours=HOURS_TO_FETCH)
    last_height = driver.execute_script("return document.body.scrollHeight")
    while True:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(10)
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            print("已達頁面底部，停止滾動。")
            break
        last_height = new_height
        
        temp_soup = BeautifulSoup(driver.page_source, 'html.parser')
        news_items = temp_soup.select('#YDC-Stream-Proxy li')
        last_news_time = None
        for item in reversed(news_items):
            h3_tag = item.select_one('h3 a')
            if h3_tag:
                time_div = h3_tag.find_parent('h3').find_previous_sibling('div')
                if time_div:
                    for span in time_div.find_all('span'):
                        text = span.text.strip()
                        if any(kw in text for kw in ['前', '小時', '分鐘', '昨天']):
                            # 將 UTC 基準時間傳給 parse_yahoo_time
                            # 注意：parse_yahoo_time 回傳的時間也會是 UTC aware
                            last_news_time = parse_yahoo_time(text, now_utc)
                            break
                if last_news_time:
                    break
        
        if last_news_time and last_news_time < time_window:
            print("偵測到最舊新聞已超出8小時範圍，停止滾動。")
            break

    print("\n滾動完畢，擷取最終 HTML 原始碼！")
    page_source = driver.page_source
    driver.quit()

    # 3. 處理資料：使用統一的 UTC 時間基準進行精準過濾
    soup = BeautifulSoup(page_source, 'html.parser')
    
    news_to_process = []
    # ... (收集 URL 和標題的邏輯不變) ...
    for item in soup.select('#YDC-Stream-Proxy li'):
        headline_tag = item.select_one('h3 a')
        if headline_tag and headline_tag.get('href'):
            url = headline_tag.get('href')
            if not url.startswith('http'):
                url = "https://tw.stock.yahoo.com" + url
            news_to_process.append({
                "headline": headline_tag.text.strip(),
                "url": url
            })

    print(f"\n列表分析完成，共 {len(news_to_process)} 個目標。開始逐一潛入進行精準時間過濾...")
    
    # 精準過濾的時間窗口，也從同一個 time_window 計算
    new_articles_count = 0
    
    for news in news_to_process:
        publish_time, content = scrape_article_details(news['url'])
        
        # 這裡現在是兩個 aware time 在做比較，非常精準
        if publish_time and content and publish_time >= time_window:
            article_data = {
                "headline": news['headline'],
                "url": news['url'],
                "time_str": publish_time.strftime('%Y-%m-%d %H:%M:%S %Z'),
                "datetime": publish_time,
                "content": content
            }
            formatted_time = article_data['datetime'].strftime('%Y-%m-%d %H:%M')
            print(f"Time:{formatted_time}\nheadline:{article_data['headline']}")
            if database.add_article(article_data):
                new_articles_count += 1
    
    # ... (最終任務報告邏輯不變) ...
    print("\n--- 任務報告 ---")
    print(f"所有目標處理完畢！")
    print(f"✔️ 本次新增 {new_articles_count} 篇符合精準時間的新文章到知識庫。")

# --- [程式總開關] ---
if __name__ == "__main__":
    main()