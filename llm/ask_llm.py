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
            
            return provider.chat(messages, model_name)
            
        except RateLimitError as e:
            print(f"{provider_name} がレートリミット（429）に達しました。次のプロバイダーに切り替えます。")
            continue  #ループを続行して次のプロバイダーを試す
            
        except Exception as e:
            print(f"{provider_name} で予期せぬエラーが発生しました: {e}")
            #レートリミット以外でも、APIキー不足などで落ちた場合に次へ行くなら continue
            continue

    #すべてのプロバイダーが全滅した場合
    raise RuntimeError("全てのLLMプロバイダーがレートリミット、またはエラーにより利用できませんでした。")
