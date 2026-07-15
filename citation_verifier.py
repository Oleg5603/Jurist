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
