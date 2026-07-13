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
