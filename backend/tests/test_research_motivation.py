"""研究驱动力从全文生成并按独立行进入表单。"""

import json

from backend.ingest.property_evidence import source_chunks
from backend.ingest.research_motivation import choose_motivation, generate_motivation, task_chunks, valid_motivation


SOURCE = """# Introduction
The stable high-pressure structure of the synthesized compound remained unresolved.
The authors therefore investigated its ordered phases under compression.
# Results
The calculated transition pressure was 111 GPa.
# Discussion
Understanding metallization motivated the exploration of superconductivity.
"""


def _motive(point, quote):
    return {"point": point, "evidences": [{"file_id": "main", "quote": quote}]}


def test_fulltext_motivation_is_numbered_on_separate_lines():
    chunks = source_chunks(SOURCE, "main")
    seen = []

    def complete(prompt, payload):
        seen.append(json.loads(payload))
        return {"motives": [
            _motive("The stable high-pressure structure needed to be established.",
                    "The stable high-pressure structure of the synthesized compound remained unresolved."),
            _motive("The authors wanted to understand metallization and superconductivity.",
                    "Understanding metallization motivated the exploration of superconductivity."),
        ]}

    value, error = generate_motivation(chunks, complete=complete)
    assert error is None
    assert value == ("1. The stable high-pressure structure needed to be established.\n"
                     "2. The authors wanted to understand metallization and superconductivity.")
    assert "The calculated transition pressure was 111 GPa." in json.dumps(seen[0])


def test_inline_numbers_and_unlocated_quotes_cannot_enter_draft():
    assert not valid_motivation("1. First motive was unresolved. 2. Second motive was unclear.")
    assert not valid_motivation("1. " + "reason " * 300)
    chunks = source_chunks(SOURCE, "main")
    calls = []

    def complete(prompt, payload):
        calls.append(prompt)
        return {"motives": [_motive("The authors pursued a new structural question.",
                                    "This quote does not occur in the paper.")]}

    value, error = generate_motivation(chunks, complete=complete)
    assert (value, error) == ("", "quote_unlocated")
    assert len(calls) == 2


def test_missing_source_does_not_call_model():
    assert generate_motivation([], complete=lambda *_: (_ for _ in ()).throw(AssertionError())) == ("", "source_missing")


def test_malformed_first_reply_retries_only_this_field():
    chunks = source_chunks(SOURCE, "main")
    calls = []

    def complete(prompt, payload):
        calls.append(prompt)
        if len(calls) == 1:
            return {"motives": "1. Missing array"}
        return {"motives": [_motive("The stable structure needed to be established.",
                                    "The stable high-pressure structure of the synthesized compound remained unresolved.")]}

    value, error = generate_motivation(chunks, complete=complete)
    assert error is None
    assert value == "1. The stable structure needed to be established."
    assert len(calls) == 2


def test_task_reads_current_paper_text_and_excludes_unrelated_files(tmp_path):
    task_id = "a" * 32
    source = tmp_path / task_id
    source.mkdir()
    (source / "main.md").write_text(SOURCE, encoding="utf-8")
    (source / "background.md").write_text("External background must not enter.", encoding="utf-8")
    chunks = task_chunks(task_id, {"files": [
        {"file_id": "main", "role": "main", "original_filename": "paper.pdf"},
        {"file_id": "background", "role": "external", "original_filename": "other.pdf"},
    ]}, tmp_path)
    assert chunks and {chunk["file_id"] for chunk in chunks} == {"main"}
    assert all("External background" not in chunk["content"] for chunk in chunks)


def test_initial_motivation_with_located_quotes_needs_no_second_model_call():
    chunks = source_chunks(SOURCE, "main")
    value = "1. The stable high-pressure structure needed to be established."
    quote = {"file_id": "main", "quote": "The stable high-pressure structure of the synthesized compound remained unresolved."}
    assert choose_motivation(value, [quote], chunks,
                             complete=lambda *_: (_ for _ in ()).throw(AssertionError("不得二次调用"))) == (
                                 value, None, "initial")


def test_failed_retry_keeps_first_motivation_and_reports_missing_quote():
    chunks = source_chunks(SOURCE, "main")
    value = "1. The stable high-pressure structure needed to be established."
    result = choose_motivation(value, [{"file_id": "main", "quote": "不存在的引句"}], chunks,
                               complete=lambda *_: {"motives": []})
    assert result == (value, "quote_unlocated", "initial_review")
