import inspect
import json
import os
import time
from datetime import datetime

LOG_PATH = "logs/llm_calls.jsonl"

def _write_log(record):
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
#ログ用


from groq import RateLimitError

from llm.providers import gemini, groq, mistral
from settings import LLM_MODEL, LLM_PROVIDER

PROVIDERS = {
    "groq": groq,
    "mistral": mistral,
    "gemini": gemini,
}

#切り替え先の優先順位リスト（例: groqがダメならmistral、それもダメならgemini）
PROVIDER_ORDER = ["groq","mistral","gemini"]

def ask_llm(system_prompt, user_prompt):
    caller = inspect.currentframe().f_back.f_code.co_name
    #ログ用

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    #最初はconfigで指定されたプロバイダーを試す
    current_provider_name = LLM_PROVIDER
    
    #指定されたプロバイダーから開始して、ダメなら順次切り替えるループ
    start_index = PROVIDER_ORDER.index(current_provider_name) if current_provider_name in PROVIDER_ORDER else 0
    active_orders = PROVIDER_ORDER[start_index:] + PROVIDER_ORDER[:start_index]

    for provider_name in active_orders:
        try:
            provider = PROVIDERS[provider_name]
            model_name = LLM_MODEL[provider_name]
            
            print(f" {provider_name} ({model_name}) で回答を生成中...")
            
            #元々　return provider.chat(messages, model_name)

            start = time.time()
            answer = provider.chat(messages, model_name)
            _write_log({
                "time": datetime.now().isoformat(timespec="seconds"),
                "caller": caller,
                "provider": provider_name,
                "model": model_name,
                "seconds": round(time.time() - start, 1),
                "prompt_chars": len(system_prompt) + len(user_prompt),
                "system_head": system_prompt[:300],
                "response": answer,
            })
            return answer
            #ログ用
            
        except RateLimitError as e:
            print(f"{provider_name} がレートリミット（429）に達しました。次のプロバイダーに切り替えます。")
            _write_log({"time": datetime.now().isoformat(timespec="seconds"), "caller": caller, "provider": provider_name, "error": str(e)})
            #ログ用
            continue  #ループを続行して次のプロバイダーを試す
            
        except Exception as e:
            print(f"{provider_name} で予期せぬエラーが発生しました: {e}")
            #レートリミット以外でも、APIキー不足などで落ちた場合に次へ行くなら continue
            _write_log({"time": datetime.now().isoformat(timespec="seconds"), "caller": caller, "provider": provider_name, "error": str(e)})
            #ログ用
            continue

    #すべてのプロバイダーが全滅した場合
    raise RuntimeError("全てのLLMプロバイダーがレートリミット、またはエラーにより利用できませんでした。")
