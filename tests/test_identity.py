from rosetta.engine.identity import NICKNAME_MAX, Identity, decode_nickname, encode_nickname


def test_encode_fits_in_16_characters():
    assert encode_nickname(Identity(2, 1, "PSU Lab A")) == "PSU Lab A m2p1"
    long_name = encode_nickname(Identity(5, 3, "Portland State Architecture"))
    assert len(long_name) <= NICKNAME_MAX
    assert long_name.endswith(" m5p3")


def test_encode_without_label():
    assert encode_nickname(Identity(6, 1, "")) == "m6p1"


def test_decode_round_trip():
    for identity in (Identity(2, 1, "PSU Lab A"), Identity(6, 1, "")):
        assert decode_nickname(encode_nickname(identity)) == identity


def test_decode_foreign_nickname_is_none():
    assert decode_nickname("Jen's AxiDraw") is None
    assert decode_nickname("") is None
