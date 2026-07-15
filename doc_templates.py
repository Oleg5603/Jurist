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
