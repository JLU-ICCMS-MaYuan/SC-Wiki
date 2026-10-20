"""选题、引用与模型配置的确定性边界。"""
import pytest
from backend.community import generation as g
from backend.community import configuration as c
from backend.rag.llm_context import LlmConfig


def test_ten_categories_and_unicode_normalization():
    assert len(g.CATEGORIES) == 10
    assert g.fingerprint('为什么 Ｔｃ 上升？') == g.fingerprint('为什么 Tc 上升')


@pytest.mark.parametrize('body', ['假引用 [S9]', 'https://invented.example/paper', 'DOI 10.1234/fake', ''])
def test_rejects_unverified_citation_or_empty_answer(monkeypatch, body):
    monkeypatch.setattr(g, 'complete', lambda *a: {'body': body})
    with pytest.raises(g.GenerationError):
        g.create_answer('问题', [{'id': 'S1', 'paper_id': 1}])


def test_all_consulted_sources_retained_but_only_cited_sources_marked(monkeypatch):
    monkeypatch.setattr(g, 'complete', lambda *a: {'body': '依据文献 [S1]。'})
    sources = [{'id': 'S1', 'paper_id': 1}, {'id': 'S2', 'paper_id': 2}]
    assert g.create_answer('问题', sources) == ('依据文献 [S1]。', [{**sources[0], 'cited': True}, {**sources[1], 'cited': False}])


def test_duplicate_question_stops_after_three_candidates(monkeypatch):
    class DB:
        def scalars(self, statement): return ['迈斯纳效应是什么？']
    calls=[]
    monkeypatch.setattr(g,'complete',lambda *a: calls.append(a) or {'title':'迈斯纳效应是什么？','body':''})
    with pytest.raises(g.GenerationError, match='duplicate_question'):
        g.create_question(DB(),'foundations')
    assert len(calls)==3


def test_semantic_duplicate_is_rejected(monkeypatch):
    class DB:
        def scalars(self, statement): return ['解释迈斯纳效应']
    calls=[]
    def complete(prompt,payload):
        calls.append(payload)
        return {'duplicate':True} if 'candidate' in payload else {'title':'什么是超导体的迈斯纳效应？','body':''}
    monkeypatch.setattr(g,'complete',complete)
    with pytest.raises(g.GenerationError, match='duplicate_question'):
        g.create_question(DB(),'foundations')
    assert len(calls)==6


def test_model_identity_ignores_rotated_key_but_not_endpoint_or_model():
    first=LlmConfig('server','https://example.com/v1','m','secret')
    rotated=LlmConfig('server','https://example.com/v1/','m','rotated')
    other=LlmConfig('server','https://other.example/v1','m','secret')
    assert c.identity(first)==c.identity(rotated)
    assert c.identity(first)!=c.identity(other)
