"""#135：栏目标签不能成为文件题名，也不因此取消真实文件冲突保护。"""
import pytest
from backend.ingest.document_identity import extract_identity, compare_identities

TITLE = 'Pressure-induced metallization of dense (H2S)2H2 with high-Tc superconductivity'


@pytest.mark.parametrize('header', ['SUBJECT AREAS: THEORY AND COMPUTATION CONDENSED-MATTER PHYSICS',
                                   'Subject areas： Theory and Computation'])
def test_subject_metadata_is_unknown_instead_of_a_conflicting_title(header):
    main = extract_identity({'file_id': 'main', 'role': 'main'}, f'## {header}\nDefang Duan, Yunxian Liu\n')
    supplement = extract_identity({'file_id': 'si', 'role': 'supplementary'},
        f'Supplementary information\n{TITLE}\nDefang Duan, Yunxian Liu\n')
    assert main['title'] is None
    checked = compare_identities([main, supplement])
    assert checked['status'] == 'unknown' and not checked['conflicts']


def test_real_title_or_doi_difference_still_requires_confirmation():
    main = extract_identity({'file_id': 'main', 'role': 'main'},
        f'## {TITLE}\nDefang Duan, Yunxian Liu\ndoi:10.1038/srep06968\n')
    other = extract_identity({'file_id': 'si', 'role': 'supplementary'},
        'Supplementary information\nDifferent actual reported superconducting material\nAuthor One, Author Two\ndoi:10.1000/other\n')
    assert {v['field'] for v in compare_identities([main, other])['conflicts']} == {'title', 'doi'}


def test_unheaded_first_page_and_wrapped_si_title_are_complete():
    main = extract_identity({'file_id': 'main', 'role': 'main'},
        'Pressure-induced metallization of dense\n(H2S)2H2 with high-Tc superconductivity\nDefang Duan, Yunxian Liu\n')
    si = extract_identity({'file_id': 'si', 'role': 'supplementary'},
        '1\nSupplementary information\nPressure-induced metallization of dense (H2S)2H2 with high-Tc\nsuperconductivity\nDefang Duan, Yunxian Liu\n')
    assert main['title'] == TITLE and si['title'] == TITLE
    assert compare_identities([main, si])['status'] == 'ok'
