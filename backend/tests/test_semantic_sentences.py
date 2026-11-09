from backend.ingest.chunker import _split_by_sentence


def test_decimals_abbreviations_and_original_text_survive_boundaries():
    text = 'Dr. Wang reports lambda = 2.35 in Fig. 2. Tc reaches 200 K. Another condition gives 180 K.'
    parts = _split_by_sentence(text, 15)
    assert ''.join(parts) == text
    assert any('Dr. Wang' in p and '2.35' in p and 'Fig. 2.' in p for p in parts)
    assert not any(p.strip() in {'35', '2.'} for p in parts)
