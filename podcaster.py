import database
from datetime import datetime
import os
import re
from dotenv import load_dotenv
import azure.cognitiveservices.speech as speechsdk
import boto3

S3_BUCKET_NAME = 'ai-news-podcast-output-andy-1102'
BYTE_LIMIT = 15000

def setup_gcp_credentials(): # 雖然改用Azure，但這個函數的設計模式很好，保留下來，萬一以後要用
    gcp_json_content = os.getenv("GCP_CREDENTIALS_JSON")
    if gcp_json_content:
        temp_credentials_path = "gcp_credentials_temp.json"
        with open(temp_credentials_path, "w") as f:
            f.write(gcp_json_content)
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = temp_credentials_path
        print("已從環境變數載入 GCP 憑證。")

def upload_to_s3(file_path, bucket_name, object_name):
    # (與 analyzer.py 中的函數相同)
    s3_client = boto3.client('s3')
    try:
        s3_client.upload_file(file_path, bucket_name, object_name)
        print(f"檔案已成功上傳至 S3: s3://{bucket_name}/{object_name}")
        return True
    except Exception as e:
        print(f"S3 上傳失敗: {e}")
        return False

def create_text_chunks(text):
    chunks, current_chunk = [], ""
    sentences = text.replace('\n', '。').replace('！', '。').replace('？', '。').split('。')
    for sentence in sentences:
        if not sentence: continue
        sentence_with_period = sentence + "。"
        if len((current_chunk + sentence_with_period).encode('utf-8')) > BYTE_LIMIT:
            if current_chunk: chunks.append(current_chunk)
            current_chunk = sentence_with_period
        else:
            current_chunk += sentence_with_period
    if current_chunk: chunks.append(current_chunk)
    return chunks

def main():
    load_dotenv()
    
    print("--- AI 播音員 (Azure 版) 啟動 ---")
    latest_summary = database.get_latest_summary()
    if not latest_summary:
        print("錯誤：資料庫中找不到任何分析報告。"); return
    summary_text = latest_summary['summary_text']
    print("成功讀取報告，準備進行語音合成...")

    cleaned_text = re.sub(r'#+\s*', '', summary_text).replace('**', '').replace('*', '').replace('---', '')

    speech_key = os.getenv("AZURE_SPEECH_KEY")
    speech_region = os.getenv("AZURE_SPEECH_REGION")
    if not all([speech_key, speech_region]):
        print("錯誤：缺少 AZURE_SPEECH_KEY 或 AZURE_SPEECH_REGION 環境變數。"); return

    file_timestamp = datetime.now().strftime('%Y%m%d_%H')
    filename = f"podcast_{file_timestamp}.mp3"
    
    speech_config = speechsdk.SpeechConfig(subscription=speech_key, region=speech_region)
    audio_config = speechsdk.audio.AudioOutputConfig(filename=filename)
    voice_name = "zh-TW-YunJheNeural"
    speech_config.speech_synthesis_voice_name = voice_name
    speech_synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=audio_config)

    text_chunks = create_text_chunks(cleaned_text)
    print(f"報告已切分成 {len(text_chunks)} 段落，準備使用聲音 '{voice_name}' 進行合成...")
    for i, chunk in enumerate(text_chunks):
        print(f"  - 正在合成第 {i+1}/{len(text_chunks)} 段語音...")
        result = speech_synthesizer.speak_text_async(chunk).get()
        if result.reason == speechsdk.ResultReason.Canceled:
            cancellation_details = result.cancellation_details
            print(f"語音合成被取消: {cancellation_details.reason}")
            if cancellation_details.reason == speechsdk.CancellationReason.Error:
                print(f"錯誤詳情: {cancellation_details.error_details}")
            return
    
    print("\n所有段落語音合成完畢！")
    
    upload_to_s3(filename, S3_BUCKET_NAME, f"podcasts/{filename}")
    os.remove(filename)

if __name__ == "__main__":
    main()