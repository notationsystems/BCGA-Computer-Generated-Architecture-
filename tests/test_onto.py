"""
Tests for the BCGA knowledge layer.

These need no Blender: the whole point of bcga_onto is that it is ordinary
Python over the standard library, so the corpus can be checked, queried and
served anywhere.

    python3 tests/test_onto.py
"""

import json
import math
import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bcga_onto import Audit, Canon, Graph, canon, loadCorpus
from bcga_onto.vocab import BCGA, SOURCE

RESULTS = []


def check(name, function):
    try:
        RESULTS.append(("PASS", name, function() or ""))
    except Exception as error:
        RESULTS.append(("FAIL", name, "%s: %s" % (type(error).__name__, error)))
        traceback.print_exc()


def near(a, b, tolerance=1e-9):
    return abs(a - b) <= tolerance


# ------------------------------------------------------------------- corpus

def t_corpus_loads():
    graph = loadCorpus()
    assert len(graph) > 100, "corpus looks too small: %d triples" % len(graph)
    return "%d triples over %d subjects" % (len(graph), len(graph.subjects()))


def t_five_orders():
    c = canon()
    heights = {c.label(s): c.graph.value(s, BCGA.columnHeight) for s in c.graph.typed(BCGA.Order)}
    expected = {"Tuscan": 7, "Doric": 8, "Ionic": 9, "Corinthian": 9.5, "Composite": 10}
    assert heights == expected, "column heights are %s, expected %s" % (heights, expected)
    return "column heights in M: %s" % ", ".join(
        "%s %g" % (name, heights[name]) for name in ("Tuscan", "Doric", "Ionic", "Corinthian", "Composite"))


def t_five_intercolumniations():
    c = canon()
    spaces = {c.label(s): c.graph.value(s, BCGA.clearSpace)
              for s in c.graph.typed(BCGA.Intercolumniation)}
    expected = {"Pycnostyle": 1.5, "Systyle": 2, "Eustyle": 2.25, "Diastyle": 3, "Araeostyle": 3.5}
    assert spaces == expected, "clear spaces are %s" % spaces
    preferred = [c.label(s) for s in c.graph.typed(BCGA.Intercolumniation)
                 if c.graph.value(s, BCGA.preferred)]
    assert preferred == ["Eustyle"], "the preferred spacing should be Eustyle, got %s" % preferred
    return "clear spaces in M, with %s preferred" % preferred[0]


def t_seven_room_shapes():
    c = canon()
    shapes = c.roomShapes()
    assert len(shapes) == 7, "Palladio permits exactly seven shapes, corpus has %d" % len(shapes)
    return "seven shapes: %s" % ", ".join(c.label(s) for s in shapes)


def t_every_fact_is_sourced():
    """A knowledge base without provenance is just numbers someone typed"""
    c = canon()
    unsourced = []
    for kind in (BCGA.Order, BCGA.Intercolumniation, BCGA.RoomShape, BCGA.CeilingRule,
                 BCGA.Principle, BCGA.Portico, BCGA.Rule, BCGA.Villa):
        for subject in c.graph.typed(kind):
            if not c.graph.objects(subject, SOURCE):
                unsourced.append(c.graph.shrink(subject))
    assert not unsourced, "these nodes cite no source: %s" % sorted(unsourced)
    return "every instance node carries a dcterms:source"


# ------------------------------------------------------------------ orders

def t_order_arithmetic():
    derived = canon().order("ionic", module=0.9)
    assert near(derived["columnHeight"], 8.1), derived["columnHeight"]
    assert near(derived["entablature"], 1.62), derived["entablature"]
    assert near(derived["architrave"], 0.486) and near(derived["frieze"], 0.486), derived
    assert near(derived["cornice"], 0.648), derived["cornice"]
    assert near(derived["architrave"] + derived["frieze"] + derived["cornice"],
                derived["entablature"]), "the 3:3:4 split must sum to the entablature"
    assert near(derived["neckDiameter"], 0.75), derived["neckDiameter"]
    return "Ionic at M=0.9: column %.2f, entablature %.2f (%.3f/%.3f/%.3f)" % (
        derived["columnHeight"], derived["entablature"],
        derived["architrave"], derived["frieze"], derived["cornice"])


def t_spacing_corrects_slenderness():
    plain = canon().order("ionic", module=1.0)
    wide = canon().order("ionic", module=1.0, spacing="araeostyle")
    assert plain["columnHeightModules"] == 9, plain
    assert wide["columnHeightModules"] == 8, wide
    assert wide["columnHeightFrom"] == "spacing"
    return "Ionic is 9 M alone, 8 M at araeostyle: the wider the bay the stouter the column"


def t_decor_chooses_the_order():
    c = canon()
    assert c.orderFor("libraries") == "Ionic"
    assert c.orderFor("workshops") == "Tuscan"
    assert c.orderFor("tombs") == "Corinthian"
    try:
        c.orderFor("data centre")
    except KeyError as error:
        assert "known purposes" in str(error), error
    else:
        raise AssertionError("an unassigned purpose should not silently pick an order")
    return "libraries->Ionic, workshops->Tuscan, tombs->Corinthian; unknown purposes refuse"


# --------------------------------------------------------------- colonnade

def t_colonnade_layout():
    laid = canon().colonnade(6, module=1.0, spacing="eustyle")
    assert laid["bays"] == 5, laid["bays"]
    assert laid["centreBay"] == 2, laid["centreBay"]
    widths = laid["bayWidths"]
    assert widths[2] > widths[0], "the centre bay must be the widest: %s" % widths
    assert near(widths[0], 3.25) and near(widths[2], 4.0), widths
    positions = laid["positions"]
    assert near(positions[0], -positions[-1]), "the front must be symmetric about the axis"
    assert near(sum(widths), laid["span"]), "bay widths must sum to the span"
    return "6 columns, 5 bays, centre bay %g vs %g at the sides" % (widths[2], widths[0])


def t_module_for_span():
    c = canon()
    module = c.moduleForSpan(20.0, 6)
    bands = c.colonnadeBands(6, module=module)
    assert near(sum(width for _, width in bands), 20.0, 1e-9), sum(w for _, w in bands)
    centres = c.moduleForSpan(20.0, 6, outerColumns=False)
    assert near(c.colonnade(6, module=centres)["span"], 20.0, 1e-9)
    return "M=%.4f fits a 20 m built front; the centre-to-centre variant differs" % module


def t_triglyph_count():
    c = canon()
    laid = c.colonnade(6, module=1.0, spacing="systyle")
    centres = c.triglyphs(laid)
    assert len(centres) == 2 * laid["bays"] + 1, "expected %d triglyphs, got %d" % (
        2 * laid["bays"] + 1, len(centres))
    return "%d triglyphs across %d bays (2 x bays + 1)" % (len(centres), laid["bays"])


def t_colonnade_needs_columns():
    try:
        canon().colonnade(1)
    except ValueError:
        return "a colonnade of one column is refused"
    raise AssertionError("a single column was accepted as a colonnade")


# ------------------------------------------------------------------- rooms

def t_room_from_shape():
    derived = canon().room("squareAndAHalf", width=6.0, ceiling="geometricMean")
    assert near(derived["length"], 9.0), derived["length"]
    assert near(derived["height"], math.sqrt(9.0 * 6.0)), derived["height"]
    assert derived["consonance"] == "perfect fifth", derived["consonance"]
    return "6 m wide square-and-a-half: %.1f long, %.3f high (geometric mean, a perfect fifth)" % (
        derived["length"], derived["height"])


def t_three_means_differ():
    c = canon()
    heights = {rule: c.room("doubleSquare", width=5.0, ceiling=rule)["height"]
               for rule in ("arithmeticMean", "geometricMean", "harmonicMean")}
    assert heights["arithmeticMean"] > heights["geometricMean"] > heights["harmonicMean"], heights
    return "arithmetic %.2f > geometric %.2f > harmonic %.2f" % (
        heights["arithmeticMean"], heights["geometricMean"], heights["harmonicMean"])


# ---------------------------------------------------------------- pediment

def t_pediment_rules():
    c = canon()
    vitruvian = c.pediment(20.0, "vitruvian")
    palladian = c.pediment(20.0, "palladian")
    assert near(vitruvian["height"], 20.0 / 9, 1e-9), vitruvian
    assert 12.0 < vitruvian["pitchDegrees"] < 13.0, vitruvian["pitchDegrees"]
    assert 21.8 <= palladian["pitchDegrees"] <= 26.6, palladian["pitchDegrees"]
    return "Vitruvian %.1f deg, Palladian %.1f deg over the same span" % (
        vitruvian["pitchDegrees"], palladian["pitchDegrees"])


# ------------------------------------------------------------------- audit

def t_audit_passes_a_canonical_front():
    c = canon()
    front = c.templeFront(columns=6, module=0.9, purpose="libraries", podium=1.5)
    text, ok = Audit.report(Audit().templeFront(front))
    assert ok, "a resolved front should satisfy the canon:\n%s" % text
    return "an Ionic hexastyle eustyle front passes every constraint"


def t_audit_catches_doric_widened_bay():
    c = canon()
    front = c.templeFront(columns=6, module=0.9, order="doric", spacing="eustyle")
    findings = Audit().templeFront(front)
    failures = [f for f in findings if not f.passed]
    assert failures, "Doric with a widened centre bay cannot keep its metopes square"
    assert any("square" in f.message for f in failures), [f.message for f in failures]
    uniform = c.templeFront(columns=6, module=0.9, order="doric", spacing="systyle")
    _, ok = Audit.report(Audit().templeFront(uniform))
    assert ok, "the same order at a uniform spacing should pass"
    return "the triglyph rule fails at eustyle and holds at systyle"


def t_audit_catches_odd_front():
    c = canon()
    front = c.templeFront(columns=5, module=1.0, order="ionic", spacing="systyle")
    failures = [f for f in Audit().templeFront(front) if not f.passed]
    assert any("even-numbered" in f.message for f in failures), [f.message for f in failures]
    return "an odd-numbered front is reported: a column would block the axis"


def t_audit_room():
    audit = Audit()
    good = [f for f in audit.room(width=6.0, length=9.0) if not f.passed]
    assert not good, [f.message for f in good]
    bad = [f for f in audit.room(width=6.0, length=10.3) if not f.passed]
    assert bad, "10.3 : 6 is not one of the seven shapes and should be reported"
    return "2:3 is recognised as square-and-a-half; 1.717:1 is reported as undesigned"


# --------------------------------------------------------------- interchange

def t_jsonld_roundtrip():
    original = loadCorpus()
    document = original.toJSONLD()
    restored = Graph().parse(json.loads(json.dumps(document)))
    assert len(restored) == len(original), "%d triples became %d" % (len(original), len(restored))
    missing = [t for t in original.triples() if t not in restored]
    assert not missing, "lost in the roundtrip: %s" % missing[:3]
    return "%d triples survive a JSON-LD roundtrip unchanged" % len(original)


def t_turtle_output():
    turtle = loadCorpus().toTurtle()
    assert "@prefix bcga:" in turtle, "no prefixes emitted"
    assert "<https://notationsystems.github.io/ns/bcga#ionic>" in turtle, "ionic missing"
    return "%d lines of Turtle" % len(turtle.splitlines())


def t_value_refuses_ambiguity():
    graph = Graph()
    graph.add(BCGA.thing, BCGA.height, 1)
    graph.add(BCGA.thing, BCGA.height, 2)
    try:
        graph.value(BCGA.thing, BCGA.height)
    except ValueError:
        return "value() refuses to pick between conflicting statements"
    raise AssertionError("value() silently chose between two conflicting values")


def t_rdflib_bridge():
    try:
        import rdflib  # noqa: F401
    except ImportError:
        return "SKIPPED: rdflib not installed (the corpus works without it)"
    graph = loadCorpus().toRDFLib()
    rows = list(graph.query("""
        PREFIX bcga: <https://notationsystems.github.io/ns/bcga#>
        SELECT ?label WHERE { ?o a bcga:Order ; bcga:columnHeight 9 ;
                              <http://www.w3.org/2000/01/rdf-schema#label> ?label }"""))
    assert [str(row[0]) for row in rows] == ["Ionic"], rows
    return "SPARQL over the bridged graph finds the 9 M order is Ionic"


def t_unknown_term_lists_alternatives():
    try:
        canon().order("dorik")
    except KeyError as error:
        assert "Doric" in str(error), error
        return "a misspelled order is refused, and the real ones are listed"
    raise AssertionError("a misspelled order was accepted")


def main():
    for name, function in [
        ("the corpus loads", t_corpus_loads),
        ("five orders with canonical heights", t_five_orders),
        ("five named intercolumniations", t_five_intercolumniations),
        ("Palladio's seven room shapes", t_seven_room_shapes),
        ("every fact cites a source", t_every_fact_is_sourced),
        ("an order derives from one module", t_order_arithmetic),
        ("spacing corrects slenderness", t_spacing_corrects_slenderness),
        ("decor chooses the order", t_decor_chooses_the_order),
        ("colonnade layout and centre bay", t_colonnade_layout),
        ("the module solved from a span", t_module_for_span),
        ("triglyph count is 2 x bays + 1", t_triglyph_count),
        ("a colonnade needs columns", t_colonnade_needs_columns),
        ("a room from one of the seven shapes", t_room_from_shape),
        ("the three means are ordered", t_three_means_differ),
        ("both pediment rules", t_pediment_rules),
        ("audit passes a canonical front", t_audit_passes_a_canonical_front),
        ("audit catches Doric with a wide bay", t_audit_catches_doric_widened_bay),
        ("audit catches an odd front", t_audit_catches_odd_front),
        ("audit of a room plan", t_audit_room),
        ("JSON-LD roundtrip", t_jsonld_roundtrip),
        ("Turtle output", t_turtle_output),
        ("value() refuses ambiguity", t_value_refuses_ambiguity),
        ("rdflib bridge and SPARQL", t_rdflib_bridge),
        ("unknown terms list alternatives", t_unknown_term_lists_alternatives),
    ]:
        check(name, function)

    print("\n" + "=" * 78)
    passed = sum(1 for r in RESULTS if r[0] == "PASS")
    for status, name, detail in RESULTS:
        print("%-4s %-40s %s" % (status, name, detail))
    print("=" * 78)
    print("%d/%d passed" % (passed, len(RESULTS)))
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
