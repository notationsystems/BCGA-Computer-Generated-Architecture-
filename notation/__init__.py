"""
Notation Systems: the shared discipline its apparatuses are built to.

Notation Systems builds and operates provenance-bearing computational corpora.
This package is the part of that sentence which is executable -- the clauses an
apparatus is checked against, and the Manifest by which it declares how those
clauses bind to its own vocabulary.

It deliberately depends on nothing, imports no corpus, and knows about no
particular domain. An apparatus over architectural doctrine and an apparatus
over freight movements are checked by the same code.

See NOTATION.md for the clauses in prose and the reasoning behind each.
"""

from .conformance import (
    CLAUSES, FAILS, HOLDS, NOT_APPLICABLE, Manifest, Verdict, check, report,
)

__all__ = [
    "CLAUSES", "FAILS", "HOLDS", "NOT_APPLICABLE",
    "Manifest", "Verdict", "check", "report",
]
