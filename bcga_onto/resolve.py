"""
Turning the knowledge graph into numbers a grammar can build with.

Nothing here hardcodes a proportion. Every value is read out of the corpus, so
correcting a source, or pointing the resolver at a different graph, changes
what gets built. That is the whole point of attaching an ontology to a shape
grammar rather than writing the ratios into the rules.
"""

import math

from .graph import Graph, loadCorpus
from .vocab import BCGA, LABEL, IRI


class Canon:
    """A resolver over one knowledge graph"""

    def __init__(self, graph=None):
        self.graph = graph if graph is not None else loadCorpus()

    # ------------------------------------------------------------- lookup

    def resolve(self, term, kind=None):
        """
        Resolves "ionic", "Ionic" or a full IRI to the IRI of a corpus node.

        kind, when given, is the class the node must belong to, which turns a
        typo into a helpful error listing the real alternatives.
        """
        candidate = IRI(term) if str(term).startswith("http") else BCGA[str(term)]
        if any(self.graph.triples(candidate)):
            if kind is None or IRI(candidate) in self.graph.typed(kind):
                return IRI(candidate)
        if kind is not None:
            for subject in self.graph.typed(kind):
                if str(self.graph.value(subject, LABEL, "")).lower() == str(term).lower():
                    return subject
            known = sorted(str(self.graph.value(s, LABEL, s)) for s in self.graph.typed(kind))
            raise KeyError("%r is not in the corpus; known: %s" % (term, ", ".join(known)))
        raise KeyError("%r is not in the corpus" % (term,))

    def label(self, subject):
        return self.graph.value(subject, LABEL, self.graph.shrink(subject))

    def sources(self, subject):
        """The citations behind a node, as readable strings"""
        from .vocab import SOURCE
        return sorted(
            str(self.graph.value(citation, LABEL, citation))
            for citation in self.graph.objects(subject, SOURCE))

    # -------------------------------------------------------------- orders

    def order(self, name, module=1.0, spacing=None):
        """
        Derives a whole order from one number.

        module is M, the diameter of the column at its base. When spacing is
        given, Vitruvius' slenderness correction applies: the wider the bay,
        the stouter the column must look, so the spacing table overrides the
        order table (III.3.7-10).
        """
        subject = self.resolve(name, BCGA.Order)
        height = self.graph.value(subject, BCGA.columnHeight)
        heightSource = "order"
        if spacing is not None:
            spacingIRI = self.resolve(spacing, BCGA.Intercolumniation)
            corrected = self.graph.value(spacingIRI, BCGA.correctedColumnHeight)
            if corrected is not None:
                height, heightSource = corrected, "spacing"
        entablature = height * self.graph.value(subject, BCGA.entablatureRatio)
        return {
            "order": self.label(subject),
            "iri": subject,
            "module": module,
            "columnHeightModules": height,
            "columnHeightFrom": heightSource,
            "columnHeight": height * module,
            "entablature": entablature * module,
            "architrave": entablature * module * self.graph.value(subject, BCGA.architraveShare),
            "frieze": entablature * module * self.graph.value(subject, BCGA.friezeShare),
            "cornice": entablature * module * self.graph.value(subject, BCGA.corniceShare),
            "neckDiameter": module * self.graph.value(subject, BCGA.shaftDiminution),
            "flutes": self.graph.value(subject, BCGA.flutes),
            "hasTriglyphFrieze": bool(self.graph.value(subject, BCGA.hasTriglyphFrieze, False)),
            "character": self.graph.value(subject, BCGA.character),
            "sources": self.sources(subject),
        }

    def ordersBySlenderness(self):
        return sorted(self.graph.typed(BCGA.Order),
                      key=lambda s: self.graph.value(s, BCGA.slendernessRank, 0))

    def orderFor(self, purpose):
        """
        Decor: chooses the order whose character suits the purpose.

        Vitruvius assigns orders by character, not by taste, so this is a
        graph lookup rather than a preference. The most solid order that
        admits the purpose wins, which keeps a workshop out of Corinthian.
        """
        for subject in self.ordersBySlenderness():
            if any(str(purpose).lower() == str(use).lower()
                   for use in self.graph.objects(subject, BCGA.suitedTo)):
                return self.label(subject)
        known = sorted({str(use) for s in self.graph.typed(BCGA.Order)
                        for use in self.graph.objects(s, BCGA.suitedTo)})
        raise KeyError("no order in the corpus is assigned to %r; known purposes: %s"
                       % (purpose, ", ".join(known)))

    # ---------------------------------------------------------- colonnade

    def colonnade(self, columns, module=1.0, spacing="eustyle"):
        """
        Lays out a front of evenly spaced columns about the axis.

        Fronts are even-numbered so no column blocks the axis, and eustyle
        widens the centre bay to mark the entrance without breaking rhythm.
        Returns centre-to-centre positions measured from the axis.
        """
        if columns < 2:
            raise ValueError("a colonnade needs at least 2 columns, got %r" % (columns,))
        subject = self.resolve(spacing, BCGA.Intercolumniation)
        side = (self.graph.value(subject, BCGA.clearSpace) + 1) * module
        centreClear = self.graph.value(subject, BCGA.centreClearSpace)
        centre = ((centreClear + 1) * module) if centreClear is not None else side
        bays = columns - 1
        middle = bays // 2 if bays % 2 else None
        widths = [centre if index == middle else side for index in range(bays)]
        span = sum(widths)
        positions, x = [-span / 2], -span / 2
        for width in widths:
            x += width
            positions.append(x)
        return {
            "spacing": self.label(subject),
            "iri": subject,
            "columns": columns,
            "bays": bays,
            "bayWidths": widths,
            "centreBay": middle,
            "span": span,
            "positions": positions,
            "sources": self.sources(subject),
        }

    def moduleForSpan(self, span, columns, spacing="eustyle", outerColumns=True):
        """
        Works the canon backwards: the module that makes a front fit a span.

        Ordinatio fixes the module first, but a plot fixes the width first.
        Solving for M reconciles the two, so a real footprint still yields
        canonical proportions rather than arbitrary ones.

        colonnade() reports the span between the OUTER COLUMN CENTRES, so a
        built front is half a column wider at each end. outerColumns=True, the
        default, treats span as that full built width, which is what a facade
        of a given size needs; pass False to match centre-to-centre instead.
        """
        unit = self.colonnade(columns, module=1.0, spacing=spacing)["span"]
        return span / (unit + 1.0) if outerColumns else span / unit

    def colonnadeBands(self, columns, module=1.0, spacing="eustyle"):
        """
        The column rhythm as consecutive bands across the front.

        Returns (kind, width) pairs alternating "column" and "void", which is
        the form a shape grammar splits on. Widths are in the same units as
        module; divide by the span for proportional splits.
        """
        laid = self.colonnade(columns, module=module, spacing=spacing)
        bands, previous = [], None
        for position in laid["positions"]:
            if previous is not None:
                bands.append(("void", (position - module / 2) - (previous + module / 2)))
            bands.append(("column", module))
            previous = position
        return bands

    def elevationBands(self, order, module=1.0, spacing="eustyle", podium=0.0):
        """
        The horizontal courses of an elevation, bottom to top.

        Returns (kind, height) pairs: the podium, the column zone, then the
        entablature split into architrave, frieze and cornice.
        """
        derived = self.order(order, module=module, spacing=spacing)
        bands = []
        if podium:
            bands.append(("podium", podium))
        bands.append(("column", derived["columnHeight"]))
        bands.append(("architrave", derived["architrave"]))
        bands.append(("frieze", derived["frieze"]))
        bands.append(("cornice", derived["cornice"]))
        return bands

    def triglyphs(self, colonnade):
        """
        Triglyph centres: one over every column and one over every bay.

        Count across a front is 2 x bays + 1. Where the centre bay is widened
        the metopes stop being square, which the audit reports rather than
        silently accepting.
        """
        positions = colonnade["positions"]
        centres = []
        for index, position in enumerate(positions):
            centres.append(position)
            if index + 1 < len(positions):
                centres.append((position + positions[index + 1]) / 2)
        return centres

    # -------------------------------------------------------------- rooms

    def room(self, shape, width, ceiling="geometricMean"):
        """Derives a room's length and height from one of the seven shapes"""
        subject = self.resolve(shape, BCGA.RoomShape)
        ratioWidth = self.graph.value(subject, BCGA.ratioWidth)
        ratioLength = self.graph.value(subject, BCGA.ratioLength)
        length = width * ratioLength / ratioWidth
        rule = self.resolve(ceiling, BCGA.CeilingRule)
        height = self._ceiling(rule, length, width)
        return {
            "shape": self.label(subject),
            "iri": subject,
            "width": width,
            "length": length,
            "ratio": "%g:%g" % (ratioWidth, ratioLength),
            "consonance": self.graph.value(subject, BCGA.consonance),
            "height": height,
            "ceilingRule": self.label(rule),
            "sources": sorted(set(self.sources(subject) + self.sources(rule))),
        }

    def _ceiling(self, rule, length, width):
        formula = self.graph.value(rule, BCGA.formula)
        means = {
            "(length + width) / 2": lambda: (length + width) / 2,
            "sqrt(length * width)": lambda: math.sqrt(length * width),
            "2 * length * width / (length + width)": lambda: 2 * length * width / (length + width),
            "width": lambda: width,
        }
        if formula not in means:
            raise KeyError("no implementation for the ceiling formula %r" % (formula,))
        return means[formula]()

    def roomShapes(self):
        return sorted(self.graph.typed(BCGA.RoomShape),
                      key=lambda s: self.graph.value(s, BCGA.ordinal, 0))

    # ----------------------------------------------------------- pediment

    def pediment(self, span, rule="palladian"):
        """
        Tympanum height over a given cornice span.

        Both named rules take their ratio against the full cornice span:
        Vitruvius 1/9, giving a shallow ~12.5 degrees; Palladio 1/4 to 1/5,
        giving ~22 to 27. See the corpus note on the source's wording.
        """
        subject = BCGA.pedimentPitch
        if rule == "vitruvian":
            height = span * self.graph.value(subject, BCGA.vitruvianTympanumRatio)
        elif rule == "palladian":
            low = self.graph.value(subject, BCGA.palladianSpanRatioMin)
            high = self.graph.value(subject, BCGA.palladianSpanRatioMax)
            height = span * (low + high) / 2
        else:
            raise KeyError("pediment rule must be 'vitruvian' or 'palladian', got %r" % (rule,))
        return {
            "span": span,
            "height": height,
            "pitchDegrees": math.degrees(math.atan(height / (span / 2))),
            "rule": rule,
            "sources": self.sources(subject),
        }

    # ------------------------------------------------------- whole fronts

    def templeFront(self, columns=6, module=1.0, order=None, spacing="eustyle",
                    purpose=None, podium=0.0):
        """
        A complete portico: the specification a rule set needs to build one.

        Give a purpose instead of an order and decor chooses the order.
        """
        if order is None:
            order = self.orderFor(purpose) if purpose else self.label(
                self.graph.value(BCGA.palladianVilla, BCGA.defaultOrder))
        theOrder = self.order(order, module=module, spacing=spacing)
        theColonnade = self.colonnade(columns, module=module, spacing=spacing)
        # the pediment sits on the cornice, so it spans the outer column centres
        thePediment = self.pediment(theColonnade["span"])
        return {
            "module": module,
            "podium": podium,
            "order": theOrder,
            "colonnade": theColonnade,
            "pediment": thePediment,
            "height": podium + theOrder["columnHeight"] + theOrder["entablature"] + thePediment["height"],
            "purpose": purpose,
        }


_canon = None


def canon():
    """The default resolver over the bundled corpus, loaded once"""
    global _canon
    if _canon is None:
        _canon = Canon()
    return _canon
