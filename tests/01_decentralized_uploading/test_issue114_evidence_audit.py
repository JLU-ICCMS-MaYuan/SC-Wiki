"""反例驱动的定位、覆盖与工具预算验收。"""
import pytest
from backend.ingest.claim_evidence import Claim, EvidenceLocator, validate_claim
from backend.ingest.coverage_audit import audit_coverage
from backend.ingest.document_agent import DocumentTools, AgentStopped
from backend.ingest.document_ir import DocumentIR, DocumentBlock, DocumentTable, TableCell, PageGeometry


def document():
    return DocumentIR(document_id="d", source_file_id="f", source_sha256="a"*64, parse_profile="text",
        parser={"name":"pymupdf","version":"1","mode":"text"}, pages=[PageGeometry(pdf_page=1,width=600,height=800)],
        blocks=[DocumentBlock(block_id="b", block_type="paragraph", pdf_page=1, printed_page=115,
        reading_order=0, text="Tc = 200 K at 150 GPa.", bbox=(10,10,200,40), content_hash="b"*64)])


def candidate(**changes):
    evidence = {"file_id":"f","pdf_page":1,"block_id":"b","quote":"200 K", "parser":"pymupdf","parser_version":"1", **changes}
    return Claim(claim_id="c", target_path="value", value=200, raw_value="200 K", basis_kind="paper_quote",
                 source_kind="text_layer", evidences=[EvidenceLocator(**evidence)])


@pytest.mark.parametrize("change", [
    {"quote":""}, {"quote":"201 K"}, {"file_id":"elsewhere"}, {"pdf_page":2},
    {"parser_version":"fake"}, {"parser":"other"}, {"source_version":2},
    {"printed_page":116}, {"bbox":(0,0,1,1)}, {"source_kind":"ocr"},
    {"table_id":"wrong"}, {"block_id":"unknown"},
])
def test_forged_evidence_cannot_validate(change):
    assert not validate_claim(candidate(**change), document()).valid


def test_canonical_locator_comes_from_ir_and_empty_inference_stays_uncertain():
    result = validate_claim(candidate(), document())
    assert result.valid
    assert result.claim.evidences[0].bbox == (10,10,200,40)
    inference = Claim.model_validate(candidate().model_dump() | {"basis_kind":"general_knowledge", "evidences":[]})
    assert not validate_claim(inference, document()).valid


def test_ambiguous_quote_requires_explicit_block():
    ir = document()
    ir.blocks.append(ir.blocks[0].model_copy(update={"block_id":"other"}))
    assert not validate_claim(candidate(block_id=None), ir).valid
    assert validate_claim(candidate(), ir).valid


def test_reading_document_without_claim_does_not_pass_coverage():
    report = audit_coverage(document(), [], processed_pages=[1])
    assert report.requires_human and "block:b" in report.uncovered_candidates
    assert audit_coverage(document(), [candidate()], processed_pages=[1]).status == "complete"
    assert audit_coverage(document(), [candidate()]).requires_human
    assert audit_coverage(document(), [candidate(quote="201 K")], processed_pages=[1]).requires_human


def test_unclaimed_table_row_and_formula_are_detected():
    ir=document()
    ir.tables=[DocumentTable(table_id="t",pdf_page=1,row_count=2,column_count=1,
                             cells=[TableCell(cell_id="cell",row_index=0,column_index=0,block_id="b",text="200 K")])]
    ir.blocks.append(DocumentBlock(block_id="formula",block_type="formula",pdf_page=1,reading_order=1,
                                    text="T_c",content_hash="c"*64))
    report=audit_coverage(ir,[candidate()],processed_pages=[1])
    assert "table:t:row:1" in report.uncovered_candidates
    assert "region:formula" in report.uncovered_candidates


def _exclusion(**kwargs):
    base = {"file_id": "f", "category": "non_result_content", "reason": "not a result"}
    base.update(kwargs)
    return base


def test_declared_exclusion_unblocks_reviewed_row_and_region():
    ir=document()
    ir.tables=[DocumentTable(table_id="t",pdf_page=1,row_count=2,column_count=1,
                             cells=[TableCell(cell_id="cell",row_index=0,column_index=0,block_id="b",text="200 K")])]
    ir.blocks.append(DocumentBlock(block_id="fig",block_type="figure",pdf_page=1,reading_order=1,
                                    text="",content_hash="d"*64))
    exclusions=[_exclusion(table_id="t", row_index=1, category="header_or_unit_row"),
                _exclusion(block_id="fig", category="figure_without_data")]
    report=audit_coverage(ir,[candidate()],processed_pages=[1],exclusions=exclusions)
    assert "table:t:row:1" not in report.uncovered_candidates
    assert "region:fig" not in report.uncovered_candidates
    assert report.status == "complete" and not report.requires_human
    assert {e["category"] for e in report.exclusions} == {"header_or_unit_row", "figure_without_data"}


def test_unreadable_or_overwhelming_exclusions_keep_requires_human():
    ir=document()
    ir.tables=[DocumentTable(table_id="t",pdf_page=1,row_count=2,column_count=1,
                             cells=[TableCell(cell_id="cell",row_index=0,column_index=0,block_id="b",text="200 K")])]
    unreadable=audit_coverage(ir,[candidate()],processed_pages=[1],
                              exclusions=[_exclusion(table_id="t",row_index=1,category="unreadable",reason="cannot read")])
    assert "table:t:row:1" not in unreadable.uncovered_candidates
    assert unreadable.requires_human and "unreadable_exclusion_present" in unreadable.limitations
    # 疑似结果段落被大面积申报为"非结果内容"：提取可能不充分，保留人工复核。
    crowded=DocumentIR(document_id="d", source_file_id="f", source_sha256="a"*64, parse_profile="text",
        parser={"name":"pymupdf","version":"1","mode":"text"}, pages=[PageGeometry(pdf_page=1,width=600,height=800)],
        blocks=[DocumentBlock(block_id=f"b{i}", block_type="paragraph", pdf_page=1, printed_page=115,
        reading_order=i, text="Tc = 200 K at 150 GPa.", bbox=(10,10,200,40), content_hash="b"*64) for i in range(4)])
    overwhelmed=audit_coverage(crowded,[],processed_pages=[1],
                               exclusions=[_exclusion(block_id=f"b{i}",category="non_result_content") for i in range(4)])
    assert overwhelmed.requires_human and "excluded_ratio_above_threshold" in overwhelmed.limitations
    # 小样本（疑似块不足 4 个）比例无统计意义，不触发阈值；正当归类不计入比例。
    sparse=audit_coverage(document(),[],processed_pages=[1],
                          exclusions=[_exclusion(block_id="b",category="reference_or_background")])
    assert "excluded_ratio_above_threshold" not in sparse.limitations


def test_empty_text_figure_is_pipeline_boundary_not_missing():
    ir=document()
    ir.blocks.append(DocumentBlock(block_id="emptyfig",block_type="figure",pdf_page=1,reading_order=1,
                                    text="",content_hash="e"*64))
    ir.blocks.append(DocumentBlock(block_id="captionfig",block_type="figure",pdf_page=1,reading_order=2,
                                    text="Fig. 1 Tc versus pressure",content_hash="f"*64))
    report=audit_coverage(ir,[candidate()],processed_pages=[1])
    assert "region:emptyfig" not in report.uncovered_candidates
    assert report.figures_without_text_layer == 1
    assert "region:captionfig" in report.uncovered_candidates


def test_foreign_file_exclusion_is_ignored():
    report=audit_coverage(document(),[],processed_pages=[1],
                          exclusions=[_exclusion(file_id="other",block_id="b")])
    assert "block:b" in report.uncovered_candidates


def test_tool_scope_budget_and_retry_are_enforced():
    tools=DocumentTools({"f":document()})
    with pytest.raises(AgentStopped,match="tool_not_allowed"):
        tools.call("web_search",{"file_id":"f"})
    with pytest.raises(AgentStopped,match="file_not_in_task"):
        tools.call("read_document",{"file_id":"external"})
    with pytest.raises(AgentStopped,match="invalid_tool_arguments"):
        tools.call("read_document",{"file_id":"f","path":"/etc/passwd"})
    for i in range(2):
        tools.call("read_document",{"file_id":"f"},retry=True)
    with pytest.raises(AgentStopped,match="agent_retry_exhausted"):
        tools.call("read_document",{"file_id":"f"},retry=True)
    while tools.budget.actions<12:
        tools.call("read_page",{"file_id":"f","page":1})
    with pytest.raises(AgentStopped,match="agent_budget_exhausted"):
        tools.call("read_page",{"file_id":"f","page":1})
    assert all("thought" not in event for event in tools.audit)


def test_truncated_read_does_not_mark_page_read():
    ir=document();ir.blocks[0].text="x"*50001
    tools=DocumentTools({"f":ir})
    assert tools.call("read_page",{"file_id":"f","page":1})["truncated"]
    assert not tools.read_pages["f"]
    tools.cancelled=lambda:True
    with pytest.raises(AgentStopped,match="cancelled"):
        tools.call("read_document",{"file_id":"f"})


def test_default_rollout_requires_complete_quality_report():
    from backend.ingest.parser_rollout import RolloutConfig, RolloutStage, quality_gate_passed, select_profile
    with pytest.raises(ValueError,match="50"):
        RolloutConfig(stage=RolloutStage.DEFAULT)
    report=dict(annotated_papers=50,new_f1=.9,legacy_f1=.89,new_complex_recall=.9,legacy_complex_recall=.8,
        evidence_location_rate=.96,unsupported_writes=0,failure_recovery_passed=True,legacy_revision_review_passed=True)
    # 只有汇总数字的旧报告不能再用于默认切换，必须附逐论文/逐类别计数。
    assert not quality_gate_passed(report)
    for change in ({"annotated_papers":49},{"new_f1":.7},{"new_complex_recall":.8},
                   {"evidence_location_rate":.94},{"unsupported_writes":1},{"new_f1":float("nan")},
                   {"failure_recovery_passed":False}):
        assert not quality_gate_passed(report|change)
    config=RolloutConfig(stage=RolloutStage.GRAY,gray_ratio=1)
    assert select_profile(config,task_id="t",requested_profile="legacy")=="legacy"


def test_agent_cannot_change_scientific_value_and_stops_after_budget():
    from backend.ingest.document_agent import repair_claims
    original=candidate(quote="missing")
    bad=candidate().model_dump(mode="json");bad["value"]=999
    decisions=[]
    def decide(observation):
        decisions.append(observation)
        return {"claims":[bad],"action":{"name":"read_page","arguments":{"file_id":"f","page":1}}}
    claims,audit=repair_claims({"f":document()},[original],decide)
    assert len(decisions)==12 and audit["actions"]==12
    assert claims[0].value==200
    assert not validate_claim(claims[0],document()).valid
    fixed=candidate().model_dump(mode="json")
    claims,audit=repair_claims({"f":document()},[original],lambda _:{"done":True,"claims":[fixed]})
    assert validate_claim(claims[0],document()).valid


def test_empty_text_or_unparsed_table_does_not_pass_coverage():
    ir=document();ir.blocks[0].text=""
    assert audit_coverage(ir,[],processed_pages=[1]).requires_human
    ir.blocks[0].block_type="table"
    report=audit_coverage(ir,[],processed_pages=[1])
    assert "table:b:structure_missing" in report.uncovered_candidates


def test_material_only_claim_does_not_cover_tc_result():
    claim=candidate().model_copy(update={"value":{"material":"LaH10","pressure_value_gpa":150}})
    assert audit_coverage(document(),[claim],processed_pages=[1]).requires_human


def test_summary_must_keep_distinct_tc_values_from_same_paragraph():
    from backend.ingest.document_claims import missing_tc_measurements
    before=[candidate().model_copy(update={"claim_id":str(value),"value":{"tc_value_k":value,"tc_method":"allen_dynes"}}) for value in (200,210)]
    after=[candidate().model_copy(update={"value":{"property_code":"tc","value_number":200,"method_code":"allen_dynes"}})]
    assert missing_tc_measurements(before,after)==["210"]
