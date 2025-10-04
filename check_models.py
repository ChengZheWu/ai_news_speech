# 檔名: check_models.py

import google.generativeai as genai

# !!! 在這裡貼上你 analyzer.py 裡面用的同一組 API KEY !!!
GOOGLE_API_KEY = ''

try:
    genai.configure(api_key=GOOGLE_API_KEY)
    
    print("成功連線到 Google AI，正在查詢可用的模型...\n")
    print("--- 您可用的模型列表 (支援 generateContent) ---")
    
    count = 0
    # genai.list_models() 會回傳所有模型
    for m in genai.list_models():
      # 我們只關心支援我們所需功能 (generateContent) 的模型
      if 'generateContent' in m.supported_generation_methods:
        print(m.name)
        count += 1
        
    print(f"\n查詢完畢，共找到 {count} 個可用模型。")
    print("請從上面的列表中，挑選一個模型的名字 (例如 'models/gemini-1.5-flash-latest')，")
    print("然後把它填入 analyzer.py 的 GenerativeModel() 中。")

except Exception as e:
    print(f"查詢失敗，請檢查你的 API Key 是否有效。錯誤訊息: {e}")