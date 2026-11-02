"""#183/#204：结构审核必须收到当前文件，指纹不能代替原子坐标。"""
import json
from backend.ingest import property_evidence as ev, scientific_evidence as science
from backend.ingest.field_review import independent_fields


def test_structure_model_receives_current_file_and_versions_only_keep_summary(db_session):
    from backend.ingest.model_review import review_fields
    text = 'H\n1\n2 0 0\n0 2 0\n0 0 2\nH\n1\nDirect\n0 0 0\n'
    structure = {'structure_format': 'poscar', 'structure_text': text, 'review_key': 'current-geometry'}
    parent = science.structure_record(structure, 's', 'material_states[0].structure')
    parent['required'] = True
    row = independent_fields([parent])[0]
    chunks = [{'file_id': 'main', 'chunk_index': 0, 'content': 'H is at (0,0,0) in the 2 Angstrom cubic cell.'}]
    snapshot = ev.complete_snapshot('upload', 'structure-input-test', [row], chunks, {}, split_fields=False)
    def model(system, payload, **kwargs):
        record = json.loads(payload)['records'][0]
        assert record['structure_input']['structure_format'] == 'poscar'
        assert record['structure_input']['structure_text'] == text
        return {'results': [{'key': row['key'], 'status': 'supported', 'reason': '已读取实际原子坐标与原文核对',
                            'source_ids': ['review-source-0']}]}
    results = review_fields(snapshot['records'], chunks, model=model)
    assert results[row['key']]['status'] == 'supported'
    science.save_results(db_session, snapshot, results, 1)
    db_session.flush()
    cached = science.load_results(db_session, snapshot, 1)
    assert '_structure_model_input' not in json.dumps(cached)
    assert '_structure_model_input' not in json.dumps(ev.public_snapshot(snapshot, cached))
