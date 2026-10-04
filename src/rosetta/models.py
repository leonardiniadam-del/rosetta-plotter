"""AxiDraw models and pen types.

Travel limits are copied from EMS axidraw_conf.py (inches) and converted with x 25.4,
so Rosetta's limits match the engine's exactly.
"""
from dataclasses import dataclass

from rosetta.units import MM_PER_INCH


@dataclass(frozen=True)
class MachineModel:
    number: int  # the EMS 'model' option value
    name: str
    travel_x_in: float
    travel_y_in: float

    @property
    def travel_mm(self) -> tuple[float, float]:
        return (self.travel_x_in * MM_PER_INCH, self.travel_y_in * MM_PER_INCH)


MODELS = {
    model.number: model
    for model in (
        MachineModel(1, "AxiDraw V2 / V3 / SE/A4", 11.81, 8.58),
        MachineModel(2, "AxiDraw V3/A3 or SE/A3", 16.93, 11.69),
        MachineModel(3, "AxiDraw V3 XLX", 23.42, 8.58),
        MachineModel(4, "AxiDraw MiniKit", 6.30, 4.00),
        MachineModel(5, "AxiDraw SE/A1", 34.02, 23.39),
        MachineModel(6, "AxiDraw SE/A2", 23.39, 17.01),
        MachineModel(7, "AxiDraw V3/B6", 7.48, 5.51),
    )
}


def get_model(number: int) -> MachineModel:
    try:
        return MODELS[number]
    except KeyError:
        raise ValueError(f"Unknown AxiDraw model number: {number}") from None


@dataclass(frozen=True)
class PenType:
    key: str
    label: str
    speed_pendown: int  # percent of maximum, EMS 'speed_pendown'


PEN_TYPES = {
    pen.key: pen
    for pen in (
        PenType("fineliner", "Fine liner", 25),
        PenType("marker", "Marker", 35),
        PenType("brush", "Brush / paint pen", 12),
    )
}

PEN_UP_SPEED = 75  # percent, same for all pen types
