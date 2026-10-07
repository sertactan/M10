from data.providers.sec_cik_lookup import SecCikNameLookupProvider


def test_sec_cik_lookup_keeps_only_unique_normalized_names() -> None:
    payload = """ACME, INC.:123:
UNIQUE CORP:456:
ACME INC:789:
NAME WITH: COLON LLC:999:
bad row
"""
    mapping = SecCikNameLookupProvider.parse(payload)
    # Punctuation normalization makes the two ACME names ambiguous.
    assert "ACME INC" not in mapping
    assert mapping["UNIQUE CORP"] == "0000000456"
    assert mapping["NAME WITH COLON LLC"] == "0000000999"
