import sys
import os
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from orchestrator import JuristOrchestrator


def test_handle_chat_returns_llm_reply_when_no_bad_citations():
    orch = JuristOrchestrator()
    with patch("orchestrator.classify_practice", return_value="labor"), \
         patch("orchestrator.call_llm", return_value="Ответ без ссылок на статьи."):
        result = orch.handle_chat("Как уволить сотрудника?", [], "Claude")
    assert result == "Ответ без ссылок на статьи."


def test_handle_chat_appends_warning_for_fake_citation():
    orch = JuristOrchestrator()
    with patch("orchestrator.classify_practice", return_value="labor"), \
         patch("orchestrator.call_llm", return_value="См. ст. 99999 ТК РФ."):
        result = orch.handle_chat("Вопрос", [], "Claude")
    assert "99999 ТК РФ" in result
    assert "Не удалось подтвердить" in result


def test_handle_document_uses_template_when_available():
    orch = JuristOrchestrator()
    captured = {}

    def fake_call_llm(model, system, messages):
        captured["system"] = system
        return "Текст документа."

    with patch("orchestrator.classify_practice", return_value="civil"), \
         patch("orchestrator.call_llm", side_effect=fake_call_llm):
        result = orch.handle_document("NDA", "Стороны: А и Б.", "Claude")

    assert result == "Текст документа."
    assert "СОГЛАШЕНИЕ О НЕРАЗГЛАШЕНИИ" in captured["system"]


def test_handle_document_skips_template_for_unknown_type():
    orch = JuristOrchestrator()
    captured = {}

    def fake_call_llm(model, system, messages):
        captured["system"] = system
        return "Текст документа."

    with patch("orchestrator.classify_practice", return_value="civil"), \
         patch("orchestrator.call_llm", side_effect=fake_call_llm):
        orch.handle_document("Незнакомый тип", "Вводные.", "Claude")

    assert "СОГЛАШЕНИЕ О НЕРАЗГЛАШЕНИИ" not in captured["system"]


def test_handle_contract_returns_analysis():
    orch = JuristOrchestrator()
    with patch("orchestrator.classify_practice", return_value="realestate"), \
         patch("orchestrator.call_llm", return_value="🔴 Риск: ..."):
        result = orch.handle_contract("Текст договора.", "Claude")
    assert result == "🔴 Риск: ..."
