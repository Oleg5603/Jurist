import io
import os
import uuid

import docx
import pypdf
from fastapi import FastAPI, Request, HTTPException, Form, Depends, UploadFile, File
from fastapi.responses import RedirectResponse, FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from pydantic import BaseModel

import storage
from config import APP_LOGIN, APP_PASSWORD, SESSION_SECRET
from llm import call_llm, LLMError, DEFAULT_MODEL

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


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
