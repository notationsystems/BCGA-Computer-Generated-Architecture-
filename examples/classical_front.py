"""
A classical elevation whose proportions come from the knowledge graph.

Not one proportion is stated in this file. The order is chosen by decor from
the building's purpose, and the bay rhythm and the courses of the entablature
are resolved out of bcga_onto, so correcting a source in the corpus changes
what this builds. The plot decides the size; the canon decides the ratios.

Open this in Blender's text editor, put it in the BCGA Script field and press
Apply on a footprint.
"""

from pro import *

from bcga_onto import canon

# what the building is for; Vitruvius assigns the order from this, not taste
PURPOSE = "houses"
COLUMNS = 6
SPACING = "eustyle"

# tweakable from the redo panel
frontWidth = param(20)
podiumHeight = param(1.5)

COLOURS = {
    "podium": "#8d8378",
    "column": "#e8e2d8",
    "void": "#46505a",
    "architrave": "#ded7cb",
    "frieze": "#d3ccbf",
    "cornice": "#c7bfb1",
    "roof": "#6d5a4a",
}

_canon = canon()


@rule
def Begin():
    # ordinatio worked backwards: the plot fixes the width, so solve for M
    module = _canon.moduleForSpan(float(frontWidth), COLUMNS, SPACING)
    order = _canon.orderFor(PURPOSE)
    courses = _canon.elevationBands(
        order, module=module, spacing=SPACING, podium=float(podiumHeight))
    bays = _canon.colonnadeBands(COLUMNS, module=module, spacing=SPACING)
    extrude(sum(height for _, height in courses),
            top >> Roof(), side >> Elevation(courses, bays))


@rule
def Elevation(courses, bays):
    # the courses are absolute: their heights are what M makes them
    split(y, *[flt(height) >> Course(kind, bays) for kind, height in courses])


@rule
def Course(kind, bays):
    if kind != "column":
        color(COLOURS[kind])
        return
    # the rhythm is proportional, so every face of the block keeps it whatever
    # its width -- the canon fixes ratios, not sizes
    total = sum(width for _, width in bays)
    split(x, *[rel(width / total) >> Face(band) for band, width in bays])


@rule
def Face(kind):
    color(COLOURS[kind])


@rule
def Roof():
    color(COLOURS["roof"])
