# PyInstaller spec for the student app: a one-folder, windowed build (design spec section 2: one-folder because
# antivirus tools flag one-file builds more often).
#
#   .venv\Scripts\pyinstaller --noconfirm --distpath build\pyinstaller\dist --workpath build\pyinstaller\work packaging\rosetta.spec
#
# (scripts\build_installer.ps1 runs it.) The result is build\pyinstaller\dist\Rosetta Plotter\RosettaPlotter.exe.
# Build the page first (`npm run build` in ui\): ui\dist is bundled at ui/dist, where rosetta.app.main.ui_entry
# looks under sys._MEIPASS.
import re
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules
from PyInstaller.utils.win32.versioninfo import (
    FixedFileInfo, StringFileInfo, StringStruct, StringTable, VarFileInfo, VarStruct, VSVersionInfo,
)

ROOT = Path(SPECPATH).resolve().parent  # noqa: F821 (SPECPATH is set by PyInstaller)
SRC = ROOT / "src"
UI_DIST = ROOT / "ui" / "dist"
ICON = ROOT / "packaging" / "rosetta.ico"

if not (UI_DIST / "index.html").is_file():
    raise SystemExit("ui\\dist\\index.html is missing: run `npm run build` in ui\\ first")

VERSION = re.search(r'__version__\s*=\s*"([^"]+)"', (SRC / "rosetta" / "__init__.py").read_text(encoding="utf-8")).group(1)
NUMBERS = tuple((int(part) for part in re.findall(r"\d+", VERSION)[:4]))
NUMBERS = NUMBERS + (0,) * (4 - len(NUMBERS))

# The EMS engine loads some of its modules by name (axidrawinternal.axidraw_conf, plot_utils_import),
# so collect every submodule rather than trusting the import scan.
hiddenimports = []
for package in ("rosetta", "pyaxidraw", "axidrawinternal", "plotink", "ink_extensions", "ink_extensions_utils"):
    hiddenimports += collect_submodules(package)
hiddenimports += ["serial.tools.list_ports", "serial.tools.list_ports_windows"]
# axidrawinternal.axidraw imports these by name too (plot_utils_import.from_dependency_import), for its webhook.
hiddenimports += ["requests", "urllib3"]

excludes = [
    # Development and test tools.
    "pytest", "_pytest", "pluggy", "iniconfig", "PyInstaller", "pip", "setuptools", "_distutils_hack",
    "pygments", "tkinter", "rosetta.cli",
    # pywebview backends other than WebView2 (edgechromium).
    "webview.platforms.android", "webview.platforms.cocoa", "webview.platforms.gtk", "webview.platforms.qt",
    "webview.platforms.cef",  # (mshtml stays: pywebview falls back to it when WebView2 is missing)
]
hiddenimports = [name for name in hiddenimports if not any(name == ex or name.startswith(ex + ".") for ex in excludes)]

a = Analysis(  # noqa: F821
    [str(ROOT / "packaging" / "rosetta_entry.py")],
    pathex=[str(SRC)],
    binaries=[],
    datas=[(str(UI_DIST), "ui/dist")],
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
)

# PyMuPDF ships its C headers and import libraries (pymupdf/mupdf-devel) for building extensions; the app
# doesn't need them, nor pywebview's Android jar. (pywebview's lib/runtimes folders for every architecture
# must stay: it checks they exist when it starts.)
def _unneeded(dest: str) -> bool:
    dest = dest.replace("\\", "/")
    return dest.startswith("pymupdf/mupdf-devel/") or dest.endswith("pywebview-android.jar")

a.datas = [entry for entry in a.datas if not _unneeded(entry[0])]
a.binaries = [entry for entry in a.binaries if not _unneeded(entry[0])]

pyz = PYZ(a.pure)  # noqa: F821

version_info = VSVersionInfo(
    ffi=FixedFileInfo(filevers=NUMBERS, prodvers=NUMBERS),
    kids=[
        StringFileInfo([StringTable("040904B0", [
            StringStruct("CompanyName", "Rosetta Plotter"),
            StringStruct("FileDescription", "Rosetta Plotter"),
            StringStruct("FileVersion", VERSION),
            StringStruct("InternalName", "RosettaPlotter"),
            StringStruct("LegalCopyright", "AGPL-3.0-or-later"),
            StringStruct("OriginalFilename", "RosettaPlotter.exe"),
            StringStruct("ProductName", "Rosetta Plotter"),
            StringStruct("ProductVersion", VERSION),
        ])]),
        VarFileInfo([VarStruct("Translation", [0x0409, 1200])]),
    ],
)

exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="RosettaPlotter",
    debug=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    icon=str(ICON) if ICON.is_file() else None,
    version=version_info,
)

coll = COLLECT(  # noqa: F821
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="Rosetta Plotter",
)
