"""PyInstaller's entry script for RosettaPlotter.exe (packaging/rosetta.spec): the same as `rosetta-app`."""
import sys

from rosetta.app.main import main

if __name__ == "__main__":
    sys.exit(main())
