from citation_verifier import verify_citations
from doc_templates import select_template
from llm import call_llm, classify_practice
from practices import with_practice

CITATION_HONESTY_RULE = """ВАЖНО про ссылки на нормы права: указывай номер статьи и кодекс, только если
уверен в нём. Если не уверен в точном номере статьи — прямо скажи об этом ("точный номер статьи уточните
у юриста") вместо того, чтобы называть правдоподобный, но не проверенный номер. Неправильный номер статьи
опаснее, чем его отсутствие."""

CHAT_SYSTEM_PROMPT = f"""Ты — юридический ассистент, ориентированный на право Российской Федерации.
Помогаешь разобраться в правовых вопросах: даёшь ссылки на применимые нормы, объясняешь порядок действий,
указываешь на риски. ВАЖНО: твой ответ не является юридической консультацией и не заменяет очную консультацию
юриста — всегда явно указывай это, если вопрос касается конкретной спорной ситуации.

{CITATION_HONESTY_RULE}"""

DOCUMENT_SYSTEM_PROMPT = f"""Ты — юридический ассистент, готовящий черновики документов по праву РФ.
На основе вводных данных составь полный текст документа указанного типа, с корректной структурой
(шапка, стороны, предмет, условия, реквизиты для подписи). Незаполненные детали помечай [В КВАДРАТНЫХ СКОБКАХ].
В конце документа добавь пометку: "Документ сформирован автоматически, требует проверки юристом перед использованием."

{CITATION_HONESTY_RULE}"""

CONTRACT_SYSTEM_PROMPT = f"""Ты — юридический ассистент, анализирующий договоры по праву РФ на риски.
Изучи текст договора и составь список рисков. Каждый риск помечай одним из значков:
🔴 критический (может привести к прямым убыткам/недействительности), 🟡 важный (требует внимания),
🟢 приемлемый (незначительный, для полноты картины). Также перечисли типовые защитные пункты, которых
не хватает в договоре, и предложи конкретные формулировки правок. Отвечай структурированным списком.

{CITATION_HONESTY_RULE}"""


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
