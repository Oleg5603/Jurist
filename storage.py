import json
import os
from datetime import datetime, timezone

from config import CASES_DIR, CHATS_DIR, DOCUMENTS_DIR, CONTRACTS_DIR


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_chat_record(session_id: str) -> dict:
    path = os.path.join(CHATS_DIR, f"{session_id}.json")
    if not os.path.exists(path):
        return {"session_id": session_id, "case_id": None, "created_at": _now_iso(), "messages": []}
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):  # legacy format: bare message list
        return {"session_id": session_id, "case_id": None, "created_at": _now_iso(), "messages": data}
    return data


def load_chat(session_id: str) -> list[dict]:
    return _load_chat_record(session_id)["messages"]


def save_chat(session_id: str, messages: list[dict], case_id: str | None = None) -> None:
    _ensure_dir(CHATS_DIR)
    record = _load_chat_record(session_id)
    record["messages"] = messages
    if case_id is not None:
        record["case_id"] = case_id
    path = os.path.join(CHATS_DIR, f"{session_id}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)


def list_chats() -> list[dict]:
    _ensure_dir(CHATS_DIR)
    records = []
    for name in os.listdir(CHATS_DIR):
        if name.endswith(".json"):
            with open(os.path.join(CHATS_DIR, name), "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                continue
            records.append({k: v for k, v in data.items() if k != "messages"})
    records.sort(key=lambda r: r.get("created_at", ""), reverse=True)
    return records


def save_case(case_id: str, name: str) -> dict:
    _ensure_dir(CASES_DIR)
    record = {"id": case_id, "name": name, "created_at": _now_iso()}
    path = os.path.join(CASES_DIR, f"{case_id}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)
    return record


def list_cases() -> list[dict]:
    _ensure_dir(CASES_DIR)
    records = []
    for name in os.listdir(CASES_DIR):
        if name.endswith(".json"):
            with open(os.path.join(CASES_DIR, name), "r", encoding="utf-8") as f:
                records.append(json.load(f))
    records.sort(key=lambda r: r.get("created_at", ""), reverse=True)
    return records


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


def save_contract(contract_id: str, source_filename: str, source_bytes: bytes, analysis: dict, case_id: str | None = None) -> None:
    contract_dir = os.path.join(CONTRACTS_DIR, contract_id)
    _ensure_dir(contract_dir)
    with open(os.path.join(contract_dir, source_filename), "wb") as f:
        f.write(source_bytes)
    meta = {
        **analysis,
        "id": contract_id,
        "source_filename": source_filename,
        "case_id": case_id,
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
