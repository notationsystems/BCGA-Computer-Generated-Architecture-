"""
The BCGA knowledge layer: an architectural corpus that drives the grammar.

BCGA already separates the abstract shape grammar (pro) from its Blender
backend (bpro). This package sits on the other side of the grammar: a graph of
architectural knowledge, with its sources, that resolves into the parameters a
rule set builds from. Proportions live in the corpus, not in the rules.

It depends on nothing but the standard library, because a Blender add-on
cannot install packages. rdflib is used only if it happens to be present.

    from bcga_onto import canon

    front = canon().templeFront(columns=6, module=0.9, purpose="libraries")
    front["order"]["order"]          # 'Ionic', chosen by decor
    front["colonnade"]["positions"]  # column centres about the axis

    from bcga_onto import Audit
    text, ok = Audit.report(Audit().templeFront(front))
"""

from .audit import Audit, Finding
from .graph import Graph, loadCorpus
from .resolve import Canon, canon
from .vocab import BCGA, IRI, Namespace

__all__ = [
    "Audit", "Finding",
    "Graph", "loadCorpus",
    "Canon", "canon",
    "BCGA", "IRI", "Namespace",
]
