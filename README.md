# Rosetta Plotter

Step-by-step pen plotting for Evil Mad Scientist AxiDraw machines, built for students.
Windows only. Licensed AGPL-3.0-or-later. Bundles the EMS AxiDraw API (GPL).

Developer setup:

    py -3.12 -m venv .venv
    .venv\Scripts\python -m pip install -c constraints.txt vendor\AxiDraw_API.zip
    .venv\Scripts\python -m pip install -c constraints.txt -e ".[dev]"
    .venv\Scripts\python -m pytest

If py -3.12 fails, run the full path to a Python 3.12 python.exe instead.

## The student window (ui/)

The window's page is a Vite + TypeScript + Lit app in `ui/`:

    cd ui
    npm install
    npm test            # unit and component tests (jsdom)
    npm run dev         # the page in a browser, against a demo backend with a pretend plotter
    npm run build       # writes ui\dist, which the real window loads

Then run the real window with `.venv\Scripts\python -m rosetta.app.main`. To work on the page live inside the real
window, keep `npm run dev` running and start the window with `$env:ROSETTA_UI_URL="http://localhost:5173"`.

## Printing into the app

`packaging\printer\Install Rosetta Printer.bat` adds a Windows printer named "Rosetta Plotter" (it asks for
administrator rights once). It is Windows' own "Microsoft Print To PDF" driver on a local port whose name is
`%ProgramData%\Rosetta Plotter\Print\print.pdf`, so printing to it from Illustrator, Rhino or anything else
writes that file without asking. While the app is open, `rosetta.app.printinbox` sees each new print, copies it
to `%APPDATA%\RosettaPlotter\prints` and imports the copy into the Jobs list. `Remove Rosetta Printer.bat`
takes the printer away again. The student installer puts both in `{app}\Printer` with a Start menu shortcut, and
its "Add the Rosetta Plotter printer" checkbox (ticked by default) runs the install script at the end of setup,
after one Windows permission prompt.

## Running the app

Run the app (it shows the student window once `ui\dist` is built, and a bridge console for trying every method until then):

    .venv\Scripts\python -m rosetta.app.main

The bridge console can't answer `close_requested`, so to close it mid-plot, call `quit_confirmed`.

The bridge between Python and the page is documented in docs/bridge.md.
