from backend.ingest.structure_extractor import extract_structure_candidates
import pytest


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


@pytest.mark.parametrize("text", [
    "The compound LaSc2H24 has space group P6/mmm at 300 GPa.",
    "Table S2. Lattice parameters and H-H distances.\na = b c\n300 4.735 3.216 1.076-1.204",
])
def test_structural_mentions_without_coordinate_evidence_are_not_candidates(text):
    assert extract_structure_candidates("<!-- page: 3 -->\n" + text, source={"file_id": "main"}) == []


@pytest.mark.parametrize("angles", ["α = 90 β = 90 γ = 90", "\uf061 = 90 \uf062 = 90 \uf067 = 90"])
def test_pdf_greek_cell_angles_are_read_without_claiming_missing_parameters(angles):
    text = f"<!-- page: 8 -->\na = 3 b = 3 c = 3 {angles}\nFractional coordinates:\nCu 0 0 0"
    candidate, = extract_structure_candidates(text, source={"file_id": "main"})
    assert candidate["status"] == "valid"
    assert candidate["validation"]["cell_parameters"]["gamma"] == 90


def test_pdf_row_layout_recovers_compounds_with_audited_rounding_derivation(tmp_path):
    import pymupdf
    doc = pymupdf.open()
    page = doc.new_page()
    rows = """Table S1. The calculated crystal structural parameters at 300 GPa.
Atomic coordinates (fractional)
Compound Space group Lattice parameters Atoms X Y Z
LaSc2 Fddd a = 4.248 La (8b) 0 0 0.5
b = 6.845 Sc (16f) 0 0.843 0
c = 7.682 alpha = 90 beta = 90 gamma = 90
LaSc2H24 P6/mmm a = 4.712 La (1b) 0 0 0.5
b = 4.712 Sc (2c) 0.333 0.667 0
c = 3.236 H (6m) 0.759 0.519 0.5
alpha = 90 H (6j) 0.762 0 0
beta = 90 H (12n) 0.614 0 0.289
gamma = 120"""
    page.insert_text((30, 40), rows, fontsize=9)
    path = tmp_path / "structure.pdf"
    doc.save(path); doc.close()
    flattened = """<!-- page: 1 -->
Table S1. The calculated crystal structural parameters at 300 GPa.
Atomic coordinates (fractional)
LaSc2 Fddd a = 4.248
b = 6.845 c = 7.682 alpha = 90 beta = 90 gamma = 90
La (8b)
Sc (16f)
0 0 0 .843 .5 0
"""
    # 没有行布局时不能按猜测重组列。
    assert extract_structure_candidates(flattened, source={"file_id": "supp"})[0]["status"] == "blocked"
    candidates = extract_structure_candidates(flattened, source={"file_id": "supp"}, pdf_path=path)
    assert [c["reported_structure"]["material"] for c in candidates] == ["LaSc2", "LaSc2H24"]
    assert [c["reported_structure"]["pressure_value_gpa"] for c in candidates] == [300, 300]
    assert candidates[0]["validation"]["atom_count"] == 24
    assert candidates[0]["reported_structure"]["independent_sites"] == 2
    assert candidates[1]["status"] == "valid"
    assert candidates[1]["confirmation"] == "unreviewed"
    assert candidates[1]["validation"]["atom_count"] == 27
    from backend.services.structure_candidates import read_atoms
    from pymatgen.io.ase import AseAtomsAdaptor
    from pymatgen.symmetry.analyzer import SpacegroupAnalyzer
    atoms = read_atoms("cif", candidates[1]["representations"]["conventional"]["cif"]["text"])
    assert atoms.get_chemical_symbols().count("H") == 24
    assert SpacegroupAnalyzer(AseAtomsAdaptor.get_structure(atoms), symprec=1e-4).get_space_group_number() == 191
    assert [x["site"] for x in candidates[1]["derivation"]["rounding_adjustments"]] == ["Sc(2c)", "H(6m)"]
    assert "0.333" in candidates[1]["sources"][0]["quote"]
    assert len({c["candidate_id"] for c in candidates}) == 2
    assert all(c["sources"][0]["page"] == 1 for c in candidates)


def test_rounding_projection_does_not_hide_incompatible_reported_coordinates():
    text = """<!-- page: 1 -->
Table S1. Structural parameters at 300 GPa.
Atomic coordinates (fractional)
Sc2 P6/mmm a=4 b=4 c=3 alpha=90 beta=90 gamma=120
Sc (2c) 0.340 0.667 0.000
"""
    candidate, = extract_structure_candidates(text, source={"file_id": "supp"})
    assert candidate["status"] == "blocked"
    assert candidate["representations"] == {}


def test_same_geometry_at_explicitly_different_pressures_is_not_merged():
    text = """<!-- page: 1 -->
Table S1 | Structure parameters
Atomic coordinates (fractional)
Im-3m a=2.984 H(6b) 0 0.5 0.5
(200 GPa) S(2a) 0.5 0.5 0.5
Im-3m a=2.984 H(6b) 0 0.5 0.5
(250 GPa) S(2a) 0.5 0.5 0.5
"""
    candidates = extract_structure_candidates(text, source={"file_id": "supp"})
    assert [c["reported_structure"]["pressure_value_gpa"] for c in candidates] == [200, 250]
    assert len({c["candidate_id"] for c in candidates}) == 2
