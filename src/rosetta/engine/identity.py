"""The plotter's model, stored in its EBB nickname so every laptop recognizes it (spec §8)."""
import re
from dataclasses import dataclass

NICKNAME_MAX = 16  # EBB nickname limit
_SUFFIX = re.compile(r"(?:^|\s)m([1-7])p([1-3])$")


@dataclass(frozen=True)
class Identity:
    model: int
    penlift: int
    label: str


def encode_nickname(identity: Identity) -> str:
    suffix = f"m{identity.model}p{identity.penlift}"
    room = NICKNAME_MAX - len(suffix) - 1
    label = identity.label.strip()[:room].strip() if room > 0 else ""
    return f"{label} {suffix}" if label else suffix


def decode_nickname(nickname: str) -> Identity | None:
    text = (nickname or "").strip()
    match = _SUFFIX.search(text)
    if not match:
        return None
    return Identity(int(match.group(1)), int(match.group(2)), text[: match.start()].strip())
