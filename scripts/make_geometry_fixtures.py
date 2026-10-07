"""Write ui/src/geometry/fixtures.json: rosetta.geometry's answers, which the page's placement math
must match (ui/src/geometry/placement.test.ts). Run it again whenever rosetta.geometry changes:

    .venv\\Scripts\\python scripts\\make_geometry_fixtures.py
"""
import json
from pathlib import Path

from rosetta.geometry import place_point, rotated_size

ART = (40.0, 20.0)
ORIGIN = (12.0, 8.0)
POINTS = [(0.0, 0.0), (40.0, 0.0), (40.0, 20.0), (0.0, 20.0), (13.5, 7.25)]
PLACEMENTS = [  # x, y, scale, scale_y (None = same), rotation
    (0, 0, 1.0, None, 0), (10, 5, 2.0, None, 90), (10, 5, 0.5, None, 180), (3, 4, 1.5, None, 270),
    (10, 5, 1.0, None, 15), (2, 2, 1.25, None, 33.5), (0, 7, 0.8, None, 300),
    (5, 5, 2.0, 0.5, 0), (5, 5, 2.0, 0.5, 90), (5, 5, 1.5, 0.75, 33.5),
]


def main() -> None:
    cases = []
    for x, y, scale, scale_y, rotation in PLACEMENTS:
        both = scale if scale_y is None else scale_y
        cases.append({
            "placement": {"x": x, "y": y, "scale": scale, "scale_y": both, "rotation": rotation},
            "size": list(rotated_size(ART[0] * scale, ART[1] * both, rotation)),
            "points": [
                [list(point), list(place_point(point, ART[0], ART[1], x, y, scale, rotation, ORIGIN, scale_y))]
                for point in POINTS
            ],
        })
    out = Path(__file__).resolve().parents[1] / "ui" / "src" / "geometry" / "fixtures.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"art": list(ART), "origin": list(ORIGIN), "cases": cases}, indent=1), encoding="utf-8")
    print(f"Wrote {len(cases)} cases to {out}")


if __name__ == "__main__":
    main()
