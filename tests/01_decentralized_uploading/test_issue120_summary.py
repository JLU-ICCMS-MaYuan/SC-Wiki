"""论文总结生成与核对的行为回归。"""

from backend.ingest.paper_summary import choose_summary, valid_summary
from backend.ingest.upload_jobs import _normalize_draft
from backend.ingest import property_evidence as evidence
from backend.ingest.scientific_evidence import field_records


ABSTRACT = ("First-principles calculations predict four structures of H3S under pressure. "
            "Metallization occurs at 111 GPa, and the highest predicted Tc is 204 K at 200 GPa.")
SUMMARY = (
    "1. First-principles calculations identify four pressure-dependent phases of H3S and relate their structures to metallization.\n"
    "2. The compound becomes metallic near 111 GPa, below the corresponding threshold reported for molecular hydrogen.\n"
    "3. The R3m and Im-3m phases are predicted to reach Tc ranges of 155–166 K and 191–204 K at 130 and 200 GPa, respectively."
)


def test_summary_retries_only_invalid_output_and_never_copies_abstract():
    calls = []

    def complete(prompt, payload):
        calls.append((prompt, payload))
        return {"summary": SUMMARY}

    assert valid_summary(SUMMARY, ABSTRACT)
    assert choose_summary(SUMMARY, ABSTRACT, [{"metadata": {"abstract": ABSTRACT}}], complete) == (SUMMARY, None)
    assert not calls
    selected, error = choose_summary(ABSTRACT, ABSTRACT, [{"key_findings": ["Tc reaches 204 K"]}], complete)
    assert (selected, error) == (SUMMARY, None)
    assert len(calls) == 1 and calls[0][1]["abstract"] == ABSTRACT
    assert not valid_summary("1. One sentence. Another sentence.\n2. A second conclusion.\n3. A third conclusion.", ABSTRACT)


def test_failed_retry_leaves_summary_empty_without_normalization_fallback():
    selected, error = choose_summary(ABSTRACT, ABSTRACT, [], lambda *_: {"summary": ABSTRACT})
    assert (selected, error) == ("", "invalid_summary")
    draft = _normalize_draft({"paper": {"abstract": ABSTRACT, "summary": selected, "paper_type": "unknown"},
                              "summary": ABSTRACT, "material_states": []})
    assert draft["paper"]["summary"] == ""
    assert choose_summary("", ABSTRACT, [], lambda *_: (_ for _ in ()).throw(RuntimeError())) == ("", "retry_failed")


def test_long_abstract_requires_a_slightly_longer_summary():
    long_abstract = " ".join([ABSTRACT] * 6)
    assert not valid_summary(SUMMARY, long_abstract)
    paper_abstract = " ".join([ABSTRACT] * 3)
    longer_conclusions = (
        "1. First-principles calculations identify four pressure-dependent phases of H3S and relate their structures to metallization under compression at several observed transitions, with detailed structural and electronic evidence for each phase.\n"
        "2. The compound becomes metallic near 111 GPa, below the corresponding threshold reported for molecular hydrogen in the same pressure regime.\n"
        "3. The R3m and Im-3m phases are predicted to reach Tc ranges of 155–166 K and 191–204 K at 130 and 200 GPa, respectively, based on electron-phonon calculations."
    )
    assert valid_summary(longer_conclusions, paper_abstract)
    calls = []
    def retry(_, payload):
        calls.append(payload)
        return {"summary": longer_conclusions}
    assert choose_summary(SUMMARY, paper_abstract, [{"results": "current paper"}], retry) == (longer_conclusions, None)
    assert len(calls) == 1


def test_summary_evidence_is_synthesis_and_requires_located_quote():
    record = field_records("paper", "paper", {"summary": SUMMARY}, {"summary": "总结"})[0]
    chunks = [{"file_id": "main", "chunk_index": 0, "page_start": 2,
               "content": "The Im-3m phase is predicted to have Tc of 191–204 K at 200 GPa."}]
    raw = {"status": "supported", "reason": "本文的计算结果和相应压力支持所述相变与 Tc 结论。",
           "evidences": [{"file_id": "main", "chunk_index": 0,
                          "quote": "The Im-3m phase is predicted to have Tc of 191–204 K at 200 GPa."}]}
    checked = evidence.checked_result(record, raw, chunks)
    assert checked["status"] == "supported"
    assert checked["source_kind"] == "paper_synthesis"
    assert checked["ai_reason"] == raw["reason"]
    assert checked["evidences"][0]["page_start"] == 2
    no_source = evidence.checked_result(record, {**raw, "evidences": []}, chunks)
    assert no_source["status"] == "missing"
    assert "缺少可定位" in no_source["ai_reason"]


def test_aggregated_summary_reason_tracks_all_located_batches():
    row = {"key": "summary", "field": "paper.summary"}
    candidates = [{"status": "supported", "reason": "相变有依据", "evidences": [{"quote": "phase"}],
                   "ai_reason": "相变有依据", "fields": ["paper.summary"]},
                  {"status": "supported", "reason": "Tc 有依据", "evidences": [{"quote": "Tc"}],
                   "ai_reason": "Tc 有依据", "fields": ["paper.summary"]}]
    result = evidence.aggregate_candidates([row], {"summary": candidates}, {"summary": []}, "test")["summary"]
    assert result["source_kind"] == "paper_synthesis"
    assert result["ai_reason"] == "相变有依据；Tc 有依据"
