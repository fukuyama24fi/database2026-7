from google import genai
from dotenv import load_dotenv
import os

load_dotenv()

client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY")
)


def chat(messages, model):

    system_prompt = ""
    user_prompt = ""

    for m in messages:
        if m["role"] == "system":
            system_prompt = m["content"]
        elif m["role"] == "user":
            user_prompt = m["content"]

    response = client.models.generate_content(
        model=model,
        contents=user_prompt,
        config={
            "system_instruction": system_prompt
        }
    )

    return response.text
