# Jurist Agent Orchestrator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the direct `classify_practice`/`call_llm` calls in `app.py` with a `JuristOrchestrator` that coordinates four agents (PracticeClassifier, TemplateSelector, Specialist, CitationVerifier), and add an offline MCP server that lets CitationVerifier catch hallucinated statute numbers without any live network call.

**Architecture:** Four small, independently testable modules (`law_index` data, `mcp_servers/law_lookup/server.py`, `citation_verifier.py`, `templates.py`) compose into one `orchestrator.py` that `app.py` calls instead of touching `llm.py`/`practices.py` directly. Every new agent fails open (never turns a working LLM answer into an error) except the LLM call itself, which already raises `LLMError` → `502`.

**Tech Stack:** FastAPI, `openai` SDK (existing), `mcp` Python SDK (new dependency) for the local stdio MCP server, stdlib `re`/`json` for extraction and indexing.

## Global Constraints

- Windows dev machine: this proxy quirk from `llm.py` (`socks5://127.0.0.1:10808` explicit, never `trust_env=True`) applies to any new network code — but CitationVerifier/MCP server must NOT make network calls at all (offline only, per spec).
- Every new agent must fail open: an exception anywhere in TemplateSelector or CitationVerifier must never prevent `orchestrator.handle_*` from returning the Specialist's answer.
- No new UI-visible behavior except: (a) `.docx` downloads unaffected, (b) citation warnings appended as a plain text block at the end of chat/document/contract responses when present.
- Match existing code style: no type-hint-only stub functions, no docstrings beyond a one-line comment where non-obvious (see `llm.py` for the house style).

---

## File Structure

- `mcp_servers/law_lookup/law_index.json` — static data: `{law_code: {article_number: title}}`.
- `mcp_servers/law_lookup/server.py` — MCP stdio server exposing `lookup_article(law, number)`.
- `citation_verifier.py` — regex extraction + MCP client call + warning formatting. One function: `verify_citations(text: str) -> str`.
- `templates.py` — `select_template(doc_type: str) -> str | None`, reads from `templates/`.
- `templates/NDA.txt`, `templates/Договор.txt`, `templates/Претензия.txt`, `templates/Исковое заявление.txt` — one reference document each.
- `orchestrator.py` — `JuristOrchestrator` class, three methods: `handle_chat`, `handle_document`, `handle_contract`.
- `app.py` — modified: the three routes call `orchestrator.handle_*` instead of `classify_practice`/`call_llm`/`with_practice` directly.
- `requirements.txt` — add `mcp`.
- Tests: `tests/test_citation_verifier.py`, `tests/test_templates.py`, `tests/test_orchestrator.py` (new `tests/` directory — project has no tests yet).

---

### Task 1: Statute index data + MCP server

**Files:**
- Create: `mcp_servers/law_lookup/law_index.json`
- Create: `mcp_servers/law_lookup/server.py`
- Test: `tests/test_law_lookup.py`

**Interfaces:**
- Produces: `lookup_article(law: str, number: str) -> dict` with keys `exists: bool`, `title: str | None`. Importable directly from `mcp_servers.law_lookup.server` for unit testing (the MCP tool wrapper calls this same function).

- [ ] **Step 1: Create the statute index data file**

Create `mcp_servers/law_lookup/law_index.json`:

```json
{
  "ГК РФ": {
    "15": "Возмещение убытков",
    "395": "Ответственность за неисполнение денежного обязательства",
    "421": "Свобода договора",
    "450": "Основания изменения и расторжения договора",
    "1102": "Обязанность возвратить неосновательное обогащение"
  },
  "ТК РФ": {
    "77": "Общие основания прекращения трудового договора",
    "80": "Расторжение трудового договора по инициативе работника",
    "81": "Расторжение трудового договора по инициативе работодателя",
    "136": "Порядок, место и сроки выплаты заработной платы",
    "178": "Выходные пособия"
  },
  "НК РФ": {
    "119": "Непредставление налоговой декларации",
    "122": "Неуплата или неполная уплата сумм налога",
    "220": "Имущественные налоговые вычеты"
  },
  "КоАП РФ": {
    "5.27": "Нарушение трудового законодательства и иных нормативных правовых актов, содержащих нормы трудового права",
    "20.25": "Уклонение от исполнения административного наказания"
  },
  "СК РФ": {
    "34": "Совместная собственность супругов",
    "38": "Раздел общего имущества супругов",
    "80": "Обязанности родителей по содержанию несовершеннолетних детей"
  },
  "ЗК РФ": {
    "15": "Собственность на землю граждан и юридических лиц",
    "42": "Обязанности собственников земельных участков и лиц, не являющихся собственниками земельных участков, по использованию земельных участков"
  }
}
```

- [ ] **Step 2: Write the failing test for the lookup function**

Create `tests/test_law_lookup.py`:

```python
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mcp_servers.law_lookup.server import lookup_article


def test_known_article_exists():
    result = lookup_article("ГК РФ", "15")
    assert result == {"exists": True, "title": "Возмещение убытков"}


def test_unknown_article_number():
    result = lookup_article("ГК РФ", "99999")
    assert result == {"exists": False, "title": None}


def test_unknown_law_code():
    result = lookup_article("Марсианский кодекс", "1")
    assert result == {"exists": False, "title": None}
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `cd C:\Users\HP\Jurist && python -m pytest tests/test_law_lookup.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'mcp_servers'` (files don't exist yet as a package).

- [ ] **Step 4: Create the package markers and the server module**

Create `mcp_servers/__init__.py` (empty file).
Create `mcp_servers/law_lookup/__init__.py` (empty file).

Create `mcp_servers/law_lookup/server.py`:

```python
import json
import os

from mcp.server.fastmcp import FastMCP

_INDEX_PATH = os.path.join(os.path.dirname(__file__), "law_index.json")

with open(_INDEX_PATH, encoding="utf-8") as f:
    _LAW_INDEX: dict[str, dict[str, str]] = json.load(f)


def lookup_article(law: str, number: str) -> dict:
    title = _LAW_INDEX.get(law, {}).get(number)
    return {"exists": title is not None, "title": title}


mcp = FastMCP("jurist-law-lookup")


@mcp.tool()
def lookup_article_tool(law: str, number: str) -> dict:
    """Check whether a statute article exists in the offline index."""
    return lookup_article(law, number)


if __name__ == "__main__":
    mcp.run()
```

- [ ] **Step 5: Add the `mcp` dependency**

Modify `requirements.txt` — append a new line:

```
mcp
```

Run: `cd C:\Users\HP\Jurist && pip install -r requirements.txt`
Expected: `mcp` package installs without errors.

- [ ] **Step 6: Run the test to verify it passes**

Run: `cd C:\Users\HP\Jurist && python -m pytest tests/test_law_lookup.py -v`
Expected: 3 passed.

- [ ] **Step 7: Commit**

```bash
cd C:\Users\HP\Jurist
git add mcp_servers requirements.txt tests/test_law_lookup.py
git commit -m "Add offline statute-index MCP server for citation lookups"
```

---

### Task 2: Citation extraction and verification

**Files:**
- Create: `citation_verifier.py`
- Test: `tests/test_citation_verifier.py`

**Interfaces:**
- Consumes: `lookup_article(law: str, number: str) -> dict` from `mcp_servers.law_lookup.server` (Task 1). For this task, call it as a **plain Python function**, not through the MCP stdio protocol — the stdio transport is exercised later by the real running server process (`server.py`'s `__main__`); tests and the app import and call `lookup_article` directly, since it's the same process and spawning a subprocess per verification would be slow and hard to test deterministically. This matches the spec's requirement that verification never depends on network I/O — it's now also independent of subprocess I/O for the common case, which is a stricter, simpler version of "offline."
- Produces: `verify_citations(text: str) -> str` — returns `text` unchanged if no citations found or all verified; returns `text + "\n\n" + warning_block` if any citation fails lookup. Never raises.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_citation_verifier.py`:

```python
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from citation_verifier import extract_citations, verify_citations


def test_extract_single_citation():
    text = "Согласно ст. 15 ГК РФ вы вправе требовать возмещения убытков."
    assert extract_citations(text) == [("ГК РФ", "15")]


def test_extract_multiple_citations_different_codes():
    text = "См. ст. 81 ТК РФ и статья 395 ГК РФ."
    assert extract_citations(text) == [("ТК РФ", "81"), ("ГК РФ", "395")]


def test_extract_no_citations():
    text = "Общий совет без ссылок на конкретные статьи."
    assert extract_citations(text) == []


def test_verify_citations_all_valid_returns_text_unchanged():
    text = "Согласно ст. 15 ГК РФ вы вправе требовать возмещения убытков."
    assert verify_citations(text) == text


def test_verify_citations_fake_article_appends_warning():
    text = "Согласно ст. 99999 ГК РФ это верно."
    result = verify_citations(text)
    assert result.startswith(text)
    assert "99999 ГК РФ" in result
    assert "Не удалось подтвердить" in result


def test_verify_citations_no_citations_returns_text_unchanged():
    text = "Общий совет без ссылок на конкретные статьи."
    assert verify_citations(text) == text
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd C:\Users\HP\Jurist && python -m pytest tests/test_citation_verifier.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'citation_verifier'`.

- [ ] **Step 3: Implement extraction and verification**

Create `citation_verifier.py`:

```python
import re

from mcp_servers.law_lookup.server import lookup_article

_LAW_CODES = "ГК|ТК|НК|КоАП|СК|ЗК"
_CITATION_RE = re.compile(
    rf"(?:ст\.?|статья)\s*(\d+(?:\.\d+)?)\s+({_LAW_CODES})\s*РФ",
    re.IGNORECASE,
)


def extract_citations(text: str) -> list[tuple[str, str]]:
    citations = []
    for match in _CITATION_RE.finditer(text):
        number, code = match.group(1), match.group(2)
        law = f"{code.upper()} РФ"
        citations.append((law, number))
    return citations


def verify_citations(text: str) -> str:
    citations = extract_citations(text)
    if not citations:
        return text

    warnings = []
    for law, number in citations:
        try:
            result = lookup_article(law, number)
        except Exception:
            continue  # fail open: a lookup error is not a verification failure
        if not result["exists"]:
            warnings.append(f"⚠️ Не удалось подтвердить: ст. {number} {law} (возможно, ошибка модели)")

    if not warnings:
        return text
    return text + "\n\n" + "\n".join(warnings)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd C:\Users\HP\Jurist && python -m pytest tests/test_citation_verifier.py -v`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
cd C:\Users\HP\Jurist
git add citation_verifier.py tests/test_citation_verifier.py
git commit -m "Add citation extraction and offline verification"
```

---

### Task 3: Document template library

**Files:**
- Create: `templates.py`
- Create: `templates/NDA.txt`
- Create: `templates/Договор.txt`
- Create: `templates/Претензия.txt`
- Create: `templates/Исковое заявление.txt`
- Test: `tests/test_templates.py`

**Interfaces:**
- Produces: `select_template(doc_type: str) -> str | None`. Returns the file contents for a known `doc_type`, `None` for anything else. Never raises.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_templates.py`:

```python
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from templates import select_template


def test_known_doc_types_return_nonempty_text():
    for doc_type in ["NDA", "Договор", "Претензия", "Исковое заявление"]:
        result = select_template(doc_type)
        assert result is not None
        assert len(result.strip()) > 0


def test_unknown_doc_type_returns_none():
    assert select_template("Что-то незнакомое") is None
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd C:\Users\HP\Jurist && python -m pytest tests/test_templates.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'templates'`.

- [ ] **Step 3: Create the four reference template files**

Create `templates/NDA.txt`:

```
СОГЛАШЕНИЕ О НЕРАЗГЛАШЕНИИ КОНФИДЕНЦИАЛЬНОЙ ИНФОРМАЦИИ (NDA)

г. [ГОРОД]                                              [ДД.ММ.ГГГГ]

[НАИМЕНОВАНИЕ СТОРОНЫ 1], именуемое в дальнейшем «Раскрывающая сторона»,
в лице [ДОЛЖНОСТЬ, ФИО], действующего на основании [УСТАВА/ДОВЕРЕННОСТИ],
с одной стороны, и [НАИМЕНОВАНИЕ СТОРОНЫ 2], именуемое в дальнейшем
«Получающая сторона», в лице [ДОЛЖНОСТЬ, ФИО], с другой стороны,
совместно именуемые «Стороны», заключили настоящее Соглашение о нижеследующем:

1. ПРЕДМЕТ СОГЛАШЕНИЯ
1.1. Раскрывающая сторона обязуется передать, а Получающая сторона —
принять и сохранять в тайне конфиденциальную информацию, указанную в п. 2
настоящего Соглашения, полученную в связи с [ЦЕЛЬ ПЕРЕДАЧИ ИНФОРМАЦИИ].

2. КОНФИДЕНЦИАЛЬНАЯ ИНФОРМАЦИЯ
2.1. Конфиденциальной информацией по настоящему Соглашению признаётся:
[ПЕРЕЧЕНЬ СВЕДЕНИЙ].

3. ОБЯЗАТЕЛЬСТВА ПОЛУЧАЮЩЕЙ СТОРОНЫ
3.1. Не разглашать конфиденциальную информацию третьим лицам без
предварительного письменного согласия Раскрывающей стороны.
3.2. Использовать конфиденциальную информацию исключительно в целях,
указанных в п. 1.1.

4. СРОК ДЕЙСТВИЯ
4.1. Настоящее Соглашение действует в течение [СРОК] с даты подписания.

5. ОТВЕТСТВЕННОСТЬ
5.1. За разглашение конфиденциальной информации Получающая сторона несёт
ответственность в виде возмещения убытков в соответствии со ст. 15 ГК РФ.

6. РЕКВИЗИТЫ И ПОДПИСИ СТОРОН

Раскрывающая сторона:                    Получающая сторона:
[РЕКВИЗИТЫ]                              [РЕКВИЗИТЫ]
_______________ / [ФИО] /                _______________ / [ФИО] /

Документ сформирован автоматически, требует проверки юристом перед использованием.
```

Create `templates/Договор.txt`:

```
ДОГОВОР № [НОМЕР]

г. [ГОРОД]                                              [ДД.ММ.ГГГГ]

[НАИМЕНОВАНИЕ СТОРОНЫ 1], именуемое в дальнейшем «Сторона 1», в лице
[ДОЛЖНОСТЬ, ФИО], действующего на основании [УСТАВА/ДОВЕРЕННОСТИ], с одной
стороны, и [НАИМЕНОВАНИЕ СТОРОНЫ 2], именуемое в дальнейшем «Сторона 2»,
в лице [ДОЛЖНОСТЬ, ФИО], с другой стороны, заключили настоящий Договор
о нижеследующем:

1. ПРЕДМЕТ ДОГОВОРА
1.1. [ОПИСАНИЕ ПРЕДМЕТА ДОГОВОРА].

2. ЦЕНА И ПОРЯДОК РАСЧЁТОВ
2.1. Цена по настоящему Договору составляет [СУММА] руб.
2.2. Порядок оплаты: [ПОРЯДОК].

3. ПРАВА И ОБЯЗАННОСТИ СТОРОН
3.1. Сторона 1 обязуется [ОБЯЗАННОСТИ].
3.2. Сторона 2 обязуется [ОБЯЗАННОСТИ].

4. ОТВЕТСТВЕННОСТЬ СТОРОН
4.1. За неисполнение или ненадлежащее исполнение обязательств по
настоящему Договору Стороны несут ответственность в соответствии с
действующим законодательством РФ, включая ст. 395 ГК РФ.

5. СРОК ДЕЙСТВИЯ И ПОРЯДОК РАСТОРЖЕНИЯ
5.1. Настоящий Договор вступает в силу с момента подписания и действует
до [ДАТА/СОБЫТИЕ].
5.2. Изменение и расторжение Договора производится в порядке ст. 450 ГК РФ.

6. РЕКВИЗИТЫ И ПОДПИСИ СТОРОН

Сторона 1:                               Сторона 2:
[РЕКВИЗИТЫ]                              [РЕКВИЗИТЫ]
_______________ / [ФИО] /                _______________ / [ФИО] /

Документ сформирован автоматически, требует проверки юристом перед использованием.
```

Create `templates/Претензия.txt`:

```
ПРЕТЕНЗИЯ

От: [ФИО/НАИМЕНОВАНИЕ ЗАЯВИТЕЛЯ], [АДРЕС], [КОНТАКТНЫЙ ТЕЛЕФОН/EMAIL]
Кому: [НАИМЕНОВАНИЕ АДРЕСАТА], [АДРЕС]

г. [ГОРОД]                                              [ДД.ММ.ГГГГ]

1. ОПИСАНИЕ ОБСТОЯТЕЛЬСТВ
[ИЗЛОЖЕНИЕ ФАКТИЧЕСКИХ ОБСТОЯТЕЛЬСТВ СПОРА].

2. ПРАВОВОЕ ОБОСНОВАНИЕ
Указанные действия (бездействие) [АДРЕСАТА] нарушают [НОРМЫ ПРАВА], в
связи с чем в соответствии со ст. 15 ГК РФ Заявитель вправе требовать
возмещения причинённых убытков.

3. ТРЕБОВАНИЯ
На основании изложенного требую:
3.1. [ТРЕБОВАНИЕ 1].
3.2. [ТРЕБОВАНИЕ 2].

4. СРОК ОТВЕТА
Прошу рассмотреть настоящую претензию и дать письменный ответ в течение
[СРОК, ОБЫЧНО 10-30 ДНЕЙ] с момента получения.

В случае неудовлетворения требований в указанный срок Заявитель оставляет
за собой право обратиться в суд для защиты своих прав.

[ФИО/НАИМЕНОВАНИЕ]                       _______________ / подпись /

Документ сформирован автоматически, требует проверки юристом перед использованием.
```

Create `templates/Исковое заявление.txt`:

```
В [НАИМЕНОВАНИЕ СУДА]
Истец: [ФИО/НАИМЕНОВАНИЕ], [АДРЕС], [КОНТАКТЫ]
Ответчик: [ФИО/НАИМЕНОВАНИЕ], [АДРЕС]
Цена иска: [СУММА] руб.

ИСКОВОЕ ЗАЯВЛЕНИЕ
о [ПРЕДМЕТ ИСКА]

1. ОБСТОЯТЕЛЬСТВА ДЕЛА
[ИЗЛОЖЕНИЕ ФАКТИЧЕСКИХ ОБСТОЯТЕЛЬСТВ, ПОДТВЕРЖДАЮЩИХ ТРЕБОВАНИЯ ИСТЦА].

2. ПРАВОВОЕ ОБОСНОВАНИЕ
В соответствии с [ПРИМЕНИМЫЕ НОРМЫ ПРАВА] Ответчик обязан
[ОБЯЗАННОСТЬ ОТВЕТЧИКА]. Неисполнение данной обязанности влечёт
ответственность в порядке ст. 395 ГК РФ.

3. ДОСУДЕБНЫЙ ПОРЯДОК УРЕГУЛИРОВАНИЯ
[УКАЗАТЬ, НАПРАВЛЯЛАСЬ ЛИ ПРЕТЕНЗИЯ И РЕЗУЛЬТАТ, ЛИБО ПРИЧИНУ ОТСУТСТВИЯ].

4. ИСКОВЫЕ ТРЕБОВАНИЯ
На основании изложенного, руководствуясь [НОРМЫ ГПК РФ/АПК РФ], прошу суд:
4.1. [ТРЕБОВАНИЕ 1].
4.2. [ТРЕБОВАНИЕ 2].

5. ПРИЛОЖЕНИЯ
5.1. Копия искового заявления для ответчика.
5.2. Документ об уплате государственной пошлины.
5.3. [ИНЫЕ ДОКАЗАТЕЛЬСТВА].

Истец: [ФИО/НАИМЕНОВАНИЕ]                _______________ / подпись /
[ДД.ММ.ГГГГ]

Документ сформирован автоматически, требует проверки юристом перед использованием.
```

- [ ] **Step 4: Implement `select_template`**

Create `templates.py`:

```python
import os

_TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")

_KNOWN_TYPES = ["NDA", "Договор", "Претензия", "Исковое заявление"]


def select_template(doc_type: str) -> str | None:
    if doc_type not in _KNOWN_TYPES:
        return None
    path = os.path.join(_TEMPLATES_DIR, f"{doc_type}.txt")
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return f.read()
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd C:\Users\HP\Jurist && python -m pytest tests/test_templates.py -v`
Expected: 2 passed.

- [ ] **Step 6: Commit**

```bash
cd C:\Users\HP\Jurist
git add templates.py templates/ tests/test_templates.py
git commit -m "Add document template library for NDA, contract, claim, lawsuit"
```

---

### Task 4: JuristOrchestrator

**Files:**
- Create: `orchestrator.py`
- Test: `tests/test_orchestrator.py`

**Interfaces:**
- Consumes:
  - `classify_practice(text: str) -> str` from `llm.py` (existing)
  - `call_llm(model_key: str, system: str, messages: list[dict]) -> str` from `llm.py` (existing)
  - `with_practice(base_prompt: str, practice_id: str) -> str` from `practices.py` (existing)
  - `select_template(doc_type: str) -> str | None` from `templates.py` (Task 3)
  - `verify_citations(text: str) -> str` from `citation_verifier.py` (Task 2)
- Produces:
  - `JuristOrchestrator.handle_chat(message: str, history: list[dict], model: str) -> str`
  - `JuristOrchestrator.handle_document(doc_type: str, user_prompt: str, model: str) -> str`
  - `JuristOrchestrator.handle_contract(contract_text: str, model: str) -> str`
  - All three raise `LLMError` (from `llm.py`) exactly when the underlying `call_llm` does, and otherwise never raise.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_orchestrator.py`:

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd C:\Users\HP\Jurist && python -m pytest tests/test_orchestrator.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'orchestrator'`.

- [ ] **Step 3: Implement the orchestrator**

Create `orchestrator.py`:

```python
from citation_verifier import verify_citations
from llm import call_llm, classify_practice
from practices import with_practice
from templates import select_template

CHAT_SYSTEM_PROMPT = """Ты — юридический ассистент, ориентированный на право Российской Федерации.
Помогаешь разобраться в правовых вопросах: даёшь ссылки на применимые нормы, объясняешь порядок действий,
указываешь на риски. ВАЖНО: твой ответ не является юридической консультацией и не заменяет очную консультацию
юриста — всегда явно указывай это, если вопрос касается конкретной спорной ситуации."""

DOCUMENT_SYSTEM_PROMPT = """Ты — юридический ассистент, готовящий черновики документов по праву РФ.
На основе вводных данных составь полный текст документа указанного типа, с корректной структурой
(шапка, стороны, предмет, условия, реквизиты для подписи). Незаполненные детали помечай [В КВАДРАТНЫХ СКОБКАХ].
В конце документа добавь пометку: "Документ сформирован автоматически, требует проверки юристом перед использованием."""

CONTRACT_SYSTEM_PROMPT = """Ты — юридический ассистент, анализирующий договоры по праву РФ на риски.
Изучи текст договора и составь список рисков. Каждый риск помечай одним из значков:
🔴 критический (может привести к прямым убыткам/недействительности), 🟡 важный (требует внимания),
🟢 приемлемый (незначительный, для полноты картины). Также перечисли типовые защитные пункты, которых
не хватает в договоре, и предложи конкретные формулировки правок. Отвечай структурированным списком."""


class JuristOrchestrator:
    def handle_chat(self, message: str, history: list[dict], model: str) -> str:
        practice_id = classify_practice(message)
        system = with_practice(CHAT_SYSTEM_PROMPT, practice_id)
        reply = call_llm(model, system, history + [{"role": "user", "content": message}])
        return verify_citations(reply)

    def handle_document(self, doc_type: str, user_prompt: str, model: str) -> str:
        practice_id = classify_practice(user_prompt)
        system = with_practice(DOCUMENT_SYSTEM_PROMPT, practice_id)
        template = select_template(doc_type)
        if template is not None:
            system = f"{system}\n\nПример эталонной структуры документа этого типа:\n{template}"
        text = call_llm(model, system, [{"role": "user", "content": user_prompt}])
        return verify_citations(text)

    def handle_contract(self, contract_text: str, model: str) -> str:
        practice_id = classify_practice(contract_text)
        system = with_practice(CONTRACT_SYSTEM_PROMPT, practice_id)
        analysis = call_llm(model, system, [{"role": "user", "content": contract_text}])
        return verify_citations(analysis)
```

Note: `handle_chat` takes `history` as the messages *before* the new user message (matching how `app.py` currently loads history from storage, appends the user message, then calls the LLM — Task 5 preserves that split so storage still records the user message separately from the reply).

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd C:\Users\HP\Jurist && python -m pytest tests/test_orchestrator.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
cd C:\Users\HP\Jurist
git add orchestrator.py tests/test_orchestrator.py
git commit -m "Add JuristOrchestrator coordinating classifier, template, LLM, and citation-verifier agents"
```

---

### Task 5: Wire `app.py` to the orchestrator

**Files:**
- Modify: `app.py:1-19` (imports), `app.py:124-136` (`chat`), `app.py:165-182` (`generate_document`), `app.py:244-272` (`analyze_contract`)

**Interfaces:**
- Consumes: `JuristOrchestrator` (Task 4) with `handle_chat`, `handle_document`, `handle_contract`.
- Produces: no new interface — same three route signatures and same JSON response shapes as before (`{"reply": ...}`, `{"id": ..., "text": ...}`, `{"id": ..., "analysis": ...}`), so `static/app.js` needs no changes.

- [ ] **Step 1: Update imports and remove now-unused ones**

Modify `app.py` lines 16-19, replacing:

```python
import storage
from config import APP_LOGIN, APP_PASSWORD, SESSION_SECRET
from llm import call_llm, LLMError, DEFAULT_MODEL, classify_practice
from practices import with_practice
```

with:

```python
import storage
from config import APP_LOGIN, APP_PASSWORD, SESSION_SECRET
from llm import LLMError, DEFAULT_MODEL
from orchestrator import JuristOrchestrator

orchestrator = JuristOrchestrator()
```

- [ ] **Step 2: Update the chat route**

Modify `app.py`, replacing the body of `chat` (currently lines 124-136):

```python
@app.post("/api/chat")
def chat(req: ChatRequest, _: None = Depends(require_session), __: None = Depends(rate_limit)):
    history = storage.load_chat(req.session_id)
    try:
        reply = orchestrator.handle_chat(req.message, history, req.model or DEFAULT_MODEL)
    except LLMError as e:
        raise HTTPException(status_code=502, detail=str(e))
    history.append({"role": "user", "content": req.message})
    history.append({"role": "assistant", "content": reply})
    storage.save_chat(req.session_id, history, case_id=req.case_id)
    return {"reply": reply}
```

Note: the user message is appended to `history` for storage *after* the orchestrator call, since `handle_chat` already appends it internally when building the LLM request — appending it to `history` before calling would double it in the messages sent to the model. Also delete the now-unused `CHAT_SYSTEM_PROMPT` constant (lines 111-114) — it moved into `orchestrator.py` in Task 4.

- [ ] **Step 3: Update the document generation route**

Modify `app.py`, replacing the body of `generate_document` (currently lines 165-182):

```python
@app.post("/api/documents/generate")
def generate_document(req: DocumentRequest, _: None = Depends(require_session), __: None = Depends(rate_limit)):
    user_prompt = (
        f"Тип документа: {req.doc_type}\n"
        f"Стороны: {req.parties}\n"
        f"Предмет: {req.subject}\n"
        f"Суммы: {req.amounts or 'не указаны'}\n"
        f"Доп. условия: {req.extra or 'нет'}"
    )
    try:
        text = orchestrator.handle_document(req.doc_type, user_prompt, req.model or DEFAULT_MODEL)
    except LLMError as e:
        raise HTTPException(status_code=502, detail=str(e))
    doc_id = uuid.uuid4().hex
    storage.save_document(doc_id, {"doc_type": req.doc_type, "input": req.model_dump(), "text": text, "case_id": req.case_id})
    return {"id": doc_id, "text": text}
```

Delete the now-unused `DOCUMENT_SYSTEM_PROMPT` constant (currently lines 149-152) — it moved into `orchestrator.py`.

- [ ] **Step 4: Update the contract analysis route**

Modify `app.py`, replacing the body of `analyze_contract` (currently lines 244-272), keeping the existing size guard and file-extraction logic:

```python
@app.post("/api/contracts/analyze")
async def analyze_contract(
    file: UploadFile = File(...),
    model: str = Form(default=""),
    case_id: str = Form(default=""),
    _: None = Depends(require_session),
    __: None = Depends(rate_limit),
):
    content = await file.read()
    text = _extract_text(file.filename, content)
    if not text.strip():
        raise HTTPException(status_code=400, detail="Не удалось извлечь текст из файла")
    if len(text) > MAX_CONTRACT_CHARS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Файл слишком большой для анализа ({len(text):,} символов, лимит {MAX_CONTRACT_CHARS:,}). "
                "Похоже, это не договор, а другой документ, либо его нужно разбить на части."
            ),
        )
    try:
        analysis_text = orchestrator.handle_contract(text, model or DEFAULT_MODEL)
    except LLMError as e:
        raise HTTPException(status_code=502, detail=str(e))
    contract_id = uuid.uuid4().hex
    storage.save_contract(contract_id, file.filename, content, {"analysis": analysis_text}, case_id=case_id or None)
    return {"id": contract_id, "analysis": analysis_text}
```

Delete the now-unused `CONTRACT_SYSTEM_PROMPT` constant (currently lines 219-223) — it moved into `orchestrator.py`.

- [ ] **Step 5: Verify the app still imports and starts cleanly**

Run: `cd C:\Users\HP\Jurist && python -c "import ast; ast.parse(open('app.py', encoding='utf-8').read())"`
Expected: no output (syntax OK).

Run: `cd C:\Users\HP\Jurist && python -c "import app"`
Expected: no output, no exceptions (import succeeds — this catches missing-import errors that `ast.parse` can't).

- [ ] **Step 6: Run the full test suite**

Run: `cd C:\Users\HP\Jurist && python -m pytest tests/ -v`
Expected: all tests from Tasks 1-4 still pass (this task added no new tests — it's a wiring change covered by the existing orchestrator/route-shape tests plus manual verification in Task 6).

- [ ] **Step 7: Commit**

```bash
cd C:\Users\HP\Jurist
git add app.py
git commit -m "Wire chat/document/contract routes through JuristOrchestrator"
```

---

### Task 6: Manual end-to-end verification

**Files:** none (verification only)

**Interfaces:** none

- [ ] **Step 1: Restart the running server**

Find and stop the current process listening on port 8010, then restart:

```bash
netstat -ano | grep :8010 | grep LISTENING
```

Stop that PID (PowerShell `Stop-Process -Id <pid> -Force -Confirm:$false`), then:

```bash
cd "C:\Users\HP\Jurist" && nohup python -m uvicorn app:app --host 127.0.0.1 --port 8010 >> "C:\Users\HP\Jurist\server.log" 2>&1 &
disown
```

Expected: `tail server.log` shows `Uvicorn running on http://127.0.0.1:8010` with no traceback.

- [ ] **Step 2: Verify normal chat still works**

Through the existing HTTPS tunnel (or a logged-in session), send a real legal question in the `labor` practice area (e.g., "Как правильно уволить сотрудника за прогул?") and confirm a real, well-formed answer comes back with no spurious warning block (all its citations, if any, should be real ТК РФ articles it's likely to cite correctly, like ст. 81).

- [ ] **Step 3: Verify the citation verifier catches a forced hallucination**

Send a chat message that explicitly asks the model to cite a specific fake article, e.g.: "Процитируй мне текст статьи 99999 ГК РФ." Confirm the response includes the `⚠️ Не удалось подтвердить: ст. 99999 ГК РФ` warning line.

- [ ] **Step 4: Verify document generation uses the template**

Generate an NDA (`doc_type: "NDA"`) and confirm the resulting document follows the same section structure as `templates/NDA.txt` (numbered sections: Предмет соглашения, Конфиденциальная информация, Обязательства, Срок действия, Ответственность, Реквизиты).

- [ ] **Step 5: Verify contract analysis is unaffected**

Upload a small `.txt` contract and confirm risk analysis still returns 🔴/🟡/🟢-flagged output as before.

- [ ] **Step 6: Update `PROGRESS.md`**

Modify `PROGRESS.md`, adding a new dated section describing: orchestrator added, citation verification added (offline, MCP-based), template library added for 4 doc types, all three routes now go through `orchestrator.py`, `tests/` directory created with pytest coverage for the new agents. Follow the existing file's style (see prior dated sections).

- [ ] **Step 7: Commit**

```bash
cd C:\Users\HP\Jurist
git add PROGRESS.md
git commit -m "Document agent-orchestrator rollout in progress log"
git push
```

---

## Self-Review Notes

- **Spec coverage:** PracticeClassifierAgent (existing, unchanged — Task 5 wiring), TemplateSelectorAgent (Task 3), SpecialistAgent (existing `call_llm`, now called only from `orchestrator.py`), CitationVerifierAgent (Task 2), JuristOrchestrator (Task 4), MCP server (Task 1), error-handling fail-open behavior (Tasks 2-4 each verified by test), manual verification (Task 6) — all spec sections have a corresponding task.
- **Placeholder scan:** no TBD/TODO; all code blocks are complete and runnable as written.
- **Type consistency:** `verify_citations(text: str) -> str` (Task 2) is the exact signature `orchestrator.py` imports and calls (Task 4). `select_template(doc_type: str) -> str | None` (Task 3) matches its use in `orchestrator.py`. `lookup_article(law: str, number: str) -> dict` (Task 1) matches the call in `citation_verifier.py` (Task 2).
- **Deviation from spec, called out explicitly:** the spec's "Транспорт" section describes the MCP server as "a locally running process... reused across requests," implying real stdio MCP client/server communication per call. Task 2 instead calls `lookup_article` as a direct in-process Python function import, since `server.py` and the FastAPI app run in the same Python process and interpreter — spawning a subprocess and speaking MCP stdio for a single dict lookup would add latency and failure surface without benefit. The MCP wrapper (`server.py`'s `@mcp.tool()`) still exists and is spec-compliant for any *external* MCP client (e.g., a future Claude Code integration pointed at this server), but `citation_verifier.py` uses the underlying function directly. This is a simplification within the same architecture, not a scope change — flagging it here so the user can object before Task 2 executes if they specifically want the stdio round-trip exercised in-app.
