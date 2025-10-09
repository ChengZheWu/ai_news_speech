# 導入我們自己的 database 模組
import database

# 導入其他必要的函式庫
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import time
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, timezone
import re
import requests
import sys # 導入 sys 模組來終止程式

# --- [全域常數] ---
HOURS_TO_FETCH = 12
SCROLLING_MAX_RETRIES = 3 # 滾動失敗時，最多重試幾次
RETRY_DELAY_SECONDS = 10

# --- [函數定義區] ---

def parse_yahoo_time(time_str, time_now):
    """
    解析 Yahoo 的相對時間字串。
    此函數現在只在「智慧滾動」時用來做快速、概略的時間判斷。
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
    抓取精確時間和內文。如果失敗，則直接返回 None, None 來觸發主程式的錯誤處理。
    """
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36'}
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        publish_time = None
        content = ""

        # 抓取精確時間 (通常在 <time> 標籤的 datetime 屬性中)
        time_tag = soup.select_one('time[datetime]')
        if time_tag:
            iso_timestamp = time_tag['datetime']
            # fromisoformat 會直接把標準 ISO 格式轉成有時區的 datetime 物件
            # Z 代表 UTC+0，我們把它轉成 +00:00 讓 Python 能解析
            publish_time = datetime.fromisoformat(iso_timestamp.replace('Z', '+00:00'))

        # 抓取內文
        article_body = soup.select_one('article')
        if article_body:
            paragraphs = [p.text for p in article_body.find_all('p')]
            content = "\n".join(paragraphs)

        # 只要有一項沒抓到，就視為失敗
        if not publish_time or not content:
            print(f"  [FATAL] 內容或時間抓取不完整: {url}")
            return None, None
            
        return publish_time, content

    except requests.exceptions.RequestException as e:
        print(f"  [錯誤] 抓取頁面失敗: {url}, 原因: {e}")
        return None, None

def main():
    # 確保資料庫結構存在並清空舊資料
    database.setup_database()
    database.clear_all_data()

    # 在程式一開始，就定義一個統一的、帶有時區的「現在時間」基準點
    now_utc = datetime.now(timezone.utc)
    print(f"目前統一時間基準 (UTC): {now_utc.strftime('%Y-%m-%d %H:%M:%S')}")

    page_source = None

    print(f"啟動情報員，目標鎖定過去 {HOURS_TO_FETCH} 小時的新聞...")

    for attempt in range(SCROLLING_MAX_RETRIES):
        print(f"\n--- 開始第 {attempt + 1}/{SCROLLING_MAX_RETRIES} 次滾動嘗試 ---")
        driver = None
        scrolling_successful = False
        try:
            # --- [啟動無頭模式] ---
            chrome_options = Options()
            # "--headless=new" 是 Selenium 4 之後啟動無頭模式的標準寫法
            chrome_options.add_argument("--headless=new")
            # 以下參數是為了在 Docker/Linux 環境中增加穩定性，避免權限問題
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu") # 在無頭環境下，通常建議關閉 GPU 加速
            
            # 將設定好的 options 傳給 Chrome
            driver = webdriver.Chrome(options=chrome_options)
        except Exception as e:
            print(f"啟動 Selenium 失敗: {e}")
            return

        try:
            url = 'https://tw.stock.yahoo.com/tw-market'
            driver.get(url)
            time.sleep(3)

            # 智慧滾動邏輯 (現在也使用 UTC 基準)
            print("開始智慧滾動...")
            # 滾動用的時間窗口，也從 now_utc 計算
            time_window = now_utc - timedelta(hours=HOURS_TO_FETCH)
            last_height = driver.execute_script("return document.body.scrollHeight")
            while True:
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(10)
                new_height = driver.execute_script("return document.body.scrollHeight")
                
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
                                    # parse_yahoo_time 回傳的時間也會是 UTC aware
                                    last_news_time = parse_yahoo_time(text, now_utc)
                                    break
                        if last_news_time:
                            break
                
                if last_news_time and last_news_time < time_window:
                    print(f"偵測到最舊新聞已超出 {HOURS_TO_FETCH} 小時範圍，停止滾動。")
                    scrolling_successful = True
                    break
                
                if new_height == last_height:
                    print("已達頁面底部，進行最終條件檢查...")

                    # 取得當前頁面上所有新聞的列表
                    final_news_items = temp_soup.select('#YDC-Stream-Proxy li')
                    article_count = len(final_news_items)

                    # 取得最舊與最新的新聞時間
                    oldest_time = last_news_time # last_news_time 是我們在迴圈中持續更新的最舊時間
                    newest_time = None
                    
                    # 從頭部開始尋找，找到的第一個就是最新的時間
                    for item in final_news_items:
                        h3_tag = item.select_one('h3 a')
                        if h3_tag:
                            time_div = h3_tag.find_parent('h3').find_previous_sibling('div')
                            if time_div:
                                for span in time_div.find_all('span'):
                                    text = span.text.strip()
                                    if any(kw in text for kw in ['前', '小時', '分鐘', '昨天']):
                                        newest_time = parse_yahoo_time(text, now_utc)
                                        break # 找到第一個就跳出
                            if newest_time: break
                    
                    # 計算時間跨度 (小時)
                    time_span_hours = 0
                    if newest_time and oldest_time:
                        time_span_hours = (newest_time - oldest_time).total_seconds() / 3600

                    # 應用你的新條件來判斷是否真的失敗
                    # 如果文章數少於20篇 且 時間跨度小於(HOURS_TO_FETCH / 2)小時，才視為滾動失敗
                    if article_count < 20 and time_span_hours < (HOURS_TO_FETCH // 2):
                        print(f"滾動失敗：已達頁面底部，但條件不滿足 (文章數: {article_count}/20, 時間跨度: {time_span_hours:.2f}/6 小時)。")
                        # scrolling_successful 保持為 False
                    else:
                        print(f"滾動成功：雖未達12小時，但文章數({article_count})及時間跨度({time_span_hours:.2f}小時)滿足最低要求，視為正常。")
                        scrolling_successful = True # 滿足條件，視為成功
                    
                    break # 無論判斷結果如何，都結束滾
                last_height = new_height
            
            if scrolling_successful:
                print("\n滾動完畢，擷取最終 HTML 原始碼！")
                page_source = driver.page_source
                break # 成功，跳出重試迴圈
        except Exception as e:
            print(f"滾動時發生嚴重錯誤: {e}")
        finally:
            if driver:
                driver.quit()
        
        if attempt < SCROLLING_MAX_RETRIES - 1:
            print(f"將在 {RETRY_DELAY_SECONDS} 秒後重試滾動...")
            time.sleep(RETRY_DELAY_SECONDS)

    if not page_source:
        print("\n[FATAL ERROR] 所有滾動嘗試均失敗，無法獲取頁面內容。程式終止。")
        sys.exit(1) # 使用非 0 的 exit code 代表錯誤

    print("\n開始分析與抓取詳細內容...")
    # 3. 處理資料：使用統一的 UTC 時間基準進行精準過濾
    soup = BeautifulSoup(page_source, 'html.parser')
    news_to_process = []
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

        if not publish_time or not content:
            print(f"\n[FATAL ERROR] 無法抓取文章 '{news['headline']}' 的完整內容。程式終止。")
            sys.exit(1) # 報錯，終止整個腳本
        
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
    if new_articles_count == 0:
        print(f"[FATAL ERROR] 處理了 {len(news_to_process)} 個目標，但沒有任何一篇符合條件或為新文章。可能出現問題，程式終止。")
        sys.exit(1)
    print(f"✔️ 本次新增 {new_articles_count} 篇符合精準時間的新文章到知識庫。")

# --- [程式總開關] ---
if __name__ == "__main__":
    main()