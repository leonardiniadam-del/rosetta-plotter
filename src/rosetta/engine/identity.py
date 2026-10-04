"""The plotter's model, stored in its EBB nickname so every laptop recognizes it (spec §8)."""
import re
import unicodedata
from dataclasses import dataclass

NICKNAME_MAX = 16  # EBB nickname limit
_SUFFIX = re.compile(r"(?:^|\s)m([1-7])p([1-3])$")
_WHITESPACE = re.compile(r"\s+")
_UNSAFE = re.compile(r"[^A-Za-z0-9 _.-]")  # the EBB command line is plain ASCII; "\r" ends a command


@dataclass(frozen=True)
class Identity:
    model: int
    penlift: int
    label: str


def encode_nickname(identity: Identity) -> str:
    if not 1 <= identity.model <= 7:
        raise ValueError(f"Unknown AxiDraw model number: {identity.model}")
    if not 1 <= identity.penlift <= 3:
        raise ValueError(f"Unknown pen lift: {identity.penlift}")
    suffix = f"m{identity.model}p{identity.penlift}"
    room = NICKNAME_MAX - len(suffix) - 1
    folded = unicodedata.normalize("NFKD", identity.label)
    ascii_label = folded.encode("ascii", "ignore").decode("ascii")
    label = _UNSAFE.sub("", _WHITESPACE.sub(" ", ascii_label)).strip()  # "\r\n" becomes a space
    label = label[:room].strip() if room > 0 else ""
    return f"{label} {suffix}" if label else suffix


def decode_nickname(nickname: str) -> Identity | None:
    text = (nickname or "").strip()
    match = _SUFFIX.search(text)
    if not match:
        return None
    return Identity(int(match.group(1)), int(match.group(2)), text[: match.start()].strip())
