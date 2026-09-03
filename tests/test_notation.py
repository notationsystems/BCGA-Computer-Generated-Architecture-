"""
Tests for the Notation Systems conformance clauses.

A checker that cannot fail is decoration, so every clause is exercised in all
three of its outcomes against synthetic corpora, and only then against the
real one. Needs no Blender and nothing outside the standard library.

    python3 tests/test_notation.py
"""

import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from notation import FAILS, HOLDS, NOT_APPLICABLE, Manifest, check, report
from notation.conformance import (
    attestation, attribution, refusal, separation, temporality, warrant,
)

RESULTS = []
NS = "urn:test:"


def check_(name, function):
    try:
        RESULTS.append(("PASS", name, function() or ""))
    except Exception as error:
        RESULTS.append(("FAIL", name, "%s: %s" % (type(error).__name__, error)))
        traceback.print_exc()


class TinyGraph:
    """The smallest thing that satisfies the corpus interface"""

    def __init__(self):
        self.rows = []

    def add(self, s, p, o):
        self.rows.append((s, p, o))

    def triples(self, s=None, p=None, o=None):
        for row in self.rows:
            if (s is None or row[0] == s) and (p is None or row[1] == p) \
                    and (o is None or row[2] == o):
                yield row

    def objects(self, s, p):
        return [row[2] for row in self.triples(s, p)]

    def subjects(self, p=None, o=None):
        return sorted({row[0] for row in self.triples(None, p, o)})

    def typed(self, kind):
        return self.subjects(NS + "type", kind)

    def value(self, s, p):
        found = self.objects(s, p)
        if len(found) > 1:
            raise ValueError("%s %s has %d values" % (s, p, len(found)))
        return found[0] if found else None


class LaxGraph(TinyGraph):
    """A corpus that quietly picks a winner -- exactly what C4 must catch"""

    def value(self, s, p):
        found = self.objects(s, p)
        return found[0] if found else None


def corpus(graphClass=TinyGraph, sourced=True, kind="Order"):
    graph = graphClass()
    graph.add(NS + "thing", NS + "type", NS + kind)
    graph.add(NS + "thing", NS + "height", 9)
    if sourced:
        graph.add(NS + "thing", NS + "source", NS + "book")
    return graph


def manifest(graph, **kwargs):
    options = dict(
        name="test", graph=graph, sourceProperty=NS + "source",
        instanceKinds=(NS + "Order",), singleValued=(NS + "height",),
        emptyGraph=type(graph),
    )
    options.update(kwargs)
    return Manifest(**options)


# ------------------------------------------------------------------- clauses

def t_attribution_holds():
    v = attribution(manifest(corpus()))
    assert v.verdict == HOLDS, v
    return v.detail


def t_attribution_fails():
    v = attribution(manifest(corpus(sourced=False)))
    assert v.verdict == FAILS, v
    assert v.subjects, "a failure must name the offending subjects"
    return "%s -> %s" % (v.detail, v.subjects)


def t_attribution_not_applicable():
    v = attribution(manifest(corpus(), instanceKinds=()))
    assert v.verdict == NOT_APPLICABLE, v
    return v.detail


def t_separation_fails_on_overlap():
    graph = corpus()
    graph.add(NS + "thing", NS + "type", NS + "Observation")
    v = separation(manifest(graph, doctrineKinds=(NS + "Order",),
                            evidenceKinds=(NS + "Observation",)))
    assert v.verdict == FAILS, v
    return v.detail


def t_separation_holds_when_disjoint():
    graph = corpus()
    graph.add(NS + "other", NS + "type", NS + "Observation")
    v = separation(manifest(graph, doctrineKinds=(NS + "Order",),
                            evidenceKinds=(NS + "Observation",)))
    assert v.verdict == HOLDS, v
    return v.detail


def t_warrant_not_applicable_for_doctrine():
    v = warrant(manifest(corpus()))
    assert v.verdict == NOT_APPLICABLE, v
    assert "prescriptive" in v.detail
    return v.detail


def t_warrant_fails_without_tolerance():
    graph = corpus()
    graph.add(NS + "m", NS + "type", NS + "Measurement")
    graph.add(NS + "m", NS + "unit", "metre")
    v = warrant(manifest(graph, measurementKinds=(NS + "Measurement",),
                         measurementWarrants=(NS + "unit", NS + "tolerance", NS + "method")))
    assert v.verdict == FAILS, v
    assert "tolerance" in str(v.subjects), v.subjects
    return v.detail


def t_warrant_holds_when_complete():
    graph = corpus()
    graph.add(NS + "m", NS + "type", NS + "Measurement")
    for warrantName, value in (("unit", "metre"), ("tolerance", 0.05), ("method", "survey")):
        graph.add(NS + "m", NS + warrantName, value)
    v = warrant(manifest(graph, measurementKinds=(NS + "Measurement",),
                         measurementWarrants=(NS + "unit", NS + "tolerance", NS + "method")))
    assert v.verdict == HOLDS, v
    return v.detail


def t_refusal_holds():
    v = refusal(manifest(corpus()))
    assert v.verdict == HOLDS, v
    return v.detail


def t_refusal_catches_a_silent_chooser():
    v = refusal(manifest(corpus(LaxGraph)))
    assert v.verdict == FAILS, "a graph that silently picks a winner must not pass C4"
    return v.detail


def t_attestation_and_temporality():
    graph = corpus()
    graph.add(NS + "obs", NS + "type", NS + "Observation")
    undated = temporality(manifest(graph, evidenceKinds=(NS + "Observation",),
                                   knownAtProperty=NS + "knownAt"))
    assert undated.verdict == FAILS, undated
    graph.add(NS + "obs", NS + "knownAt", "2026-01-01")
    dated = temporality(manifest(graph, evidenceKinds=(NS + "Observation",),
                                 knownAtProperty=NS + "knownAt"))
    assert dated.verdict == HOLDS, dated
    absent = attestation(manifest(graph))
    assert absent.verdict == NOT_APPLICABLE, absent
    return "undated evidence fails, dated evidence holds, attestation abstains"


# ------------------------------------------------------------- the real one

def t_bcga_conforms():
    import bcga_onto

    verdicts = check(bcga_onto.MANIFEST())
    text, conformant = report(bcga_onto.MANIFEST(), verdicts)
    assert conformant, "BCGA should have no failing clause:\n%s" % text
    byClause = {v.clause: v.verdict for v in verdicts}
    assert byClause["C1"] == HOLDS, byClause
    assert byClause["C4"] == HOLDS, byClause
    # the corpus is doctrine only, and must say so rather than pass quietly
    for clause in ("C2", "C3", "C5", "C6"):
        assert byClause[clause] == NOT_APPLICABLE, (clause, byClause)
    return "C1 and C4 hold; C2, C3, C5, C6 abstain -- a doctrinal corpus, stated as such"


def t_report_is_legible():
    import bcga_onto

    text, _ = report(bcga_onto.MANIFEST())
    assert "NOTATION SYSTEMS CONFORMANCE" in text
    assert "not applicable" in text
    return "%d lines" % len(text.splitlines())


def main():
    for name, function in [
        ("C1 holds when everything is sourced", t_attribution_holds),
        ("C1 fails and names the subjects", t_attribution_fails),
        ("C1 abstains with nothing to check", t_attribution_not_applicable),
        ("C2 fails when kinds overlap", t_separation_fails_on_overlap),
        ("C2 holds when kinds are disjoint", t_separation_holds_when_disjoint),
        ("C3 abstains over pure doctrine", t_warrant_not_applicable_for_doctrine),
        ("C3 fails on an unweighable measurement", t_warrant_fails_without_tolerance),
        ("C3 holds on a complete measurement", t_warrant_holds_when_complete),
        ("C4 holds when the reader refuses", t_refusal_holds),
        ("C4 catches a silent chooser", t_refusal_catches_a_silent_chooser),
        ("C5 and C6 over evidence", t_attestation_and_temporality),
        ("BCGA conforms, and abstains honestly", t_bcga_conforms),
        ("the report reads", t_report_is_legible),
    ]:
        check_(name, function)

    print("\n" + "=" * 78)
    passed = sum(1 for r in RESULTS if r[0] == "PASS")
    for status, name, detail in RESULTS:
        print("%-4s %-40s %s" % (status, name, detail))
    print("=" * 78)
    print("%d/%d passed" % (passed, len(RESULTS)))
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
