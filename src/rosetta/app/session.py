"""What the student is putting together (manager UI spec §7): the Jobs list of imported files, the
pieces placed from them on the paper, and the pen colors to leave out.

The plotter's model and pen settings live on Machine; the plot itself in PlotController.
Methods here are called from several bridge threads; each change is one list or attribute update.
"""
import dataclasses
import itertools
import math
from dataclasses import dataclass
from pathlib import Path

from rosetta.compose import DEFAULT_MARGIN_MM, Job, Material, PlacedPiece, Placement, compose_job
from rosetta.errors import ImportProblem, UserProblem
from rosetta.geometry import rotated_size
from rosetta.loader import Artwork, load_artwork
from rosetta.models import MachineModel
from rosetta.pdf_import import page_count

DUPLICATE_OFFSET_MM = 10.0
MAX_SCALE = 100.0
GONE = "That drawing isn't on the paper anymore."
TOO_BIG = "Drawings can be scaled up to 10000%."
JOB_GONE = "That file isn't in the Jobs list anymore."


@dataclass
class QueuedJob:
    """An imported file waiting in the Jobs list. It can be placed on the paper any number of times."""

    id: str
    path: str
    page: int  # 0-based
    artwork: Artwork


@dataclass
class Piece:
    """One placed copy of a job."""

    id: str
    job_id: str
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
        self.jobs: list[QueuedJob] = []
        self.pieces: list[Piece] = []
        self.hidden_colors: set[str] = set()  # lowercase '#rrggbb' pens left out of the plot
        self._job_ids = itertools.count(1)
        self._piece_ids = itertools.count(1)

    # The Jobs list.

    def load_job(self, path, page: int = 0) -> QueuedJob:
        """Import a file into the Jobs list (slow for big files). Nothing is placed yet."""
        artwork = load_artwork(Path(path), page)
        job = QueuedJob(f"job-{next(self._job_ids)}", str(path), page, artwork)
        self.jobs.append(job)
        return job

    def get_job(self, job_id: str) -> QueuedJob:
        for job in self.jobs:
            if job.id == job_id:
                return job
        raise UserProblem(JOB_GONE)

    def remove_job(self, job_id: str) -> list[str]:
        """Take a file off the Jobs list, with every copy of it on the paper. Returns those pieces' ids."""
        job = self.get_job(job_id)
        removed = [piece.id for piece in self.pieces if piece.job_id == job_id]
        self.pieces = [piece for piece in self.pieces if piece.job_id != job_id]
        self.jobs.remove(job)
        return removed

    def place_job(self, job_id: str, x, y) -> Piece:
        """Put a copy of a job on the paper at full size, its top-left corner at (x, y) from the paper's corner."""
        job = self.get_job(job_id)
        placement = _checked(Placement(float(x), float(y), 1.0, 0.0))
        piece = Piece(f"piece-{next(self._piece_ids)}", job.id, job.artwork, placement)
        self.pieces.append(piece)
        return piece

    # Pieces on the paper.

    def get(self, piece_id: str) -> Piece:
        for piece in self.pieces:
            if piece.id == piece_id:
                return piece
        raise UserProblem(GONE)

    def place(self, piece_id: str, x, y, scale, rotation, scale_y=None) -> Piece:
        piece = self.get(piece_id)
        piece.placement = _checked(Placement(
            float(x), float(y), float(scale), float(rotation) % 360.0,
            None if scale_y is None else float(scale_y),
        ))
        return piece

    def duplicate(self, piece_id: str) -> Piece:
        original = self.get(piece_id)
        placement = dataclasses.replace(
            original.placement,
            x=original.placement.x + DUPLICATE_OFFSET_MM,
            y=original.placement.y + DUPLICATE_OFFSET_MM,
        )
        copy = Piece(f"piece-{next(self._piece_ids)}", original.job_id, original.artwork, placement)
        self.pieces.insert(self.pieces.index(original) + 1, copy)
        return copy

    def remove(self, piece_id: str) -> None:
        self.pieces.remove(self.get(piece_id))

    def clear(self) -> None:
        self.pieces.clear()

    def rotate_paper(self) -> None:
        """Turn the paper and everything on it 90° clockwise (manager UI spec §4.2).

        A point (px, py) on the sheet moves to (H - py, px), H being the sheet's height before the turn,
        so each piece's box (x, y, w, h) becomes (H - y - h, x, h, w) and its angle gains 90°.
        """
        old = self.material
        self.material = Material(old.x, old.y, old.height, old.width)
        for piece in self.pieces:
            placement, art = piece.placement, piece.artwork
            scale_y = placement.scale if placement.scale_y is None else placement.scale_y
            _width, height = rotated_size(art.width_mm * placement.scale, art.height_mm * scale_y, placement.rotation)
            piece.placement = dataclasses.replace(
                placement,
                x=old.height - placement.y - height,
                y=placement.x,
                rotation=(placement.rotation + 90.0) % 360.0,
            )

    # Pens.

    def set_color_visible(self, color: str, visible: bool) -> None:
        color = color.lower()
        if visible:
            self.hidden_colors.discard(color)
        else:
            self.hidden_colors.add(color)

    def compose(self, model: MachineModel, include_hidden: bool = False) -> Job:
        placed = [PlacedPiece(piece.artwork, piece.placement) for piece in list(self.pieces)]
        skip = frozenset() if include_hidden else frozenset(self.hidden_colors)
        return compose_job(model, self.material, placed, skip_white=self.skip_white, skip_colors=skip)


def _checked(placement: Placement) -> Placement:
    """Placements come from the page; refuse values that would put NaN or mirrored art in a plot."""
    if not (math.isfinite(placement.x) and math.isfinite(placement.y)):
        raise ValueError(f"Placement position must be finite: {placement}")
    for scale in (placement.scale, placement.scale if placement.scale_y is None else placement.scale_y):
        if not (math.isfinite(scale) and scale > 0):
            raise ValueError(f"Placement scale must be above 0: {placement}")
        if scale > MAX_SCALE:
            raise UserProblem(TOO_BIG)  # typed or dragged by the student
    if not math.isfinite(placement.rotation):
        raise ValueError(f"Placement rotation must be a finite number of degrees: {placement}")
    return placement
