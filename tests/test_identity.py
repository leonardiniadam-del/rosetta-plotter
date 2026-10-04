import pytest

from rosetta.engine.identity import NICKNAME_MAX, Identity, decode_nickname, encode_nickname


def test_encode_fits_in_16_characters():
    assert encode_nickname(Identity(2, 1, "PSU Lab A")) == "PSU Lab A m2p1"
    long_name = encode_nickname(Identity(5, 3, "Portland State Architecture"))
    assert len(long_name) <= NICKNAME_MAX
    assert long_name.endswith(" m5p3")


def test_encode_without_label():
    assert encode_nickname(Identity(6, 1, "")) == "m6p1"


def test_encode_keeps_only_safe_ascii_characters():
    # "\r" would end the EBB command early, and a non-ASCII byte makes the whole write fail.
    assert encode_nickname(Identity(2, 1, "Café\r\nLab 🙂")) == "Cafe Lab m2p1"
    assert encode_nickname(Identity(2, 1, "🙂🙂")) == "m2p1"


def test_encode_rejects_a_model_or_pen_lift_that_decode_could_not_read():
    for identity in (Identity(8, 1, ""), Identity(0, 1, ""), Identity(2, 4, ""), Identity(2, 0, "")):
        with pytest.raises(ValueError):
            encode_nickname(identity)


def test_decode_round_trip():
    for identity in (Identity(2, 1, "PSU Lab A"), Identity(6, 1, "")):
        assert decode_nickname(encode_nickname(identity)) == identity


def test_decode_foreign_nickname_is_none():
    assert decode_nickname("Jen's AxiDraw") is None
    assert decode_nickname("") is None
