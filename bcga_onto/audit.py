"""
Checking a design against the canon.

Generation and audit are different jobs: a resolver produces something
canonical by construction, but a design that came from anywhere else -- a
hand-built model, an imported plan, a rule set someone tuned by eye -- still
has to be answerable to the constraints. Both read the same graph, so the
audit cannot drift from what the generator believes.
"""

from .resolve import Canon
from .vocab import BCGA


class Finding:
    """One checked constraint"""

    def __init__(self, principle, passed, message, sources=()):
        self.principle = principle
        self.passed = passed
        self.message = message
        self.sources = list(sources)

    def __repr__(self):
        return "%s %s: %s" % ("PASS" if self.passed else "FAIL", self.principle, self.message)


class Audit:
    def __init__(self, canon=None):
        self.canon = canon if canon is not None else Canon()

    def templeFront(self, front):
        """Audits a specification produced by Canon.templeFront (or like it)"""
        findings = []
        order, colonnade = front["order"], front["colonnade"]
        graph = self.canon.graph

        # ordinatio: every dimension stated in modules
        findings.append(Finding(
            "ordinatio", bool(front.get("module")),
            "the module M is %s" % front.get("module") if front.get("module")
            else "no module is stated, so nothing is yet designed",
            self.canon.sources(BCGA.ordinatio)))

        # symmetria: entablature between a quarter and a fifth of the column
        ratio = order["entablature"] / order["columnHeight"]
        findings.append(Finding(
            "symmetria", 0.2 - 1e-9 <= ratio <= 0.25 + 1e-9,
            "the entablature is %.3f of the column height (the canon allows 1/5 to 1/4)" % ratio,
            self.canon.sources(order["iri"])))

        # decor: even-numbered front, so no column blocks the axis
        findings.append(Finding(
            "decor", colonnade["columns"] % 2 == 0,
            "the front has %d columns; fronts are even-numbered so no column blocks the axis"
            % colonnade["columns"],
            self.canon.sources(BCGA.evenFrontRule)))

        # the spacing must be one of the five named intercolumniations
        named = {self.canon.label(s) for s in graph.typed(BCGA.Intercolumniation)}
        findings.append(Finding(
            "symmetria", colonnade["spacing"] in named,
            "the spacing %r is one of the named intercolumniations" % colonnade["spacing"]
            if colonnade["spacing"] in named else
            "the spacing %r is not one of %s" % (colonnade["spacing"], sorted(named)),
            self.canon.sources(colonnade["iri"])))

        # the Doric triglyph rule, which a widened centre bay breaks
        if order["hasTriglyphFrieze"]:
            widths = set(round(width, 9) for width in colonnade["bayWidths"])
            findings.append(Finding(
                "symmetria", len(widths) == 1,
                "every bay is the same width, so the metopes can come out square"
                if len(widths) == 1 else
                "the bays are not all the same width (%s), so the metopes cannot all be "
                "square. Doric and a widened centre bay cannot both be satisfied: fix the "
                "bay, not the frieze" % ", ".join("%g" % width for width in sorted(widths)),
                self.canon.sources(order["iri"])))

        # eurythmia: the pediment must follow one of the rules the corpus names,
        # rather than a pitch window invented here. A Greek temple front is
        # legitimately shallow, so a fixed range would condemn Vitruvius.
        pitch = front["pediment"]["pitchDegrees"]
        vitruvian = graph.value(BCGA.pedimentPitch, BCGA.vitruvianPitchDegrees)
        low = graph.value(BCGA.pedimentPitch, BCGA.palladianPitchDegreesMin)
        high = graph.value(BCGA.pedimentPitch, BCGA.palladianPitchDegreesMax)
        named = (abs(pitch - vitruvian) < 0.5) or (low - 0.5 <= pitch <= high + 0.5)
        findings.append(Finding(
            "eurythmia", named,
            "the pediment pitch is %.1f degrees, which follows the canon "
            "(Vitruvian %.1f, or Palladian %.1f to %.1f)" % (pitch, vitruvian, low, high)
            if named else
            "the pediment pitch is %.1f degrees, which is neither the Vitruvian %.1f nor "
            "the Palladian %.1f to %.1f; steeper reads Gothic, shallower reads weak"
            % (pitch, vitruvian, low, high),
            self.canon.sources(BCGA.pedimentPitch)))

        return findings

    def room(self, width, length, height=None, tolerance=0.02):
        """Audits a room against the seven shapes and the three means"""
        findings = []
        proportion = max(width, length) / min(width, length)
        matches = []
        for subject in self.canon.roomShapes():
            ratio = (self.canon.graph.value(subject, BCGA.ratioLength)
                     / self.canon.graph.value(subject, BCGA.ratioWidth))
            if abs(ratio - proportion) <= tolerance:
                matches.append(self.canon.label(subject))
        findings.append(Finding(
            "symmetria", bool(matches),
            "the plan is %s (%.3f)" % (" or ".join(matches), proportion) if matches else
            "the plan ratio %.3f is not one of the seven shapes, so the room is undesigned"
            % proportion,
            self.canon.sources(BCGA.squareAndAHalf)))

        if height is not None:
            named = []
            for rule in self.canon.graph.typed(BCGA.CeilingRule):
                derived = self.canon._ceiling(rule, max(width, length), min(width, length))
                if abs(derived - height) <= tolerance * max(1.0, height):
                    named.append(self.canon.label(rule))
            findings.append(Finding(
                "symmetria", bool(named),
                "the ceiling height follows the %s" % " or ".join(named) if named else
                "the ceiling height %g comes from none of the three means" % height,
                self.canon.sources(BCGA.geometricMean)))
        return findings

    @staticmethod
    def report(findings):
        """A readable summary; returns (text, passed)"""
        lines = [repr(finding) for finding in findings]
        failed = [finding for finding in findings if not finding.passed]
        lines.append("%d of %d constraints hold" % (len(findings) - len(failed), len(findings)))
        return "\n".join(lines), not failed
