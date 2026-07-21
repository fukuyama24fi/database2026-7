from mistralai.client import Mistral
from dotenv import load_dotenv
import os

load_dotenv()

client = Mistral(
    api_key=os.getenv("MISTRAL_API_KEY")
)


def chat(messages, model):

    response = client.chat.complete(
        model=model,
        messages=messages
    )

    return response.choices[0].message.content
