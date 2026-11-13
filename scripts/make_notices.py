"""Write packaging/THIRD-PARTY-NOTICES.txt: the copyright notices and license texts for everything the
student installer ships besides Rosetta Plotter's own code.

Run it after a PyInstaller build (it reads build/pyinstaller/work/rosetta to see which Python packages were
bundled) and with ui/node_modules installed:

    .venv\\Scripts\\python scripts\\make_notices.py

scripts/build_installer.ps1 runs it between PyInstaller and Inno Setup.
"""
from __future__ import annotations

import ast
import importlib.metadata as metadata
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE_URL = "https://github.com/leonardiniadam-del/rosetta-plotter"
WORK = ROOT / "build" / "pyinstaller" / "work" / "rosetta"
OUT = ROOT / "packaging" / "THIRD-PARTY-NOTICES.txt"
AXIDRAW_ZIP = ROOT / "vendor" / "AxiDraw_API.zip"
NODE_MODULES = ROOT / "ui" / "node_modules"
# Upstream license files for packages whose wheels ship none, named <distribution>.txt (with the source URL).
FALLBACK_LICENSES = ROOT / "packaging" / "licenses"
FALLBACK_SOURCES = {
    "pyserial": "https://github.com/pyserial/pyserial/blob/v3.5/LICENSE.txt",
    "proxy_tools": "https://github.com/jtushman/proxy_tools/blob/master/LICENSE.txt",
}

# Packages Vite bundles into the student window (ui/dist). The minified bundle drops license comments,
# so their notices are carried here.
UI_PACKAGES = ["lit", "lit-html", "lit-element", "@lit/reactive-element", "@tabler/icons"]

# Our own package, and the EMS engine packages, which get their own section below.
SKIP = {"rosetta-plotter", "pyaxidraw", "axidrawinternal", "axicli"}
LICENSE_HINTS = ("LICEN", "COPYING", "NOTICE", "AUTHORS")
RULE = "=" * 78


def bundled_top_level_names() -> set[str]:
    """Top-level module and folder names PyInstaller put in the build."""
    names: set[str] = set()
    pyz = ast.literal_eval((WORK / "PYZ-00.toc").read_text(encoding="utf-8"))
    for entry in pyz[1]:
        names.add(entry[0].split(".")[0])
    collect = ast.literal_eval((WORK / "COLLECT-00.toc").read_text(encoding="utf-8"))
    for entry in collect[0]:
        dest = entry[0].replace("\\", "/")
        names.add(dest.split("/")[0].split(".")[0])
    return names


def bundled_distributions() -> list[metadata.Distribution]:
    owners = metadata.packages_distributions()
    wanted: set[str] = set()
    for name in bundled_top_level_names():
        wanted.update(owners.get(name, []))
    dists = {}
    for dist in metadata.distributions():
        name = dist.metadata["Name"]
        if name in wanted and name.lower() not in SKIP:
            dists[name.lower()] = dist
    return [dists[key] for key in sorted(dists)]


def license_label(dist: metadata.Distribution) -> str:
    md = dist.metadata
    label = md.get("License-Expression") or ""
    if not label:
        raw = (md.get("License") or "").strip()
        if raw and "\n" not in raw and len(raw) < 80:
            label = raw
    if not label:
        classifiers = [c.split("::")[-1].strip() for c in md.get_all("Classifier") or [] if c.startswith("License")]
        label = ", ".join(c for c in classifiers if c != "OSI Approved")
    return label or "see license text below"


def license_texts(dist: metadata.Distribution) -> list[tuple[str, str]]:
    texts = []
    for file in dist.files or []:
        path = str(file).replace("\\", "/")
        if ".dist-info/" not in path or not any(h in Path(path).name.upper() for h in LICENSE_HINTS):
            continue
        texts.append((Path(path).name, Path(dist.locate_file(file)).read_text(encoding="utf-8", errors="replace")))
    name = dist.metadata["Name"]
    fallback = FALLBACK_LICENSES / f"{name}.txt"
    if not texts and fallback.is_file():
        texts.append((f"LICENSE from {FALLBACK_SOURCES[name]}", fallback.read_text(encoding="utf-8", errors="replace")))
    return texts


def section(title: str, body: str) -> str:
    return f"{RULE}\n{title}\n{RULE}\n\n{body.strip()}\n\n"


def axidraw_section() -> str:
    with zipfile.ZipFile(AXIDRAW_ZIP) as archive:
        gpl = archive.read("AxiDraw_API_396/pyaxidraw/LICENSE.txt").decode("utf-8", errors="replace")
    intro = (
        "EMS AxiDraw API 3.9.6 (pyaxidraw, axidrawinternal)\n"
        "Copyright 2023 Windell H. Oskay, Evil Mad Scientist Laboratories\n"
        "License: GPL-2.0-or-later\n\n"
        "Rosetta Plotter uses these packages to drive the AxiDraw. Their complete source code is in\n"
        f"Rosetta Plotter's source repository, {SOURCE_URL}, at vendor/AxiDraw_API.zip.\n"
        "(plotink, also by Evil Mad Scientist Laboratories, is MIT-licensed and listed below.)\n\n"
    )
    return section("EMS AxiDraw API", intro + gpl)


def ui_section() -> str:
    parts = []
    for name in UI_PACKAGES:
        folder = NODE_MODULES / name
        package = json.loads((folder / "package.json").read_text(encoding="utf-8"))
        files = sorted(p for p in folder.iterdir() if any(h in p.name.upper() for h in LICENSE_HINTS))
        if not files:
            raise SystemExit(f"No license file found for {name} in {folder}")
        text = "\n".join(p.read_text(encoding="utf-8", errors="replace").strip() for p in files)
        parts.append(f"--- {name} {package['version']} ({package.get('license', '?')}) ---\n\n{text}\n")
    return section("Student window (ui/): bundled JavaScript packages and icons", "\n".join(parts))


def python_section() -> str:
    license_file = Path(sys.base_prefix) / "LICENSE.txt"
    text = license_file.read_text(encoding="utf-8", errors="replace")
    intro = (
        f"Python {sys.version.split()[0]} runtime, standard library, and the libraries the Windows build of\n"
        "Python ships with (including OpenSSL, libffi, bzip2, xz and Expat), whose notices follow.\n\n"
    )
    return section("Python", intro + text)


def other_section() -> str:
    return section(
        "Other components",
        "PyInstaller bootloader (packs the app into RosettaPlotter.exe): GPL-2.0-or-later with the PyInstaller\n"
        "bootloader exception, which allows distributing the packed program under its own license.\n"
        "See https://github.com/pyinstaller/pyinstaller/blob/develop/COPYING.txt\n\n"
        "Microsoft Visual C++ runtime (MSVCP140.dll, VCRUNTIME140.dll, VCRUNTIME140_1.dll) and the Microsoft Edge\n"
        "WebView2 Runtime installer: redistributed under Microsoft's terms for those components.",
    )


def main() -> None:
    if not (WORK / "PYZ-00.toc").is_file():
        raise SystemExit("No PyInstaller build found: run PyInstaller (packaging/rosetta.spec) first.")
    dists = bundled_distributions()
    index = [f"  {d.metadata['Name']} {d.version}: {license_label(d)}" for d in dists]
    out = [
        "Rosetta Plotter: third-party notices\n\n"
        "Rosetta Plotter is Copyright (C) 2026 Adam M. Leonardini and is licensed under the GNU Affero General\n"
        "Public License, version 3 or later (see LICENSE). It includes the third-party software below, each\n"
        "under its own license. This file is generated by scripts/make_notices.py.\n\n"
        "Source code: the complete source code for this program, including the EMS AxiDraw API it bundles,\n"
        f"is available at {SOURCE_URL}\n"
        "The Python packages below are unmodified; their source is on PyPI (https://pypi.org) under each\n"
        "package's name and version. This includes certifi and tqdm, whose MPL-2.0 files are available there.\n\n"
        "Bundled Python packages:\n" + "\n".join(index) + "\n\n",
        axidraw_section(),
    ]
    for dist in dists:
        texts = license_texts(dist)
        body = f"{dist.metadata['Name']} {dist.version}\nLicense: {license_label(dist)}\n"
        home = dist.metadata.get("Home-page") or ""
        if home:
            body += f"Home page: {home}\n"
        if texts:
            body += "\n" + "\n\n".join(f"--- {name} ---\n\n{text.strip()}" for name, text in texts)
        else:
            raise SystemExit(f"No license text for {dist.metadata['Name']}: add packaging/licenses/<name>.txt")
        out.append(section(dist.metadata["Name"], body))
    out += [ui_section(), python_section(), other_section()]
    OUT.write_text("".join(out), encoding="utf-8", newline="\r\n")
    print(f"Wrote {OUT} ({len(dists)} Python packages, {len(UI_PACKAGES)} UI packages)")
    for line in index:
        print(line)


if __name__ == "__main__":
    main()
