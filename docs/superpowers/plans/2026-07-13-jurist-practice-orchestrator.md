# Jurist — Practice Orchestrator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Before each LLM call in chat/document/contract endpoints, classify the
relevant legal practice area and inject a practice-specific system-prompt
fragment, without changing the API surface or UX.

**Architecture:** A new `practices.py` module holds a static dict of 9 practice
areas (id → label + system-prompt fragment). `llm.py` gains `classify_practice()`
— one cheap Claude Haiku call via the existing OpenRouter client, with a
try/except that always falls back to `"general"` on any error. `app.py`'s three
endpoints call `classify_practice()` on their relevant input text, then build a
combined system prompt via `practices.with_practice()` before calling the
existing `call_llm()` — no change to `call_llm`'s signature.

**Tech Stack:** Python, FastAPI, OpenAI SDK (OpenRouter), no new dependencies.

## Global Constraints
- No unit test framework in this repo (per `2026-07-12-jurist-mvp-design.md` —
  "одноразовое приложение для одного пользователя") — verification is manual,
  via running the server and hitting endpoints, matching existing project
  convention. Do not add pytest or any test dependency.
- `classify_practice()` must never raise — any failure (timeout, network,
  malformed response) returns `"general"` silently, per
  `2026-07-13-jurist-practice-orchestrator-design.md` "Обработка ошибок".
- Practice classification is never exposed in any API response or the UI.
- No new pip dependencies.

---

### Task 1: Practices data module

**Files:**
- Create: `practices.py`

**Interfaces:**
- Produces: `PRACTICES: dict[str, dict]` (keys: `id`, `label`,
  `system_prompt_fragment`), `PRACTICE_IDS: list[str]`,
  `with_practice(base_prompt: str, practice_id: str) -> str`.

- [ ] **Step 1: Write `practices.py`**

```python
PRACTICES: dict[str, dict] = {
    "civil": {
        "id": "civil",
        "label": "Гражданское/договорное право",
        "system_prompt_fragment": (
            "Специализация: гражданское и договорное право РФ (ГК РФ). "
            "Ориентируйся на нормы обязательственного права, договорную "
            "ответственность, убытки и неустойку."
        ),
    },
    "labor": {
        "id": "labor",
        "label": "Трудовое право",
        "system_prompt_fragment": (
            "Специализация: трудовое право РФ (ТК РФ). Ориентируйся на права "
            "и обязанности работника/работодателя, порядок увольнения, "
            "трудовые споры и компенсации."
        ),
    },
    "corporate": {
        "id": "corporate",
        "label": "Корпоративное право",
        "system_prompt_fragment": (
            "Специализация: корпоративное право РФ (ООО, АО — ФЗ №14-ФЗ, "
            "№208-ФЗ). Ориентируйся на корпоративное управление, доли/акции, "
            "сделки между участниками, корпоративные споры."
        ),
    },
    "family": {
        "id": "family",
        "label": "Семейное/наследственное право",
        "system_prompt_fragment": (
            "Специализация: семейное и наследственное право РФ (СК РФ, "
            "раздел V ГК РФ). Ориентируйся на раздел имущества, алименты, "
            "наследование по закону и по завещанию."
        ),
    },
    "it": {
        "id": "it",
        "label": "ИТ-право",
        "system_prompt_fragment": (
            "Специализация: ИТ-право РФ (152-ФЗ о персональных данных, "
            "лицензирование ПО, договоры на разработку/поддержку ИТ-услуг). "
            "Ориентируйся на защиту данных, лицензионные условия, SLA."
        ),
    },
    "tax": {
        "id": "tax",
        "label": "Налоговое право",
        "system_prompt_fragment": (
            "Специализация: налоговое право РФ (НК РФ). Ориентируйся на "
            "налоговые режимы, вычеты, налоговые споры и ответственность."
        ),
    },
    "admin": {
        "id": "admin",
        "label": "Административное право",
        "system_prompt_fragment": (
            "Специализация: административное право РФ (КоАП РФ). "
            "Ориентируйся на административные штрафы, порядок обжалования "
            "решений госорганов."
        ),
    },
    "realestate": {
        "id": "realestate",
        "label": "Недвижимость/земельное право",
        "system_prompt_fragment": (
            "Специализация: право недвижимости и земельное право РФ "
            "(ЗК РФ, гл. 30 ГК РФ). Ориентируйся на сделки с недвижимостью, "
            "регистрацию прав, земельные споры."
        ),
    },
    "general": {
        "id": "general",
        "label": "Общая практика",
        "system_prompt_fragment": (
            "Специализация не определена однозначно — отвечай как юрист "
            "общей практики РФ, при необходимости отметь, к какой отрасли "
            "права относится вопрос."
        ),
    },
}

PRACTICE_IDS: list[str] = list(PRACTICES)


def with_practice(base_prompt: str, practice_id: str) -> str:
    practice = PRACTICES.get(practice_id, PRACTICES["general"])
    return f"{base_prompt}\n\n{practice['system_prompt_fragment']}"
```

- [ ] **Step 2: Verify it imports cleanly**

Run: `python -c "from practices import PRACTICES, PRACTICE_IDS, with_practice; print(PRACTICE_IDS); print(with_practice('BASE', 'labor'))"`
Expected output: a list of 9 ids ending in `'general'`, then `BASE` followed by
the labor law fragment on the next line.

- [ ] **Step 3: Commit**

```bash
cd "C:\Users\HP\Jurist"
git add practices.py
git commit -m "Add practices.py: 9 legal-practice system-prompt fragments"
```

---

### Task 2: `classify_practice()` in `llm.py`

**Files:**
- Modify: `llm.py`

**Interfaces:**
- Consumes: `PRACTICE_IDS` from `practices.py` (Task 1), `_get_client()` and
  `MODELS` already defined in `llm.py`.
- Produces: `classify_practice(text: str) -> str` — always returns one of
  `PRACTICE_IDS`, never raises.

- [ ] **Step 1: Add the import and function to `llm.py`**

Add near the top, after the existing imports (`llm.py:1-4`):

```python
from practices import PRACTICE_IDS
```

Append at the end of `llm.py` (after `call_llm`, i.e. after current line 58):

```python


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
```

- [ ] **Step 2: Verify with a real call**

Run: `python -c "from llm import classify_practice; print(classify_practice('Работодатель уволил меня без предупреждения за два дня'))"`
Expected output: `labor` (may fall back to `general` if the OpenRouter/proxy
path is down — that's the designed degradation, not a failure of this step;
confirm no traceback is printed either way).

- [ ] **Step 3: Verify fallback on bad input doesn't raise**

Run: `python -c "from llm import classify_practice; print(classify_practice(''))"`
Expected output: some valid practice id (likely `general`), no traceback.

- [ ] **Step 4: Commit**

```bash
cd "C:\Users\HP\Jurist"
git add llm.py
git commit -m "Add classify_practice() to llm.py with silent fallback to general"
```

---

### Task 3: Wire classification into the three endpoints

**Files:**
- Modify: `app.py:13-15` (imports), `app.py:75-85` (`chat`),
  `app.py:108-123` (`generate_document`), `app.py:162-174` (`analyze_contract`)

**Interfaces:**
- Consumes: `classify_practice` from `llm.py` (Task 2), `with_practice` from
  `practices.py` (Task 1).

- [ ] **Step 1: Update the import line**

Change `app.py:15` from:

```python
from llm import call_llm, LLMError, DEFAULT_MODEL
```

to:

```python
from llm import call_llm, LLMError, DEFAULT_MODEL, classify_practice
from practices import with_practice
```

- [ ] **Step 2: Update the `chat` endpoint**

Change `app.py:75-85` from:

```python
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
```

to:

```python
@app.post("/api/chat")
def chat(req: ChatRequest, _: None = Depends(require_session)):
    history = storage.load_chat(req.session_id)
    history.append({"role": "user", "content": req.message})
    practice_id = classify_practice(req.message)
    system = with_practice(CHAT_SYSTEM_PROMPT, practice_id)
    try:
        reply = call_llm(req.model or DEFAULT_MODEL, system, history)
    except LLMError as e:
        raise HTTPException(status_code=502, detail=str(e))
    history.append({"role": "assistant", "content": reply})
    storage.save_chat(req.session_id, history)
    return {"reply": reply}
```

- [ ] **Step 3: Update the `generate_document` endpoint**

Change `app.py:108-123` from:

```python
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
        text = call_llm(req.model or DEFAULT_MODEL, DOCUMENT_SYSTEM_PROMPT, [{"role": "user", "content": user_prompt}])
    except LLMError as e:
        raise HTTPException(status_code=502, detail=str(e))
    doc_id = uuid.uuid4().hex
    storage.save_document(doc_id, {"doc_type": req.doc_type, "input": req.model_dump(), "text": text})
    return {"id": doc_id, "text": text}
```

to:

```python
@app.post("/api/documents/generate")
def generate_document(req: DocumentRequest, _: None = Depends(require_session)):
    user_prompt = (
        f"Тип документа: {req.doc_type}\n"
        f"Стороны: {req.parties}\n"
        f"Предмет: {req.subject}\n"
        f"Суммы: {req.amounts or 'не указаны'}\n"
        f"Доп. условия: {req.extra or 'нет'}"
    )
    practice_id = classify_practice(user_prompt)
    system = with_practice(DOCUMENT_SYSTEM_PROMPT, practice_id)
    try:
        text = call_llm(req.model or DEFAULT_MODEL, system, [{"role": "user", "content": user_prompt}])
    except LLMError as e:
        raise HTTPException(status_code=502, detail=str(e))
    doc_id = uuid.uuid4().hex
    storage.save_document(doc_id, {"doc_type": req.doc_type, "input": req.model_dump(), "text": text})
    return {"id": doc_id, "text": text}
```

- [ ] **Step 4: Update the `analyze_contract` endpoint**

Change `app.py:162-174` from:

```python
@app.post("/api/contracts/analyze")
async def analyze_contract(file: UploadFile = File(...), model: str = Form(default=""), _: None = Depends(require_session)):
    content = await file.read()
    text = _extract_text(file.filename, content)
    if not text.strip():
        raise HTTPException(status_code=400, detail="Не удалось извлечь текст из файла")
    try:
        analysis_text = call_llm(model or DEFAULT_MODEL, CONTRACT_SYSTEM_PROMPT, [{"role": "user", "content": text}])
    except LLMError as e:
        raise HTTPException(status_code=502, detail=str(e))
    contract_id = uuid.uuid4().hex
    storage.save_contract(contract_id, file.filename, content, {"analysis": analysis_text})
    return {"id": contract_id, "analysis": analysis_text}
```

to:

```python
@app.post("/api/contracts/analyze")
async def analyze_contract(file: UploadFile = File(...), model: str = Form(default=""), _: None = Depends(require_session)):
    content = await file.read()
    text = _extract_text(file.filename, content)
    if not text.strip():
        raise HTTPException(status_code=400, detail="Не удалось извлечь текст из файла")
    practice_id = classify_practice(text)
    system = with_practice(CONTRACT_SYSTEM_PROMPT, practice_id)
    try:
        analysis_text = call_llm(model or DEFAULT_MODEL, system, [{"role": "user", "content": text}])
    except LLMError as e:
        raise HTTPException(status_code=502, detail=str(e))
    contract_id = uuid.uuid4().hex
    storage.save_contract(contract_id, file.filename, content, {"analysis": analysis_text})
    return {"id": contract_id, "analysis": analysis_text}
```

- [ ] **Step 5: Verify the app still imports and starts**

Run: `cd "C:\Users\HP\Jurist" && python -c "import app; print('ok')"`
Expected output: `ok` (no ImportError/SyntaxError).

- [ ] **Step 6: Commit**

```bash
cd "C:\Users\HP\Jurist"
git add app.py
git commit -m "Wire classify_practice into chat/document/contract endpoints"
```

---

### Task 4: Manual end-to-end verification

**Files:** none (verification only, no code changes)

- [ ] **Step 1: Start the server on a free port**

Run: `cd "C:\Users\HP\Jurist" && uvicorn app:app --port 8010`
Expected: server starts without exceptions, logs `Application startup complete`.

- [ ] **Step 2: Log in and capture the session cookie**

Run (from a second terminal): `curl -s -c cookies.txt -X POST http://127.0.0.1:8010/login -d "login=BAL&password=010203040506" -o /dev/null -w "%{http_code}\n"`
Expected output: `303`.

- [ ] **Step 3: Send a labor-law chat message and inspect the reply**

Run: `curl -s -b cookies.txt -X POST http://127.0.0.1:8010/api/chat -H "Content-Type: application/json" -d "{\"session_id\":\"verify1\",\"message\":\"Работодатель уволил меня без предупреждения, что делать?\",\"model\":\"Claude\"}"`
Expected: JSON with a `reply` field whose content references trial-period/notice
rules under the Labor Code (ТК РФ) — confirms the labor fragment was applied
(content check is manual/qualitative, since practice_id is intentionally not
returned in the response).

- [ ] **Step 4: Send a corporate-law chat message for contrast**

Run: `curl -s -b cookies.txt -X POST http://127.0.0.1:8010/api/chat -H "Content-Type: application/json" -d "{\"session_id\":\"verify2\",\"message\":\"Как разделить доли между участниками ООО при выходе одного из них?\",\"model\":\"Claude\"}"`
Expected: JSON `reply` referencing ООО/ФЗ №14-ФЗ concepts (доли, выход участника)
— qualitatively different framing from Step 3's labor-law answer.

- [ ] **Step 5: Confirm no practice id leaks into any response**

Re-inspect the raw JSON bodies from Steps 3–4: only `reply` (chat),
`id`/`text` (document), or `id`/`analysis` (contract) keys should be present —
no `practice`, `practice_id`, or similar key.

- [ ] **Step 6: Stop the server and clean up**

Stop the `uvicorn` process (Ctrl+C in its terminal). Delete the temporary
`cookies.txt` if it was written into the repo directory: `rm -f "C:\Users\HP\Jurist\cookies.txt"`.

- [ ] **Step 7: Update PROGRESS.md**

Add a dated entry to `C:\Users\HP\Jurist\PROGRESS.md` under a new section
noting: practice orchestrator implemented (`practices.py`, `classify_practice`
in `llm.py`, wired into all 3 endpoints), verified manually for labor vs.
corporate practice differentiation, no UI/API change.

- [ ] **Step 8: Commit**

```bash
cd "C:\Users\HP\Jurist"
git add PROGRESS.md
git commit -m "Verify practice orchestrator end-to-end; update PROGRESS.md"
```
