# Rosetta Plotter

Step-by-step pen plotting for Evil Mad Scientist AxiDraw machines, built for students.
Windows only. Licensed AGPL-3.0-or-later. Bundles the EMS AxiDraw API (GPL).

Developer setup:

    py -3.12 -m venv .venv
    .venv\Scripts\python -m pip install -c constraints.txt vendor\AxiDraw_API.zip
    .venv\Scripts\python -m pip install -c constraints.txt -e ".[dev]"
    .venv\Scripts\python -m pytest

If py -3.12 fails, run the full path to a Python 3.12 python.exe instead.
