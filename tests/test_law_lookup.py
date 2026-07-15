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
