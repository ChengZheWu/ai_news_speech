# 檔名: run_all.py

import subprocess
import sys
import database

def run_script(script_name):
    """執行一個 Python 腳本，並檢查是否成功。"""
    print(f"\n--- 正在執行 {script_name} ---")
    # sys.executable 會確保我們用的是同一個 venv 環境下的 python.exe
    result = subprocess.run([sys.executable, script_name])
    if result.returncode != 0:
        print(f"!!! 執行 {script_name} 時發生錯誤，中止任務 !!!")
        return False
    print(f"--- {script_name} 執行成功 ---\n")
    return True

def main():
    print("==============================================")
    print("      每日財經 Podcast 自動化專案啟動      ")
    print("==============================================")

    # 步驟零：確保資料庫結構存在並清空舊資料
    database.setup_database()
    database.clear_all_data()
    
    # 步驟一：執行新聞抓取
    if not run_script("news_hunter.py"):
        return # 如果抓取失敗，就直接結束

    # 步驟二：執行 AI 分析與儲存
    if not run_script("analyzer.py"):
        return # 如果分析失敗，就直接結束

    # 步驟三：執行 Podcast 生成
    if not run_script("podcaster.py"):
        return # 如果生成語音失敗，就直接結束
    
    print("--- 所有任務執行完畢，專案成功！ ---")

if __name__ == "__main__":
    main()