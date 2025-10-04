# 檔名: podcaster.py (v1.1 智慧分塊版)

import database
from google.cloud import texttospeech
from datetime import datetime
import os # 導入 os 模組來處理資料夾和路徑
import re # 導入 re 模組來做更強大的文字淨化

# 設定每個文字塊的 byte 上限，我們設 4800 來保留一些安全邊際
BYTE_LIMIT = 4800

def setup_gcp_credentials():
    gcp_json_content = os.getenv("GCP_CREDENTIALS_JSON")
    if gcp_json_content:
        # 如果環境變數存在 (在雲端環境)
        temp_credentials_path = "gcp_credentials_temp.json"
        with open(temp_credentials_path, "w") as f:
            f.write(gcp_json_content)
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = temp_credentials_path
        print("已從環境變數載入 GCP 憑證。")
    # 如果環境變數不存在，程式會依賴本地設定的 set GOOGLE_APPLICATION_CREDENTIALS=...
    # 這讓程式碼在本機和雲端都能運作！

def create_text_chunks(text):
    """將長文本切分成多個小於 byte 上限的塊"""
    chunks = []
    current_chunk = ""
    
    # 我們以句號、換行符、驚嘆號、問號作為斷句的依據
    sentences = text.replace('\n', '。').replace('！', '。').replace('？', '。').split('。')
    
    for sentence in sentences:
        if not sentence:
            continue
        
        sentence_with_period = sentence + "。"
        
        # 檢查加上新句子後是否會超長
        if len((current_chunk + sentence_with_period).encode('utf-8')) > BYTE_LIMIT:
            # 如果會超長，就把目前的塊存起來
            if current_chunk:
                chunks.append(current_chunk)
            # 開始一個新的塊
            current_chunk = sentence_with_period
        else:
            # 如果不會超長，就繼續加到目前的塊
            current_chunk += sentence_with_period
            
    # 別忘了把最後一塊也加進去
    if current_chunk:
        chunks.append(current_chunk)
        
    print(f"報告已成功切分成 {len(chunks)} 個段落進行處理。")
    return chunks

def main():
    setup_gcp_credentials()

    """AI 播音員的主程式"""
    print("--- AI 播音員啟動 ---")
    
    # 1. 讀取最新報告
    print("正在從知識庫讀取最新的財經報告...")
    latest_summary = database.get_latest_summary()

    if not latest_summary:
        print("錯誤：資料庫中找不到任何分析報告。"); return

    summary_text = latest_summary['summary_text']
    print("成功讀取報告，準備進行語音合成...")

    print("正在清除 Markdown 格式，準備純文字講稿...")
    # 移除各級標題符號 (##, ### 等) 和隨後的空格
    cleaned_text = re.sub(r'#+\s*', '', summary_text)
    # 移除粗體、斜體和項目符號的星號
    cleaned_text = cleaned_text.replace('**', '').replace('*', '')
    # 移除分隔線
    cleaned_text = cleaned_text.replace('---', '')

    # 2. 設定 Google Cloud TTS Client (與之前相同)
    try:
        client = texttospeech.TextToSpeechClient()
    except Exception as e:
        print(f"錯誤：無法初始化 TTS 服務。請確認 GOOGLE_APPLICATION_CREDENTIALS 環境變數。詳細錯誤: {e}"); return

    # --- 核心升級：文字分塊與分段合成 ---
    text_chunks = create_text_chunks(cleaned_text)
    all_audio_content = [] # 準備一個列表來收集每一段的語音

    for i, chunk in enumerate(text_chunks):
        print(f"  - 正在合成第 {i+1}/{len(text_chunks)} 段語音...")
        
        synthesis_input = texttospeech.SynthesisInput(text=chunk)
        voice = texttospeech.VoiceSelectionParams(language_code="cmn-TW", name="cmn-TW-Wavenet-A")
        audio_config = texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.MP3, speaking_rate=1.0)

        response = client.synthesize_speech(
            input=synthesis_input, voice=voice, audio_config=audio_config
        )
        all_audio_content.append(response.audio_content)

    print("所有段落語音合成完畢，正在拼接成單一檔案...")

    # 5. 將所有拼接好的音檔儲存成 .mp3
    # 1. 定義輸出資料夾名稱
    output_folder = "podcasts"
    
    # 2. 檢查資料夾是否存在，如果不存在就建立
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
        print(f"已建立新的資料夾: {output_folder}")

    # 3. 產生帶有年月日時分的檔名
    file_timestamp = datetime.now().strftime('%Y%m%d_%H')
    filename = f"podcast_{file_timestamp}.mp3"
    
    # 4. 使用 os.path.join 來組合完整的檔案路徑，這是最標準的作法
    filepath = os.path.join(output_folder, filename)

    # 5. 使用完整的路徑來寫入檔案
    with open(filepath, "wb") as out:
        for audio_segment in all_audio_content:
            out.write(audio_segment)
        # 更新最後的成功訊息，顯示完整的路徑
        print(f"\n🎉 成功！你的專屬財經 Podcast 已儲存為: {filepath}")

if __name__ == "__main__":
    main()