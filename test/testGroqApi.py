import os
import time
from groq import Groq

# 1. あなたのAPIキーをここに貼り付けます
GROQ_API_KEY = ""

# クライアントの初期化
client = Groq(api_key=GROQ_API_KEY)

try:
    # 2. モデルを指定してリクエストを送信
    completion = client.chat.completions.create(
        model="llama-3.1-8b-instant",  # ここでモデルを指定します
        messages=[
            {
                "role": "user",
                "content": "社会シミュレーション用の架空の人物プロフィールをJSON形式で1件作ってください。項目は、id, name, age, occupation です。"
            }
        ],
        temperature=0.7,
        # レスポンスを確実なJSON形式にする設定
        response_format={"type": "json_object"} 
    )

    # 結果を表示
    print("--- API接続成功！ ---")
    print(completion.choices[0].message.content)

except Exception as e:
    print("--- エラーが発生しました ---")
    print(e)