"""Old-style (PostScript) Illustrator files -> SVG text.

Rhino's File > Export as "Adobe Illustrator (*.ai)" writes the Illustrator 3 format: a PostScript file
that starts with "%!PS-Adobe" instead of "%PDF", so PyMuPDF can't read it. Its drawing part is a short
list of operators, which this reads directly:

    x y m                    move to
    x y L | l                line to
    x1 y1 x2 y2 x3 y3 C | c  curve to (v/V and y/Y repeat one control point)
    S s  F f  B b  N n       paint the path: stroke, fill, both, neither (lower case closes it first)
    r g b XA | Xa            stroke | fill color, RGB 0-1 (K/k CMYK and G/g gray too)
    ... Lb (name) Ln ... LB  a layer; Lb's first number is 0 when the layer is hidden
    To ... TO                a text block: skipped, and reported like text in a PDF

Coordinates are points with y up; the page is the file's %%BoundingBox.
"""
import re
from dataclasses import dataclass
from pathlib import Path

from rosetta.errors import ImportProblem

PS_HEAD = b"%!PS-Adobe"
NOT_READABLE = ("This Illustrator file uses an old format Rosetta Plotter couldn't read. "
                "Export it again as PDF or SVG.")
NO_SIZE = "This Illustrator file doesn't say how big its drawing is. Export it again as PDF or SVG."

_TOKEN = re.compile(rb"\((?:\\.|[^\\)])*\)|\[|\]|/[^\s/\[\]()]*|[^\s\[\]()/]+")
_BBOX = re.compile(rb"^%%(?:HiRes)?BoundingBox:\s*(-?[\d.]+)\s+(-?[\d.]+)\s+(-?[\d.]+)\s+(-?[\d.]+)", re.M)
_PAINT = {"S": (False, True), "F": (True, False), "B": (True, True), "N": (False, False)}


@dataclass(frozen=True)
class AiPage:
    svg: str
    has_text: bool


def is_postscript_ai(path: Path) -> bool:
    with open(path, "rb") as handle:
        return handle.read(len(PS_HEAD)) == PS_HEAD


def ai_ps_to_svg(path: Path) -> AiPage:
    raw = Path(path).read_bytes()
    boxes = _BBOX.findall(raw)
    if not boxes:
        raise ImportProblem(NO_SIZE)
    # The last one wins: "%%BoundingBox: (atend)" files put the real box in the trailer.
    x0, y0, x1, y1 = (float(value) for value in boxes[-1])
    width, height = x1 - x0, y1 - y0
    if width <= 0 or height <= 0:
        raise ImportProblem(NO_SIZE)
    start = raw.find(b"%%EndSetup")
    body = raw[start:] if start >= 0 else raw
    try:
        reader = _Reader(x0, y1)
        reader.read(body)
    except (ValueError, IndexError) as exc:
        raise ImportProblem(NOT_READABLE) from exc
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{width:.4f}pt" height="{height:.4f}pt" viewBox="0 0 {width:.4f} {height:.4f}">'
        + "".join(reader.out)
        + "</svg>"
    )
    return AiPage(svg, reader.has_text)


def _rgb(r: float, g: float, b: float) -> str:
    return "#" + "".join(f"{round(min(max(v, 0.0), 1.0) * 255):02x}" for v in (r, g, b))


def _cmyk(c: float, m: float, y: float, k: float) -> str:
    return _rgb((1 - c) * (1 - k), (1 - m) * (1 - k), (1 - y) * (1 - k))


class _Reader:
    def __init__(self, left: float, top: float):
        self.left, self.top = left, top
        self.out: list[str] = []
        self.has_text = False
        self.stack: list = []
        self.path: list[str] = []
        self.current: tuple[float, float] = (0.0, 0.0)
        self.stroke, self.fill, self.width = "#000000", "#000000", 1.0
        self.hidden_depth = 0  # >0 while inside a hidden layer
        self.layer_hidden: list[bool] = []
        self.in_text = False

    def xy(self, x: float, y: float) -> str:
        return f"{x - self.left:.4f} {self.top - y:.4f}"

    def nums(self, count: int) -> list[float]:
        values = self.stack[-count:]
        if len(values) < count:
            raise ValueError("operator is missing its numbers")
        del self.stack[-count:]
        return [float(v) for v in values]

    def read(self, body: bytes) -> None:
        for line in body.splitlines():
            if line.startswith(b"%"):
                continue  # comments, including %AI5_BeginLayer markers (Lb/LB carry the layer)
            for match in _TOKEN.finditer(line):
                self.token(match.group().decode("latin-1"))

    def token(self, word: str) -> None:
        if self.in_text:
            if word == "TO":
                self.in_text = False
            return
        if word[0] in "([/" or word == "]":
            self.stack.append(word)
            return
        try:
            self.stack.append(float(word))
            return
        except ValueError:
            pass
        self.operator(word)

    def operator(self, op: str) -> None:
        if op == "To":
            self.in_text, self.has_text = True, True
            self.path = []
        elif op == "m":
            x, y = self.nums(2)
            self.path.append(f"M{self.xy(x, y)}")
            self.current = (x, y)
        elif op in ("L", "l"):
            x, y = self.nums(2)
            self.path.append(f"L{self.xy(x, y)}")
            self.current = (x, y)
        elif op in ("C", "c"):
            a, b, c, d, x, y = self.nums(6)
            self.path.append(f"C{self.xy(a, b)} {self.xy(c, d)} {self.xy(x, y)}")
            self.current = (x, y)
        elif op in ("V", "v"):  # first control point is the current point
            c, d, x, y = self.nums(4)
            self.path.append(f"C{self.xy(*self.current)} {self.xy(c, d)} {self.xy(x, y)}")
            self.current = (x, y)
        elif op in ("Y", "y"):  # second control point is the end point
            a, b, x, y = self.nums(4)
            self.path.append(f"C{self.xy(a, b)} {self.xy(x, y)} {self.xy(x, y)}")
            self.current = (x, y)
        elif op in ("H", "h"):
            self.path.append("Z")
        elif op.upper() in _PAINT and len(op) == 1:
            self.paint(op)
        elif op == "XA":
            self.stroke = _rgb(*self.nums(3))
        elif op == "Xa":
            self.fill = _rgb(*self.nums(3))
        elif op == "K":
            self.stroke = _cmyk(*self.nums(4))
        elif op == "k":
            self.fill = _cmyk(*self.nums(4))
        elif op == "G":
            g = self.nums(1)[0]
            self.stroke = _rgb(g, g, g)
        elif op == "g":
            g = self.nums(1)[0]
            self.fill = _rgb(g, g, g)
        elif op == "w":
            self.width = self.nums(1)[0]
        elif op == "Lb":
            values = self.nums(10)
            hidden = values[0] == 0
            self.layer_hidden.append(hidden)
            self.hidden_depth += hidden
        elif op == "LB":
            if self.layer_hidden:
                self.hidden_depth -= self.layer_hidden.pop()
        # Everything else (u/U groups, *u/*U compound paths, d, D, i, J, j, M, A, R, Ln, exec ...)
        # changes nothing Rosetta draws; whatever it pushed is dropped below.
        self.stack.clear()

    def paint(self, op: str) -> None:
        filled, stroked = _PAINT[op.upper()]
        if op.islower():
            self.path.append("Z")
        if self.path and not self.hidden_depth and (filled or stroked):
            self.out.append(
                f'<path d="{" ".join(self.path)}" '
                f'fill="{self.fill if filled else "none"}" '
                f'stroke="{self.stroke if stroked else "none"}" '
                f'stroke-width="{self.width:.4f}"/>'
            )
        self.path = []
