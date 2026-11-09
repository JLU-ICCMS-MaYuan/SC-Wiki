from backend.ingest.source_highlight import text_locator


def test_unique_span_keeps_context_and_original_indices():
    text = 'At 150 GPa, Tc reaches 200 K. Other conditions differ.'
    result = text_locator(text, '200 K')
    a, b = result['char_interval']
    assert text[a:b] == '200 K' and a > 0 and b < len(text)
    assert result['match_kind'] == 'exact'


def test_repeated_value_is_not_first_occurrence_and_hash_changes():
    assert text_locator('100 K; 100 K', '100 K')['match_kind'] == 'ambiguous'
    assert text_locator('100 K', '200 K')['char_interval'] is None
    assert text_locator('100 K', '100 K')['text_sha256'] != text_locator('200 K', '200 K')['text_sha256']


def test_layout_whitespace_preserves_original_span():
    text = 'Tc = 200\n K for this state.'
    result = text_locator(text, '200 K')
    a, b = result['char_interval']
    assert text[a:b] == '200\n K'
    assert result['match_kind'] == 'whitespace_equivalent'
