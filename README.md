# Rosetta Plotter

Step-by-step pen plotting for Evil Mad Scientist AxiDraw machines, built for students.
Windows only. Licensed AGPL-3.0-or-later. Bundles the EMS AxiDraw API (GPL).

Developer setup:

    py -3.12 -m venv .venv
    .venv\Scripts\python -m pip install vendor\AxiDraw_API.zip
    .venv\Scripts\python -m pip install -e ".[dev]"
    .venv\Scripts\python -m pytest
