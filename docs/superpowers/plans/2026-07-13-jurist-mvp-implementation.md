# Jurist MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the working Jurist MVP web app — login, legal Q&A chat, document generation, contract risk analysis — per the approved spec at `docs/superpowers/specs/2026-07-12-jurist-mvp-design.md`.

**Architecture:** Single FastAPI process serving a static HTML/JS/CSS frontend (no build step). Cookie-based session auth (single shared login/password from `.env`, signed with `itsdangerous`). All persistence is JSON files under `data/` (gitignored). LLM calls go through OpenRouter via the `openai` SDK client (same pattern as `veterans_agents/veteran_bot.py`).

**Tech Stack:** Python 3, FastAPI, uvicorn, `openai` SDK pointed at `https://openrouter.ai/api/v1`, `itsdangerous` for signed cookies, `python-docx` + `pypdf` for contract text extraction, `python-multipart` for file uploads.

## Global Constraints

- No unit tests — spec explicitly says this is a single-user, one-off app (`## Тестирование` in the spec). Verification is a manual run-through of the three scenarios via `/verify` after each task, not automated tests. Task steps below use "run and observe" instead of pytest.
- Single shared login/password from `.env` (`APP_LOGIN`/`APP_PASSWORD`) — no user table, no roles.
- Storage is JSON files under `data/`, already gitignored — never write real data into git.
- OpenRouter only, never call Anthropic directly (billing reason recorded in spec/PROGRESS.md) — default model is the free Llama, same model ids as `veteran_bot.py`.
- Every OpenRouter call is wrapped in try/except; failures return a clear error message to the frontend, never a silently swallowed exception or a response that looks like a normal assistant answer.
- Out of scope, do not build: law/news monitoring, VDR case search, GDPR/CCPA compliance, multi-agent orchestration, multi-user roles.

---

### Task 1: Storage layer (`storage.py`)

**Files:**
- Create: `C:\Users\HP\Jurist\storage.py`

**Interfaces:**
- Consumes: `config.CHATS_DIR`, `config.DOCUMENTS_DIR`, `config.CONTRACTS_DIR` (already defined in `config.py`)
- Produces:
  - `load_chat(session_id: str) -> list[dict]` — returns `[]` if no history file exists yet
  - `save_chat(session_id: str, messages: list[dict]) -> None`
  - `save_document(doc_id: str, data: dict) -> None`
  - `list_documents() -> list[dict]` — newest first, each dict includes `id`, `type`, `created_at`
  - `load_document(doc_id: str) -> dict | None`
  - `save_contract(contract_id: str, source_filename: str, source_bytes: bytes, analysis: dict) -> None`
  - `list_contracts() -> list[dict]` — newest first, each dict includes `id`, `source_filename`, `created_at`
  - `load_contract_analysis(contract_id: str) -> dict | None`

- [ ] **Step 1: Create the directory-ensuring helper and chat functions**

```python
import json
import os
from datetime import datetime, timezone

from config import CHATS_DIR, DOCUMENTS_DIR, CONTRACTS_DIR


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_chat(session_id: str) -> list[dict]:
    path = os.path.join(CHATS_DIR, f"{session_id}.json")
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_chat(session_id: str, messages: list[dict]) -> None:
    _ensure_dir(CHATS_DIR)
    path = os.path.join(CHATS_DIR, f"{session_id}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(messages, f, ensure_ascii=False, indent=2)
```

- [ ] **Step 2: Add document functions**

```python
def save_document(doc_id: str, data: dict) -> None:
    _ensure_dir(DOCUMENTS_DIR)
    record = {**data, "id": doc_id, "created_at": data.get("created_at") or _now_iso()}
    path = os.path.join(DOCUMENTS_DIR, f"{doc_id}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)


def load_document(doc_id: str) -> dict | None:
    path = os.path.join(DOCUMENTS_DIR, f"{doc_id}.json")
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def list_documents() -> list[dict]:
    _ensure_dir(DOCUMENTS_DIR)
    records = []
    for name in os.listdir(DOCUMENTS_DIR):
        if name.endswith(".json"):
            with open(os.path.join(DOCUMENTS_DIR, name), "r", encoding="utf-8") as f:
                records.append(json.load(f))
    records.sort(key=lambda r: r.get("created_at", ""), reverse=True)
    return records
```

- [ ] **Step 3: Add contract functions**

```python
def save_contract(contract_id: str, source_filename: str, source_bytes: bytes, analysis: dict) -> None:
    contract_dir = os.path.join(CONTRACTS_DIR, contract_id)
    _ensure_dir(contract_dir)
    with open(os.path.join(contract_dir, source_filename), "wb") as f:
        f.write(source_bytes)
    meta = {
        **analysis,
        "id": contract_id,
        "source_filename": source_filename,
        "created_at": _now_iso(),
    }
    with open(os.path.join(contract_dir, "analysis.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)


def load_contract_analysis(contract_id: str) -> dict | None:
    path = os.path.join(CONTRACTS_DIR, contract_id, "analysis.json")
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def list_contracts() -> list[dict]:
    _ensure_dir(CONTRACTS_DIR)
    records = []
    for name in os.listdir(CONTRACTS_DIR):
        analysis_path = os.path.join(CONTRACTS_DIR, name, "analysis.json")
        if os.path.exists(analysis_path):
            with open(analysis_path, "r", encoding="utf-8") as f:
                records.append(json.load(f))
    records.sort(key=lambda r: r.get("created_at", ""), reverse=True)
    return records
```

- [ ] **Step 4: Verify by hand**

Run: `python -c "import storage; storage.save_chat('t1', [{'role':'user','content':'hi'}]); print(storage.load_chat('t1'))"` from `C:\Users\HP\Jurist`
Expected: prints `[{'role': 'user', 'content': 'hi'}]`, and `data/chats/t1.json` now exists.

- [ ] **Step 5: Commit**

```bash
cd C:\Users\HP\Jurist
git add storage.py
git commit -m "Add JSON file storage layer for chats/documents/contracts"
```

---

### Task 2: LLM wrapper (`llm.py`)

**Files:**
- Create: `C:\Users\HP\Jurist\llm.py`

**Interfaces:**
- Consumes: `config.OPENROUTER_API_KEY`
- Produces:
  - `MODELS: dict[str, dict]` — same shape as `veteran_bot.py`'s `MODELS` (`label`, `model` keys), keys `"Llama"` (free, default) and `"Claude"` (paid)
  - `DEFAULT_MODEL: str = "Llama"`
  - `class LLMError(Exception)` — raised on any OpenRouter failure, message is already user-safe (no stack traces/secrets)
  - `call_llm(model_key: str, system: str, messages: list[dict]) -> str` — `messages` is a list of `{"role": ..., "content": ...}` dicts (chat history, NOT including the system prompt); raises `LLMError` on failure, never returns `None`

- [ ] **Step 1: Write the client, models table, and call_llm with error wrapping**

```python
from openai import OpenAI, APIError, APIConnectionError, APITimeoutError

from config import OPENROUTER_API_KEY

client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=OPENROUTER_API_KEY)

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
    content = resp.choices[0].message.content
    if not content:
        raise LLMError("Модель вернула пустой ответ. Попробуйте ещё раз.")
    return content
```

- [ ] **Step 2: Verify by hand**

Run (with a real `OPENROUTER_API_KEY` in `.env`): `python -c "from llm import call_llm; print(call_llm('Llama', 'Ты — тестовый ассистент.', [{'role':'user','content':'Скажи привет одним словом'}]))"` from `C:\Users\HP\Jurist`
Expected: prints a short greeting, no exception. If `.env` has no real key yet, expected instead: `llm.LLMError: Не задан OPENROUTER_API_KEY...` — this confirms the error path works cleanly rather than crashing.

- [ ] **Step 3: Commit**

```bash
cd C:\Users\HP\Jurist
git add llm.py
git commit -m "Add OpenRouter LLM wrapper with user-safe error handling"
```

---

### Task 3: Auth (`app.py` — login, session cookie, dependency)

**Files:**
- Create: `C:\Users\HP\Jurist\app.py` (this task only adds the auth slice; later tasks extend the same file)

**Interfaces:**
- Consumes: `config.APP_LOGIN`, `config.APP_PASSWORD`, `config.SESSION_SECRET`
- Produces:
  - `app: FastAPI` — the app instance later tasks register routes on
  - `require_session(request: Request) -> None` — FastAPI dependency, raises `HTTPException(401)` if the session cookie is missing/invalid; used as `Depends(require_session)` on every `/api/*` route added in later tasks
  - Routes: `POST /login` (form fields `login`, `password`), `GET /logout`, static file serving for `/` (serves `static/index.html`) — login page is the app's entrypoint

- [ ] **Step 1: Write the FastAPI app skeleton with signed-cookie auth**

```python
import os

from fastapi import FastAPI, Request, HTTPException, Form, Depends
from fastapi.responses import RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

from config import APP_LOGIN, APP_PASSWORD, SESSION_SECRET

app = FastAPI(title="Jurist")

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
COOKIE_NAME = "jurist_session"
COOKIE_MAX_AGE = 60 * 60 * 24 * 30  # 30 дней

_serializer = URLSafeTimedSerializer(SESSION_SECRET or "insecure-dev-secret")


def require_session(request: Request) -> None:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="Не авторизован")
    try:
        _serializer.loads(token, max_age=COOKIE_MAX_AGE)
    except (BadSignature, SignatureExpired):
        raise HTTPException(status_code=401, detail="Сессия истекла или недействительна")


@app.post("/login")
def login(login: str = Form(...), password: str = Form(...)):
    if login != APP_LOGIN or password != APP_PASSWORD:
        raise HTTPException(status_code=401, detail="Неверный логин или пароль")
    token = _serializer.dumps({"login": login})
    response = RedirectResponse(url="/app", status_code=303)
    response.set_cookie(COOKIE_NAME, token, max_age=COOKIE_MAX_AGE, httponly=True, samesite="lax")
    return response


@app.get("/logout")
def logout():
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie(COOKIE_NAME)
    return response


@app.get("/")
def root():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@app.get("/app")
def app_page(_: None = Depends(require_session)):
    return FileResponse(os.path.join(STATIC_DIR, "app.html"))


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
```

- [ ] **Step 2: Verify by hand**

Run: `cd C:\Users\HP\Jurist && uvicorn app:app --reload --port 8000` (with `.env` filled: set real `APP_LOGIN=lawyer`, `APP_PASSWORD` to a real password, `SESSION_SECRET` to a long random string).
Then in a browser: open `http://127.0.0.1:8000/` — expect a 404 or blank (index.html doesn't exist yet, that's fine for this task) but no Python traceback in the terminal for the `/` route resolution itself (FileResponse will 404 cleanly on missing file — acceptable since Task 5 adds it). Confirm instead with curl: `curl -i -X POST http://127.0.0.1:8000/login -d "login=lawyer&password=WRONGPASS"` → expect `401`. Then `curl -i -X POST http://127.0.0.1:8000/login -d "login=lawyer&password=<real password>"` → expect `303` with a `set-cookie: jurist_session=...` header.

- [ ] **Step 3: Commit**

```bash
cd C:\Users\HP\Jurist
git add app.py
git commit -m "Add FastAPI app with signed-cookie login/logout"
```

---

### Task 4: Chat API (`app.py` — extend)

**Files:**
- Modify: `C:\Users\HP\Jurist\app.py` (append route, add imports)

**Interfaces:**
- Consumes: `storage.load_chat`, `storage.save_chat`, `llm.call_llm`, `llm.DEFAULT_MODEL`, `require_session` (from Task 3)
- Produces: `POST /api/chat` — request body `{"session_id": str, "message": str, "model": str | null}`, response `{"reply": str}` on success or `{"error": str}` with HTTP 502 on LLM failure

- [ ] **Step 1: Add the chat system prompt, request model, and route**

```python
from pydantic import BaseModel

import storage
from llm import call_llm, LLMError, DEFAULT_MODEL

CHAT_SYSTEM_PROMPT = """Ты — юридический ассистент, ориентированный на право Российской Федерации.
Помогаешь разобраться в правовых вопросах: даёшь ссылки на применимые нормы, объясняешь порядок действий,
указываешь на риски. ВАЖНО: твой ответ не является юридической консультацией и не заменяет очную консультацию
юриста — всегда явно указывай это, если вопрос касается конкретной спорной ситуации."""


class ChatRequest(BaseModel):
    session_id: str
    message: str
    model: str | None = None


@app.post("/api/chat")
def chat(req: ChatRequest, _: None = Depends(require_session)):
    history = storage.load_chat(req.session_id)
    history.append({"role": "user", "content": req.message})
    try:
        reply = call_llm(req.model or DEFAULT_MODEL, CHAT_SYSTEM_PROMPT, history)
    except LLMError as e:
        raise HTTPException(status_code=502, detail=str(e))
    history.append({"role": "assistant", "content": reply})
    storage.save_chat(req.session_id, history)
    return {"reply": reply}


@app.get("/api/chat/{session_id}")
def get_chat_history(session_id: str, _: None = Depends(require_session)):
    return {"messages": storage.load_chat(session_id)}
```

- [ ] **Step 2: Verify by hand**

With the server running and a valid session cookie saved (from Task 3's curl, add `-c cookies.txt` to the login curl to save it): `curl -i -X POST http://127.0.0.1:8000/api/chat -b cookies.txt -H "Content-Type: application/json" -d "{\"session_id\":\"test1\",\"message\":\"Что такое исковая давность?\"}"`
Expected: `200` with JSON `{"reply": "..."}` containing a real answer. Then check `data/chats/test1.json` exists and contains both the user message and assistant reply.

- [ ] **Step 3: Commit**

```bash
cd C:\Users\HP\Jurist
git add app.py
git commit -m "Add legal Q&A chat API endpoint"
```

---

### Task 5: Document generation API (`app.py` — extend)

**Files:**
- Modify: `C:\Users\HP\Jurist\app.py`

**Interfaces:**
- Consumes: `storage.save_document`, `storage.list_documents`, `storage.load_document`, `call_llm`, `LLMError`, `DEFAULT_MODEL`
- Produces:
  - `POST /api/documents/generate` — body `{"doc_type": str, "parties": str, "subject": str, "amounts": str, "extra": str}`, response `{"id": str, "text": str}`
  - `GET /api/documents` — response `{"documents": [{"id","doc_type","created_at"}, ...]}`
  - `GET /api/documents/{doc_id}/download` — returns the generated text as a downloadable `.txt` file

- [ ] **Step 1: Add the route group**

```python
import uuid

from fastapi.responses import PlainTextResponse

DOCUMENT_SYSTEM_PROMPT = """Ты — юридический ассистент, готовящий черновики документов по праву РФ.
На основе вводных данных составь полный текст документа указанного типа, с корректной структурой
(шапка, стороны, предмет, условия, реквизиты для подписи). Незаполненные детали помечай [В КВАДРАТНЫХ СКОБКАХ].
В конце документа добавь пометку: "Документ сформирован автоматически, требует проверки юристом перед использованием."""


class DocumentRequest(BaseModel):
    doc_type: str
    parties: str
    subject: str
    amounts: str = ""
    extra: str = ""


@app.post("/api/documents/generate")
def generate_document(req: DocumentRequest, _: None = Depends(require_session)):
    user_prompt = (
        f"Тип документа: {req.doc_type}\n"
        f"Стороны: {req.parties}\n"
        f"Предмет: {req.subject}\n"
        f"Суммы: {req.amounts or 'не указаны'}\n"
        f"Доп. условия: {req.extra or 'нет'}"
    )
    try:
        text = call_llm(DEFAULT_MODEL, DOCUMENT_SYSTEM_PROMPT, [{"role": "user", "content": user_prompt}])
    except LLMError as e:
        raise HTTPException(status_code=502, detail=str(e))
    doc_id = uuid.uuid4().hex
    storage.save_document(doc_id, {"doc_type": req.doc_type, "input": req.model_dump(), "text": text})
    return {"id": doc_id, "text": text}


@app.get("/api/documents")
def documents_list(_: None = Depends(require_session)):
    return {"documents": storage.list_documents()}


@app.get("/api/documents/{doc_id}/download")
def download_document(doc_id: str, _: None = Depends(require_session)):
    doc = storage.load_document(doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Документ не найден")
    return PlainTextResponse(
        doc["text"],
        headers={"Content-Disposition": f'attachment; filename="{doc_id}.txt"'},
    )
```

- [ ] **Step 2: Verify by hand**

`curl -i -X POST http://127.0.0.1:8000/api/documents/generate -b cookies.txt -H "Content-Type: application/json" -d "{\"doc_type\":\"NDA\",\"parties\":\"ООО Ромашка и ИП Иванов\",\"subject\":\"неразглашение коммерческой тайны\",\"amounts\":\"\",\"extra\":\"\"}"`
Expected: `200`, JSON with an `id` and a `text` containing a plausible NDA draft. Then `curl -i http://127.0.0.1:8000/api/documents/{id}/download -b cookies.txt` → expect `200` with `Content-Disposition: attachment` header and the same text as body.

- [ ] **Step 3: Commit**

```bash
cd C:\Users\HP\Jurist
git add app.py
git commit -m "Add document generation API endpoints"
```

---

### Task 6: Contract analysis API (`app.py` — extend)

**Files:**
- Modify: `C:\Users\HP\Jurist\app.py`

**Interfaces:**
- Consumes: `storage.save_contract`, `storage.list_contracts`, `storage.load_contract_analysis`, `call_llm`, `LLMError`, `DEFAULT_MODEL`
- Produces:
  - `POST /api/contracts/analyze` — multipart file upload, field name `file`, accepts `.txt`/`.docx`/`.pdf`; response `{"id": str, "analysis": str}`
  - `GET /api/contracts` — response `{"contracts": [{"id","source_filename","created_at"}, ...]}`
  - `GET /api/contracts/{contract_id}` — response `{"analysis": str, "source_filename": str, "created_at": str}`

- [ ] **Step 1: Add file-text extraction helper**

```python
import io

from fastapi import UploadFile, File
import docx
import pypdf

CONTRACT_SYSTEM_PROMPT = """Ты — юридический ассистент, анализирующий договоры по праву РФ на риски.
Изучи текст договора и составь список рисков. Каждый риск помечай одним из значков:
🔴 критический (может привести к прямым убыткам/недействительности), 🟡 важный (требует внимания),
🟢 приемлемый (незначительный, для полноты картины). Также перечисли типовые защитные пункты, которых
не хватает в договоре, и предложи конкретные формулировки правок. Отвечай структурированным списком."""


def _extract_text(filename: str, content: bytes) -> str:
    lower = filename.lower()
    if lower.endswith(".txt"):
        return content.decode("utf-8", errors="replace")
    if lower.endswith(".docx"):
        doc = docx.Document(io.BytesIO(content))
        return "\n".join(p.text for p in doc.paragraphs)
    if lower.endswith(".pdf"):
        reader = pypdf.PdfReader(io.BytesIO(content))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    raise HTTPException(status_code=400, detail="Поддерживаются только файлы .txt, .docx, .pdf")
```

- [ ] **Step 2: Add the route group**

```python
@app.post("/api/contracts/analyze")
async def analyze_contract(file: UploadFile = File(...), _: None = Depends(require_session)):
    content = await file.read()
    text = _extract_text(file.filename, content)
    if not text.strip():
        raise HTTPException(status_code=400, detail="Не удалось извлечь текст из файла")
    try:
        analysis_text = call_llm(DEFAULT_MODEL, CONTRACT_SYSTEM_PROMPT, [{"role": "user", "content": text}])
    except LLMError as e:
        raise HTTPException(status_code=502, detail=str(e))
    contract_id = uuid.uuid4().hex
    storage.save_contract(contract_id, file.filename, content, {"analysis": analysis_text})
    return {"id": contract_id, "analysis": analysis_text}


@app.get("/api/contracts")
def contracts_list(_: None = Depends(require_session)):
    return {"contracts": storage.list_contracts()}


@app.get("/api/contracts/{contract_id}")
def contract_detail(contract_id: str, _: None = Depends(require_session)):
    analysis = storage.load_contract_analysis(contract_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="Анализ не найден")
    return analysis
```

- [ ] **Step 3: Verify by hand**

```bash
echo "Договор поставки между ООО Ромашка и ООО Лютик. Без условий об ответственности за просрочку." > test_contract.txt
curl -i -X POST http://127.0.0.1:8000/api/contracts/analyze -b cookies.txt -F "file=@test_contract.txt"
```
Expected: `200`, JSON with `id` and `analysis` text mentioning at least one 🔴/🟡/🟢 flag. Then `curl http://127.0.0.1:8000/api/contracts -b cookies.txt` → expect the uploaded contract listed.

- [ ] **Step 4: Commit**

```bash
cd C:\Users\HP\Jurist
git add app.py
git commit -m "Add contract risk analysis API endpoint"
del test_contract.txt
```

---

### Task 7: Frontend — login page (`static/index.html`)

**Files:**
- Create: `C:\Users\HP\Jurist\static\index.html`
- Create: `C:\Users\HP\Jurist\static\style.css`

**Interfaces:**
- Consumes: `POST /login` (Task 3)
- Produces: a working login form; `style.css` is shared by `index.html` and `app.html` (Task 8 references the same file)

- [ ] **Step 1: Write `static/style.css`**

```css
* { box-sizing: border-box; }
body {
  font-family: -apple-system, Segoe UI, Arial, sans-serif;
  background: #f4f5f7;
  color: #1f2430;
  margin: 0;
}
.container { max-width: 720px; margin: 0 auto; padding: 24px; }
.login-box {
  max-width: 360px; margin: 80px auto; background: #fff; padding: 32px;
  border-radius: 8px; box-shadow: 0 1px 4px rgba(0,0,0,.1);
}
input, textarea, select, button {
  font: inherit; width: 100%; padding: 10px; margin: 6px 0;
  border: 1px solid #ccc; border-radius: 4px;
}
button {
  background: #2b3a55; color: #fff; border: none; cursor: pointer; font-weight: 600;
}
button:hover { background: #1f2b40; }
.tabs { display: flex; gap: 8px; margin-bottom: 16px; }
.tabs button { width: auto; flex: 1; background: #e2e5ea; color: #1f2430; }
.tabs button.active { background: #2b3a55; color: #fff; }
.tab-panel { display: none; }
.tab-panel.active { display: block; }
.chat-log { border: 1px solid #ddd; border-radius: 6px; padding: 12px; height: 320px; overflow-y: auto; background: #fff; margin-bottom: 8px; }
.msg { margin: 8px 0; padding: 8px 12px; border-radius: 6px; white-space: pre-wrap; }
.msg.user { background: #dfe8ff; text-align: right; }
.msg.assistant { background: #eee; }
.error { color: #b3261e; margin: 8px 0; }
.list-item { border-bottom: 1px solid #eee; padding: 8px 0; }
```

- [ ] **Step 2: Write `static/index.html`**

```html
<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8">
  <title>Jurist — вход</title>
  <link rel="stylesheet" href="/static/style.css">
</head>
<body>
  <div class="login-box">
    <h2>Jurist</h2>
    <form id="login-form">
      <input type="text" name="login" placeholder="Логин" required>
      <input type="password" name="password" placeholder="Пароль" required>
      <button type="submit">Войти</button>
    </form>
    <div id="error" class="error"></div>
  </div>
  <script>
    document.getElementById("login-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      const form = new FormData(e.target);
      const resp = await fetch("/login", { method: "POST", body: form });
      if (resp.redirected) {
        window.location.href = resp.url;
      } else {
        document.getElementById("error").textContent = "Неверный логин или пароль";
      }
    });
  </script>
</body>
</html>
```

- [ ] **Step 3: Verify by hand**

With the server running, open `http://127.0.0.1:8000/` in a browser, enter the real `APP_LOGIN`/`APP_PASSWORD` from `.env`, submit. Expected: browser navigates to `/app` (will 404 until Task 8 adds `app.html` — confirm the redirect happens and no login error is shown, that's the pass condition for this task).

- [ ] **Step 4: Commit**

```bash
cd C:\Users\HP\Jurist
git add static/index.html static/style.css
git commit -m "Add login page frontend"
```

---

### Task 8: Frontend — main app (`static/app.html`, `static/app.js`)

**Files:**
- Create: `C:\Users\HP\Jurist\static\app.html`
- Create: `C:\Users\HP\Jurist\static\app.js`

**Interfaces:**
- Consumes: `POST /api/chat`, `GET /api/chat/{session_id}`, `POST /api/documents/generate`, `GET /api/documents`, `GET /api/documents/{id}/download`, `POST /api/contracts/analyze`, `GET /api/contracts`, `GET /api/contracts/{id}` (Tasks 4–6), `GET /logout` (Task 3)
- Produces: the three-tab working UI described in the spec

- [ ] **Step 1: Write `static/app.html`**

```html
<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8">
  <title>Jurist</title>
  <link rel="stylesheet" href="/static/style.css">
</head>
<body>
  <div class="container">
    <div style="display:flex; justify-content:space-between; align-items:center;">
      <h2>Jurist</h2>
      <a href="/logout">Выйти</a>
    </div>

    <div class="tabs">
      <button class="tab-btn active" data-tab="chat">Чат</button>
      <button class="tab-btn" data-tab="documents">Документы</button>
      <button class="tab-btn" data-tab="contracts">Анализ договора</button>
    </div>

    <div id="tab-chat" class="tab-panel active">
      <div id="chat-log" class="chat-log"></div>
      <div id="chat-error" class="error"></div>
      <form id="chat-form">
        <textarea id="chat-input" rows="3" placeholder="Ваш вопрос..." required></textarea>
        <button type="submit">Отправить</button>
      </form>
    </div>

    <div id="tab-documents" class="tab-panel">
      <form id="document-form">
        <select name="doc_type" required>
          <option value="NDA">NDA</option>
          <option value="Договор">Договор</option>
          <option value="Претензия">Претензия</option>
          <option value="Исковое заявление">Исковое заявление</option>
        </select>
        <input type="text" name="parties" placeholder="Стороны" required>
        <input type="text" name="subject" placeholder="Предмет" required>
        <input type="text" name="amounts" placeholder="Суммы (необязательно)">
        <textarea name="extra" placeholder="Доп. условия (необязательно)"></textarea>
        <button type="submit">Сгенерировать</button>
      </form>
      <div id="document-error" class="error"></div>
      <div id="document-result"></div>
      <h3>История</h3>
      <div id="document-list"></div>
    </div>

    <div id="tab-contracts" class="tab-panel">
      <form id="contract-form">
        <input type="file" name="file" accept=".txt,.docx,.pdf" required>
        <button type="submit">Загрузить и проанализировать</button>
      </form>
      <div id="contract-error" class="error"></div>
      <div id="contract-result"></div>
      <h3>История</h3>
      <div id="contract-list"></div>
    </div>
  </div>
  <script src="/static/app.js"></script>
</body>
</html>
```

- [ ] **Step 2: Write `static/app.js` — tab switching**

```javascript
document.querySelectorAll(".tab-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".tab-panel").forEach((p) => p.classList.remove("active"));
    btn.classList.add("active");
    document.getElementById("tab-" + btn.dataset.tab).classList.add("active");
  });
});
```

- [ ] **Step 3: Add chat logic to `static/app.js`**

```javascript
const CHAT_SESSION_ID = "session-" + Date.now();
const chatLog = document.getElementById("chat-log");
const chatError = document.getElementById("chat-error");

function appendMessage(role, content) {
  const div = document.createElement("div");
  div.className = "msg " + role;
  div.textContent = content;
  chatLog.appendChild(div);
  chatLog.scrollTop = chatLog.scrollHeight;
}

document.getElementById("chat-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  chatError.textContent = "";
  const input = document.getElementById("chat-input");
  const message = input.value.trim();
  if (!message) return;
  appendMessage("user", message);
  input.value = "";
  try {
    const resp = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: CHAT_SESSION_ID, message }),
    });
    if (!resp.ok) {
      const err = await resp.json();
      chatError.textContent = err.detail || "Ошибка запроса";
      return;
    }
    const data = await resp.json();
    appendMessage("assistant", data.reply);
  } catch (err) {
    chatError.textContent = "Сетевая ошибка: " + err.message;
  }
});
```

- [ ] **Step 4: Add document-generation logic to `static/app.js`**

```javascript
async function loadDocumentList() {
  const resp = await fetch("/api/documents");
  const data = await resp.json();
  const list = document.getElementById("document-list");
  list.innerHTML = "";
  data.documents.forEach((doc) => {
    const div = document.createElement("div");
    div.className = "list-item";
    div.innerHTML = `${doc.doc_type} — ${doc.created_at} — <a href="/api/documents/${doc.id}/download">скачать</a>`;
    list.appendChild(div);
  });
}

document.getElementById("document-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const errorEl = document.getElementById("document-error");
  const resultEl = document.getElementById("document-result");
  errorEl.textContent = "";
  resultEl.textContent = "";
  const form = new FormData(e.target);
  const payload = Object.fromEntries(form.entries());
  try {
    const resp = await fetch("/api/documents/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!resp.ok) {
      const err = await resp.json();
      errorEl.textContent = err.detail || "Ошибка запроса";
      return;
    }
    const data = await resp.json();
    resultEl.textContent = data.text;
    loadDocumentList();
  } catch (err) {
    errorEl.textContent = "Сетевая ошибка: " + err.message;
  }
});

loadDocumentList();
```

- [ ] **Step 5: Add contract-analysis logic to `static/app.js`**

```javascript
async function loadContractList() {
  const resp = await fetch("/api/contracts");
  const data = await resp.json();
  const list = document.getElementById("contract-list");
  list.innerHTML = "";
  data.contracts.forEach((c) => {
    const div = document.createElement("div");
    div.className = "list-item";
    div.textContent = `${c.source_filename} — ${c.created_at}`;
    list.appendChild(div);
  });
}

document.getElementById("contract-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const errorEl = document.getElementById("contract-error");
  const resultEl = document.getElementById("contract-result");
  errorEl.textContent = "";
  resultEl.textContent = "";
  const form = new FormData(e.target);
  try {
    const resp = await fetch("/api/contracts/analyze", { method: "POST", body: form });
    if (!resp.ok) {
      const err = await resp.json();
      errorEl.textContent = err.detail || "Ошибка запроса";
      return;
    }
    const data = await resp.json();
    resultEl.textContent = data.analysis;
    loadContractList();
  } catch (err) {
    errorEl.textContent = "Сетевая ошибка: " + err.message;
  }
});

loadContractList();
```

- [ ] **Step 6: Verify by hand — full manual run-through of all three scenarios**

With the server running (`uvicorn app:app --reload --port 8000`), in a browser:
1. Go to `http://127.0.0.1:8000/`, log in with real credentials → lands on `/app` with three tabs.
2. **Chat tab:** type "Что такое исковая давность?", submit → user bubble then assistant bubble appear with a real answer, no error shown.
3. **Documents tab:** fill NDA fields, submit → generated text appears below the form, and the history list below shows the new entry with a working "скачать" link that downloads a `.txt`.
4. **Contracts tab:** upload the earlier `test_contract.txt` (or any short .txt) → analysis with 🔴/🟡/🟢 flags appears, history list shows the filename.
5. Click "Выйти" → redirected to `/`, and re-visiting `/app` directly redirects/401s (confirms session cleared).

Expected: all five steps work with no unhandled exceptions in the browser console or the uvicorn terminal.

- [ ] **Step 7: Commit**

```bash
cd C:\Users\HP\Jurist
git add static/app.html static/app.js
git commit -m "Add main app frontend: chat, document generation, contract analysis tabs"
```

---

### Task 9: Update PROGRESS.md to reflect completed implementation

**Files:**
- Modify: `C:\Users\HP\Jurist\PROGRESS.md`

- [ ] **Step 1: Rewrite the status section**

Replace the `## Статус: спроектировано, реализация НЕ начата` section and the file-tree "ещё не написаны" note with: implementation complete (list all 7 code files as done), all three scenarios manually verified per Task 8 Step 6, remaining open item is login/password being placeholder values in `.env` (tracked separately, not part of this plan — see "Открытые вопросы").

- [ ] **Step 2: Commit**

```bash
cd C:\Users\HP\Jurist
git add PROGRESS.md
git commit -m "Update PROGRESS.md: MVP implementation complete"
```
