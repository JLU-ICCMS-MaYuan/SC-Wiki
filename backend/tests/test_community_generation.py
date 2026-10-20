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


def test_empty_public_library_does_not_require_embedding(monkeypatch):
    from sqlalchemy import create_engine, text
    from backend import database
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as db:
        db.execute(text("CREATE TABLE papers(id INTEGER, review_status TEXT, approved_revision INTEGER, content_revision INTEGER)"))
        db.execute(text("INSERT INTO papers VALUES (1, 'pending', NULL, 1), (2, 'approved', 1, 2)"))
    monkeypatch.setattr(database, 'engine', engine)
    assert g.retrieve_sources('为什么会出现超导？') == []
    engine.dispose()


def test_complete_requires_finished_stream(monkeypatch):
    from backend.rag import llm
    def fake(system, payload, **options):
        assert options['retries'] == 0
        options['on_call']({'finish_reason': 'length'})
        return {'body':'截断的答案'}
    monkeypatch.setattr(llm, 'complete_json', fake)
    with pytest.raises(g.GenerationError, match='invalid_model_output'):
        g.complete('system', {'question':'问题'})


def test_full_previous_answers_and_reference_validation(monkeypatch):
    previous=[{'key':'A1','body':'全文'*10000,'model_name':'DeepSeek','sequence':1}]
    def complete(prompt,payload):
        assert payload['previous_answers']==previous
        assert len(payload['previous_answers'][0]['body'])==20000
        assert '不是权威证据' in prompt
        return {'body':'认同前文 [A1]，补充另一角度。'}
    monkeypatch.setattr(g,'complete',complete)
    assert '[A1]' in g.create_answer('问题',[],previous)[0]
    monkeypatch.setattr(g,'complete',lambda *args:{'body':'虚构前文 [A9T2]'})
    with pytest.raises(g.GenerationError,match='invalid_citation'):
        g.create_answer('问题',[],previous)


def test_repeated_continuation_is_never_published(monkeypatch):
    calls=[]
    monkeypatch.setattr(g,'complete',lambda *a:calls.append(a) or {'body':'相同的原始答案'})
    with pytest.raises(g.GenerationError,match='answer_not_distinct'):
        g.create_answer('问题',[],[{'key':'A1','body':'相同的原始答案'}])
    assert len(calls)==2
    assert '上次输出被拒绝' in calls[1][0]
