import httpx
from openai import OpenAI, APIError, APIConnectionError, APITimeoutError

from config import OPENROUTER_API_KEY

# Lazy client initialization to allow module import even without API key
_client = None

def _get_client():
    global _client
    if _client is None:
        # trust_env=False: the host machine sets a SOCKS4 proxy env var (for an
        # unrelated VPN app) that httpx cannot parse (only SOCKS5 is supported),
        # which crashed every LLM call with an unhandled ValueError instead of
        # a clean LLMError. OpenRouter itself doesn't need that proxy.
        http_client = httpx.Client(trust_env=False)
        _client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=OPENROUTER_API_KEY, http_client=http_client)
    return _client

MODELS = {
    "Llama": {"label": "🟢 Llama 3.3 (бесплатно)", "model": "meta-llama/llama-3.3-70b-instruct:free"},
    "Claude": {"label": "🟣 Claude Haiku (платно)", "model": "anthropic/claude-haiku-4.5"},
}
DEFAULT_MODEL = "Llama"


class LLMError(Exception):
    pass


def call_llm(model_key: str, system: str, messages: list[dict]) -> str:
    if not OPENROUTER_API_KEY:
        raise LLMError("Не задан OPENROUTER_API_KEY в .env — получите ключ на openrouter.ai/keys.")
    if model_key not in MODELS:
        raise LLMError(f"Неизвестная модель: {model_key}")

    try:
        client = _get_client()
        resp = client.chat.completions.create(
            model=MODELS[model_key]["model"],
            max_tokens=2048,
            messages=[{"role": "system", "content": system}, *messages],
        )
    except APITimeoutError:
        raise LLMError("Модель не ответила вовремя (таймаут). Попробуйте ещё раз.")
    except APIConnectionError:
        raise LLMError("Не удалось подключиться к OpenRouter. Проверьте интернет-соединение.")
    except APIError as e:
        raise LLMError(f"Ошибка OpenRouter: {e}")
    except Exception as e:
        raise LLMError(f"Не удалось обратиться к LLM: {e}")
    content = resp.choices[0].message.content
    if not content:
        raise LLMError("Модель вернула пустой ответ. Попробуйте ещё раз.")
    return content
