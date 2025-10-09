# 檔名: analyzer.py

import database
import google.generativeai as genai
import textwrap
from datetime import datetime
from zoneinfo import ZoneInfo
import os
from dotenv import load_dotenv
import boto3

S3_BUCKET_NAME = 'ai-news-podcast-output-andy-1102'

def upload_to_s3(file_path, bucket_name, object_name):
    s3_client = boto3.client('s3')
    try:
        s3_client.upload_file(file_path, bucket_name, object_name)
        print(f"檔案已成功上傳至 S3: s3://{bucket_name}/{object_name}")
        return True
    except Exception as e:
        print(f"S3 上傳失敗: {e}")
        return False

def main():
    load_dotenv()
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("錯誤：找不到 GOOGLE_API_KEY 環境變數。"); return

    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-flash-latest')
    except Exception as e:
        print(f"AI 設定失敗: {e}"); return

    print("AI 分析師已上線，正在調閱所有情報...")
    articles = database.get_all_articles_for_analysis()
    if not articles:
        print("知識庫中沒有新聞可供分析。"); return

    print(f"成功調閱 {len(articles)} 篇新聞，正在整理成報告...")
    full_text_content = ""
    for article in articles:
        full_text_content += f"--- 新聞標題: {article['headline']} ---\n{article['content']}\n\n"

    prompt = f"""
    你是一位頂尖的台灣股市財經分析師。你的任務是閱讀以下所有從網路爬取來的財經新聞。

    ---
    寫作規則:
    撰寫一份**目標長度約為3000個繁體中文字，不要超過5000個繁體中文字**的專業分析報告。
    請不要在報告中包含任何關於「報告撰寫」、「數據基礎」或「撰寫日期」的欄位。
    你的報告應該直接從主標題或「摘要」開始。
    有日期的話，請用中文格式，例如:10月16號，不要寫10/16。
    不要出現沒必要的重複翻譯中文的英文。
    請在文章的第一句話寫"大家好，以下為12小時內新聞重點摘要"
    請在文章的最後一句話寫"本集內容由 AI 自動生成，資訊來源為 Yahoo 股市及各大財經媒體，不構成任何投資建議，僅供參考，謝謝收聽"
    ---

    請基於這些資訊，為我提供一份全面、深入的市場動態摘要報告。
    報告段落如下，不要新增或減少段落：
    1.  **摘要與核心觀點**
    2.  **市場概覽**：總結這段時間內市場的整體氣氛和主要指數（如加權指數）的表現。
    3.  **焦點板塊與題材**：哪些產業或概念股是這段時間的市場焦點？為什麼？
    4.  **關鍵公司動態**：提及至少三家在這批新聞中最重要的公司，並說明它們發生了什麼關鍵事件（如財報、法說會、重大消息等）。
    5.  **分析與展望**：綜合所有資訊，提出你對短期市場走勢的專業見解或潛在的觀察重點。

    請確保你的分析完全基於我提供的文本，並以專業、客觀、條理分明的口吻撰寫。

    --- 以下為新聞全文 ---
    {full_text_content}
    """
    
    print("報告已發送給 Gemini AI，分析需要一點時間...")
    try:
        response = model.generate_content(prompt)
        ai_summary = response.text
        
        print("\n分析完成，正在將報告存入知識庫...")
        database.add_summary(summary_text=ai_summary, source_article_count=len(articles))
        
        # 產出 .md 檔案並上傳到 S3
        tz_taipei = ZoneInfo("Asia/Taipei")
        file_timestamp = datetime.now(tz_taipei).strftime('%Y%m%d_%H')
        filename = f"summary_{file_timestamp}.md"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(ai_summary)
        
        upload_to_s3(filename, S3_BUCKET_NAME, f"reports/{filename}")
        os.remove(filename) # 上傳後刪除本地暫存檔

        print("\n\n========== Gemini AI 財經摘要報告 ========== \n")
        print(textwrap.fill(ai_summary.replace('*', ''), width=80))
        print("\n==================== 報告結束 ====================")
    except Exception as e:
        print(f"AI 分析或存檔過程中發生錯誤: {e}")

if __name__ == "__main__":
    main()