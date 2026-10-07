"""What the student is putting together (spec §6.4): the paper, and the pieces of artwork on it.

The plotter's model and pen settings live on Machine; the plot itself in PlotController.
Methods here are called from several bridge threads; each change is one list or attribute update.
"""
import dataclasses
import itertools
import math
from dataclasses import dataclass
from pathlib import Path

from rosetta.compose import (
    DEFAULT_MARGIN_MM, Job, Material, PlacedPiece, Placement, compose_job, initial_placement,
)
from rosetta.errors import ImportProblem, UserProblem
from rosetta.loader import Artwork, load_artwork
from rosetta.models import MachineModel
from rosetta.pdf_import import page_count

DUPLICATE_OFFSET_MM = 10.0
SHRUNK_BELOW = 0.99  # an import placed smaller than this was shrunk to fit, and the page says so
MAX_SCALE = 100.0
ROTATIONS = (0, 90, 180, 270)
GONE = "That drawing isn't on the paper anymore."


@dataclass
class Piece:
    id: str
    path: str
    page: int  # 0-based
    artwork: Artwork
    placement: Placement


def pages_in(path) -> int:
    """How many pages a file has: PDF and AI files can have several; everything else has one."""
    path = Path(path)
    if not path.is_file():
        raise ImportProblem(f"The file {path.name} can't be found.")
    if path.suffix.lower() in (".pdf", ".ai"):
        return page_count(path)
    return 1


class Session:
    def __init__(self, material: Material, margin_mm: float = DEFAULT_MARGIN_MM):
        self.material = material
        self.margin_mm = margin_mm
        self.skip_white = True
        self.pieces: list[Piece] = []
        self._ids = itertools.count(1)

    def add(self, path, page: int = 0) -> tuple[Piece, bool]:
        """Import a file onto the paper (slow for big files). Returns the piece and whether it was
        shrunk to fit inside the margins (spec §5, step 3)."""
        artwork = load_artwork(Path(path), page)
        placement = initial_placement(artwork, self.material, self.margin_mm)
        piece = Piece(self._new_id(), str(path), page, artwork, placement)
        self.pieces.append(piece)
        return piece, placement.scale < SHRUNK_BELOW

    def get(self, piece_id: str) -> Piece:
        for piece in self.pieces:
            if piece.id == piece_id:
                return piece
        raise UserProblem(GONE)

    def place(self, piece_id: str, x, y, scale, rotation) -> Piece:
        piece = self.get(piece_id)
        piece.placement = _checked(Placement(float(x), float(y), float(scale), int(rotation) % 360))
        return piece

    def duplicate(self, piece_id: str) -> Piece:
        original = self.get(piece_id)
        placement = dataclasses.replace(
            original.placement,
            x=original.placement.x + DUPLICATE_OFFSET_MM,
            y=original.placement.y + DUPLICATE_OFFSET_MM,
        )
        copy = Piece(self._new_id(), original.path, original.page, original.artwork, placement)
        self.pieces.insert(self.pieces.index(original) + 1, copy)
        return copy

    def remove(self, piece_id: str) -> None:
        self.pieces.remove(self.get(piece_id))

    def clear(self) -> None:
        self.pieces.clear()

    def compose(self, model: MachineModel) -> Job:
        placed = [PlacedPiece(piece.artwork, piece.placement) for piece in list(self.pieces)]
        return compose_job(model, self.material, placed, skip_white=self.skip_white)

    def _new_id(self) -> str:
        return f"piece-{next(self._ids)}"


def _checked(placement: Placement) -> Placement:
    """Placements come from the page; refuse values that would put NaN or mirrored art in a plot."""
    if not (math.isfinite(placement.x) and math.isfinite(placement.y)):
        raise ValueError(f"Placement position must be finite: {placement}")
    if not (math.isfinite(placement.scale) and 0 < placement.scale <= MAX_SCALE):
        raise ValueError(f"Placement scale must be above 0 and at most {MAX_SCALE:g}: {placement}")
    if placement.rotation not in ROTATIONS:
        raise ValueError(f"Placement rotation must be a multiple of 90 degrees: {placement}")
    return placement
