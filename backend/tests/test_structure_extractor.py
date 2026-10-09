from backend.ingest.structure_extractor import extract_structure_candidates


def test_extracts_explicit_fractional_coordinate_table_with_page_evidence():
    text = """<!-- page: 4 -->
The lattice parameters are a = 3.6, b = 3.6, c = 3.6, alpha = 90, beta = 90, gamma = 90.
Table 2 lists fractional coordinates:
atom x y z
Cu1 Cu 0 0 0
"""
    candidates = extract_structure_candidates(
        text,
        source={"file_id": "pdf-1", "filename": "paper.pdf", "role": "main"},
    )

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate["status"] == "valid"
    assert candidate["derivation"]["kind"] == "direct_coordinates"
    assert candidate["sources"][0]["page"] == 4
    assert candidate["validation"]["atom_count"] == 1
    assert candidate["representations"]["conventional"]["cif"]["text"]


def test_blocks_missing_coordinate_mode_instead_of_guessing():
    text = """<!-- page: 2 -->
The cell has a = 3, b = 3, c = 3, alpha = 90, beta = 90, gamma = 90.
Atomic coordinates:
Cu1 Cu 0 0 0
"""
    candidates = extract_structure_candidates(
        text,
        source={"file_id": "pdf-2", "filename": "paper.pdf"},
    )

    assert len(candidates) == 1
    assert candidates[0]["status"] == "blocked"
    assert candidates[0]["validation"]["code"] == "pdf_structure_incomplete"


def test_keeps_explicit_structures_on_separate_pages_separate():
    text = """<!-- page: 1 -->
Lattice a = 3, b = 3, c = 3, alpha = 90, beta = 90, gamma = 90. Fractional coordinates:
Cu1 Cu 0 0 0
<!-- page: 2 -->
Lattice a = 4, b = 4, c = 4, alpha = 90, beta = 90, gamma = 90. Fractional coordinates:
Fe1 Fe 0 0 0
"""
    candidates = extract_structure_candidates(text, source={"file_id": "pdf-3", "filename": "paper.pdf"})

    assert len(candidates) == 2
    assert [item["sources"][0]["page"] for item in candidates] == [1, 2]
    assert [item["validation"]["elements"] for item in candidates] == [["Cu"], ["Fe"]]


def test_expands_numeric_wyckoff_sites_and_marks_derivation():
    text = """<!-- page: 6 -->
Space group Fm-3m (225); lattice a = 3.6, b = 3.6, c = 3.6, alpha = 90, beta = 90, gamma = 90.
Wyckoff sites:
Cu 4a 0 0 0
"""
    candidates = extract_structure_candidates(text, source={"file_id": "pdf-4", "filename": "paper.pdf"})

    assert len(candidates) == 1
    assert candidates[0]["status"] == "valid"
    assert candidates[0]["source_kind"] == "pdf_derived"
    assert candidates[0]["derivation"]["kind"] == "space_group_expansion"
    assert candidates[0]["validation"]["atom_count"] == 4


def test_splits_phase_table_and_derives_only_space_group_cell_constraints():
    text = """<!-- page: 4 -->
Table S1 | Structure parameters of predicted P1 and Im-3m structures.
Atomic coordinates (fractional) x y z
P1 a=6.389 H(1a) 0.1 0.2 0.3
(20 GPa) b=6.432 S(1a) 0.4 0.5 0.6
c=5.355
\uf061=90.119
\uf062=89.846
\uf067=90.148
Im-3m a=2.984 H(6b) 0 0.5 0.5
(200 GPa) S(2a) 0.5 0.5 0.5
Figure S1 | Phonon dispersion
"""
    candidates = extract_structure_candidates(text, source={"file_id": "supp", "filename": "supp.pdf"})
    assert len(candidates) == 2
    assert [item["status"] for item in candidates] == ["valid", "valid"]
    assert [item["validation"]["atom_count"] for item in candidates] == [2, 8]
    assert [item["reported_structure"]["pressure_value_gpa"] for item in candidates] == [20.0, 200.0]
    assert candidates[1]["derivation"]["inferred_cell_parameters"] == ["b", "c", "alpha", "beta", "gamma"]


def test_docling_split_cells_late_caption_and_duplicate_sites_do_not_mix_phases():
    text = """<!-- page: 4 -->
Atomic coordinates (fractional)
P1
a=6.389
H(1a)
0.1
0.2
0.3
(20 GPa)
b=6.432
S(1a)
0.4
0.5
0.6
c=5.355
\uf061=90.119
\uf062=89.846
\uf067=90.148
Cccm
a=8.157
H(16m)
0.33285
0.66798
0.24948
(60 GPa)
b=8.181
c=4.830
Table S1 | Structure parameters of predicted phases.
<!-- page: 5 -->
S(8l)
0.75864
0.07766
0.50000
R3m
a=4.405
H(9b)
0.51430
0.02860
0.29941
(130 GPa)
c=2.689
S(3a)
0.66667
0.33333
0.62631
Im-3m
a=2.984
H(6b)
0
0.5
0.5
(200 GPa)
S(2a)
0.5
0.5
0.5
S(8l)
0.75864
0.07766
0.50000
R3m
a=4.405
H(9b)
0.51430
0.02860
0.29941
c=2.689
S(3a)
0.66667
0.33333
0.62631
Im-3m
a=2.984
H(6b)
0
0.5
0.5
S(2a)
0.5
0.5
0.5
Figure S1 | Phonon dispersion
"""
    candidates = extract_structure_candidates(text, source={"file_id": "supp", "filename": "supp.pdf"})
    assert [item["reported_structure"]["space_group_symbol"] for item in candidates] == ["P1", "Cccm", "R3m", "Im-3m"]
    assert [item["validation"]["atom_count"] for item in candidates] == [2, 24, 12, 8]
    assert [item["reported_structure"]["pressure_value_gpa"] for item in candidates] == [20, 60, 130, 200]
    assert candidates[2]["derivation"]["rounded_fractional_sites"] == ["S(3a)"]
