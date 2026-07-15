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
