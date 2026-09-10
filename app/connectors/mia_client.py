import os

from dotenv import load_dotenv
from openai import OpenAI
load_dotenv()

DEFAULT_BASE_URL = "https://mia.csp.kloudeks.com/v1"
DEFAULT_CHAT_MODEL = "kkbhackathon2026/Qwen3.8-27B"


class MiaConfigurationError(RuntimeError):
    """MIA yapılandırması eksik veya geçersiz olduğunda kullanılır."""


def create_mia_client() -> OpenAI:
    """Ortam değişkenlerini kullanarak güvenli bir MIA istemcisi oluşturur."""

    api_key = os.getenv("MIA_API_KEY", "").strip()
    base_url = os.getenv("MIA_BASE_URL", DEFAULT_BASE_URL).strip()

    if not api_key:
        raise MiaConfigurationError(
            "MIA_API_KEY bulunamadı. Anahtarı yerel .env dosyasına ekleyin."
        )

    if not base_url:
        raise MiaConfigurationError("MIA_BASE_URL boş bırakılamaz.")

    return OpenAI(
        api_key=api_key,
        base_url=base_url,
        timeout=30.0,
        max_retries=0,
    )


def ask_mia(prompt: str) -> str:
    """MIA sohbet modeline bir mesaj gönderir ve metin yanıtını döndürür."""

    cleaned_prompt = prompt.strip()

    if not cleaned_prompt:
        raise ValueError("MIA modeline gönderilecek mesaj boş olamaz.")

    model = os.getenv("MIA_CHAT_MODEL", DEFAULT_CHAT_MODEL).strip()

    if not model:
        raise MiaConfigurationError("MIA_CHAT_MODEL boş bırakılamaz.")

    client = create_mia_client()

    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "user",
                "content": cleaned_prompt,
            }
        ],
    )

    content = response.choices[0].message.content

    if not isinstance(content, str) or not content.strip():
        raise RuntimeError("MIA modelinden boş bir yanıt alındı.")

    return content.strip()