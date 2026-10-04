"""Synthetic SVGs that mimic what each app exports. Real exports are tested in Task 20."""

# Illustrator "Export As" with Responsive on: no width/height, viewBox in points, CSS classes.
# 283.464567 pt = 100 mm.
ILLUSTRATOR_EXPORT = b"""<?xml version="1.0" encoding="UTF-8"?>
<svg id="Layer_1" data-name="Layer 1" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 566.929134 283.464567">
  <defs><style>.cls-1{fill:none;stroke:#ff0000;stroke-miterlimit:10;}.cls-2{fill:#0000ff;}</style></defs>
  <rect class="cls-1" x="0" y="0" width="283.4646" height="283.4646"/>
  <circle class="cls-2" cx="425.1969" cy="141.7323" r="70.8661"/>
</svg>"""

# Illustrator "Save As" style: px sizes that really mean points (EMS process_ai fix).
ILLUSTRATOR_PX = b"""<?xml version="1.0" encoding="utf-8"?>
<!-- Generator: Adobe Illustrator 30.8.1, SVG Export Plug-In . SVG Version: 6.00 Build 0)  -->
<svg version="1.1" xmlns="http://www.w3.org/2000/svg" x="0px" y="0px" width="612px" height="792px" viewBox="0 0 612 792">
  <line fill="none" stroke="#000000" x1="72" y1="72" x2="144" y2="72"/>
</svg>"""

# Affinity: percent sizes, serif namespace, inline styles. 377.95276 px @96 = 100 mm.
AFFINITY_EXPORT = b"""<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<svg width="100%" height="100%" viewBox="0 0 377.95276 188.97638" version="1.1"
     xmlns="http://www.w3.org/2000/svg" xmlns:serif="http://www.serif.com/"
     style="fill-rule:evenodd;clip-rule:evenodd;stroke-linejoin:round;">
  <g id="Layer1" serif:id="Layer 1">
    <path d="M37.795276,37.795276L377.95276,37.795276" style="fill:none;stroke:#00f;stroke-width:1px;"/>
  </g>
</svg>"""

# Inkscape: real units and an Inkscape layer.
INKSCAPE_MM = b"""<?xml version="1.0" encoding="UTF-8"?>
<svg width="100mm" height="50mm" viewBox="0 0 100 50" version="1.1"
     xmlns="http://www.w3.org/2000/svg"
     xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape"
     xmlns:sodipodi="http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd">
  <g inkscape:groupmode="layer" inkscape:label="Layer 1">
    <path d="M 10,10 L 90,10 L 90,40" style="fill:none;stroke:#000000;stroke-width:0.3"/>
  </g>
</svg>"""

# Generic hand-written SVG: unitless size, no viewBox -> CSS px at 96 per inch.
GENERIC_PX = b"""<svg xmlns="http://www.w3.org/2000/svg" width="96" height="48">
  <line x1="0" y1="0" x2="96" y2="48" stroke="black"/>
</svg>"""

NO_SIZE = b"""<svg xmlns="http://www.w3.org/2000/svg"><line x1="0" y1="0" x2="1" y2="1" stroke="black"/></svg>"""

WITH_PROBLEMS = b"""<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"
     width="100mm" height="100mm" viewBox="0 0 100 100">
  <defs><text id="hidden">not counted</text><clipPath id="c"><rect width="50" height="50"/></clipPath></defs>
  <text x="10" y="10">Hello</text>
  <image x="0" y="0" width="10" height="10" xlink:href="photo.png"/>
  <g clip-path="url(#c)"><line x1="0" y1="0" x2="100" y2="100" stroke="black"/></g>
  <rect x="0" y="0" width="100" height="100" fill="#ffffff"/>
  <circle cx="50" cy="50" r="20" fill="#00ff00"/>
</svg>"""
