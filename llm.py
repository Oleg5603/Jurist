import time

import httpx
from openai import OpenAI, APIError, APIConnectionError, APITimeoutError

from config import OPENROUTER_API_KEY
from practices import PRACTICE_IDS

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
        # Explicit timeout: without one, a hung proxy connection blocks the request
        # (and the whole /api/chat call) indefinitely instead of surfacing as the
        # APITimeoutError/APIConnectionError call_llm already knows how to handle.
        http_client = httpx.Client(proxy="socks5://127.0.0.1:10808", trust_env=False, timeout=30.0)
        _client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=OPENROUTER_API_KEY, http_client=http_client, timeout=30.0, max_retries=0)
    return _client

MODELS = {
    "Llama": {"label": "🟢 Llama 3.3 (бесплатно)", "model": "meta-llama/llama-3.3-70b-instruct:free"},
    "Claude": {"label": "🟣 Claude Haiku (платно)", "model": "anthropic/claude-haiku-4.5"},
}
DEFAULT_MODEL = "Claude"


class LLMError(Exception):
    pass


def call_llm(model_key: str, system: str, messages: list[dict]) -> str:
    if not OPENROUTER_API_KEY:
        raise LLMError("Не задан OPENROUTER_API_KEY в .env — получите ключ на openrouter.ai/keys.")
    if model_key not in MODELS:
        raise LLMError(f"Неизвестная модель: {model_key}")

    # The proxy this machine routes through (see _get_client above) is known to drop
    # connections intermittently, not consistently — a single retry on connection-level
    # failures (not on timeouts or API errors) smooths over that flakiness.
    last_connection_error = None
    resp = None
    for attempt in range(2):
        try:
            client = _get_client()
            resp = client.chat.completions.create(
                model=MODELS[model_key]["model"],
                max_tokens=2048,
                messages=[{"role": "system", "content": system}, *messages],
            )
            last_connection_error = None
            break
        except APIConnectionError as e:
            last_connection_error = e
            if attempt == 0:
                time.sleep(1)
                continue
        except APITimeoutError:
            raise LLMError("Модель не ответила вовремя (таймаут). Попробуйте ещё раз.")
        except APIError as e:
            raise LLMError(f"Ошибка OpenRouter: {e}")
        except Exception as e:
            raise LLMError(f"Не удалось обратиться к LLM: {e}")
    if last_connection_error is not None:
        raise LLMError("Не удалось подключиться к OpenRouter. Проверьте интернет-соединение.")
    content = resp.choices[0].message.content
    if not content:
        raise LLMError("Модель вернула пустой ответ. Попробуйте ещё раз.")
    return content


def classify_practice(text: str) -> str:
    if not OPENROUTER_API_KEY:
        return "general"
    prompt = (
        "Определи практику права, к которой относится следующий текст. "
        f"Ответь только одним словом — id практики из списка: {', '.join(PRACTICE_IDS)}. "
        "Если не уверен или ни один вариант не подходит явно, ответь general.\n\n"
        f"Текст:\n{text[:2000]}"
    )
    try:
        client = _get_client()
        resp = client.chat.completions.create(
            model=MODELS["Claude"]["model"],
            max_tokens=10,
            messages=[{"role": "user", "content": prompt}],
        )
        answer = (resp.choices[0].message.content or "").strip().lower()
        for practice_id in PRACTICE_IDS:
            if practice_id in answer:
                return practice_id
        return "general"
    except Exception:
        return "general"
