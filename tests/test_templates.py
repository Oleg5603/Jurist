import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from doc_templates import select_template


def test_known_doc_types_return_nonempty_text():
    for doc_type in ["NDA", "Договор", "Претензия", "Исковое заявление"]:
        result = select_template(doc_type)
        assert result is not None
        assert len(result.strip()) > 0


def test_unknown_doc_type_returns_none():
    assert select_template("Что-то незнакомое") is None
