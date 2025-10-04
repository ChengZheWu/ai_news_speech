import database
import google.generativeai as genai
import textwrap
from datetime import datetime
import os # 導入 os 模組來處理資料夾
from dotenv import load_dotenv

# --- [設定] ---

# 我們要分析過去幾小時的新聞
HOURS_TO_ANALYZE = 12

def main():
    # 1. 載入 .env 檔案中的環境變數
    load_dotenv()
    
    # 2. 從環境變數中讀取 API Key
    api_key = os.getenv("GOOGLE_API_KEY")
    
    # 3. 檢查是否成功讀取到 Key
    if not api_key:
        print("錯誤：找不到 GOOGLE_API_KEY。請確認你的專案底下有 .env 檔案，並且裡面有 GOOGLE_API_KEY='...' 的設定。")
        return

    """AI 分析師的主程式"""
    # 1. 設定 AI 熱線
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-flash-latest')
    except Exception as e:
        print(f"AI 設定失敗，請檢查你的 API Key 是否正確。錯誤訊息: {e}")
        return

    print(f"AI 分析師已上線，正在從知識庫調閱過去 {HOURS_TO_ANALYZE} 小時的情報...")

    # 2. 從圖書館借書 (讀取資料庫)
    articles = database.get_all_articles_for_analysis()

    if not articles:
        print("知識庫中沒有符合時間範圍的新聞可供分析。")
        return

    print(f"成功調閱 {len(articles)} 篇新聞，正在整理成報告...")

    # 3. 把所有書的內容整理成一份報告 (合併內文)
    full_text_content = ""
    for article in articles:
        full_text_content += f"--- 新聞標題: {article['headline']} ---\n"
        full_text_content += f"{article['content']}\n\n"

    # 4. 擬定簡報指南 (設計 Prompt)
    prompt = f"""
    你是一位頂尖的台灣股市財經分析師。你的任務是閱讀以下所有從網路爬取來的過去 {HOURS_TO_ANALYZE} 小時內的財經新聞。

    ---
    寫作規則:
    撰寫一份**目標長度約為3000個繁體中文字，不要超過5000個繁體中文字**的專業分析報告。
    請不要在報告中包含任何關於「報告撰寫」、「數據基礎」或「撰寫日期」的欄位。
    你的報告應該直接從主標題或「摘要」開始。
    有日期的話，請用中文格式，例如:10月16號，不要寫10/16。
    不要出現沒必要的重複翻譯中文的英文。
    請在文章的最後一句話寫"本文為AI生成重點新聞整理與分析，僅供參考，謝謝收聽"
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

    # 5. 把報告交給 AI 顧問，並等待回覆
    print("報告已發送給 Gemini AI 顧問，請稍候，分析需要一點時間...")
    try:
        response = model.generate_content(prompt)
        ai_summary = response.text

        # 在印出報告之前，先把它存到資料庫！
        print("\n分析完成，正在將報告存入知識庫...")
        database.add_summary(summary_text=ai_summary, source_article_count=len(articles))

        print("正在將報告儲存為 Markdown 檔案...")
        # 建立一個資料夾來存放報告，如果它不存在的話
        output_folder = "reports"
        if not os.path.exists(output_folder):
            os.makedirs(output_folder)
            print(f"已建立新的資料夾: {output_folder}")

        # 產生帶有年月日時分的檔名
        file_timestamp = datetime.now().strftime('%Y%m%d_%H')
        filename = f"summary_{file_timestamp}.md"
        filepath = os.path.join(output_folder, filename)

        # 寫入檔案
        # encoding='utf-8' 非常重要，能確保中文不會變成亂碼
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(ai_summary)
        
        print(f"🎉 報告已成功儲存至: {filepath}")
        
        # 6. 呈現分析結果
        print("\n\n========== Gemini AI 財經摘要報告 ==========\n")
        # 使用 textwrap 美化輸出，避免長文亂碼
        wrapped_text = textwrap.fill(response.text, width=80)
        print(wrapped_text)
        print("\n==================== 報告結束 ====================")
        
    except Exception as e:
        print(f"AI 分析過程中發生錯誤: {e}")


if __name__ == "__main__":
    main()