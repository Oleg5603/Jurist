import httpx
from openai import OpenAI, APIError, APIConnectionError, APITimeoutError

from config import OPENROUTER_API_KEY

# Lazy client initialization to allow module import even without API key
_client = None

def _get_client():
    global _client
    if _client is None:
        # The host's Windows system proxy is a Happ/Xray SOCKS5 listener on
        # 127.0.0.1:10808, but Windows registers it under the generic "socks="
        # key, which httpx's auto-detection misreads as socks4 (unsupported,
        # crashes with ValueError). Going fully proxy-less (trust_env=False)
        # instead hits OpenRouter directly from the RU IP, which OpenRouter's
        # WAF blocks ("Access denied by security policy"). So: route through
        # the same proxy explicitly, with the correct socks5 scheme.
        http_client = httpx.Client(proxy="socks5://127.0.0.1:10808", trust_env=False)
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
