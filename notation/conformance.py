"""
Checking a corpus against the Notation Systems clauses.

Notation Systems apparatuses are provenance-bearing computational corpora.
That phrase is only worth anything if it is checkable, so the clauses below
are executable rather than aspirational, and each apparatus declares a
Manifest binding them to its own vocabulary.

Nothing here imports any particular corpus, or anything outside the standard
library. A corpus qualifies by exposing four methods -- triples, subjects,
objects and value -- which is little enough that an apparatus built on rdflib,
on plain dicts, or on a database view can all be checked by the same code.

    python3 -m notation.conformance bcga_onto

A clause returns one of three verdicts, never a bare pass or fail:

    HOLDS           the clause is satisfied
    FAILS           the clause is violated, and the report names the subjects
    NOT APPLICABLE  the corpus asserts nothing the clause governs

The third is the point. A corpus with no measurements has not passed the
measurement clause, and saying so is the difference between an instrument and
a rubber stamp.
"""

import importlib
import sys

HOLDS = "HOLDS"
FAILS = "FAILS"
NOT_APPLICABLE = "NOT APPLICABLE"


class Manifest:
    """
    How one apparatus binds the clauses to its own vocabulary.

    Everything is optional. A clause whose bindings are absent reports NOT
    APPLICABLE rather than passing quietly, so an apparatus cannot earn
    conformance by declining to describe itself.
    """

    def __init__(self, name, graph, sourceProperty=None, instanceKinds=(),
                 doctrineKinds=(), evidenceKinds=(), measurementKinds=(),
                 measurementWarrants=(), knownAtProperty=None,
                 attestationProperty=None, singleValued=(), emptyGraph=None):
        self.name = name
        self.graph = graph
        self.sourceProperty = sourceProperty
        self.instanceKinds = tuple(instanceKinds)
        self.doctrineKinds = tuple(doctrineKinds)
        self.evidenceKinds = tuple(evidenceKinds)
        self.measurementKinds = tuple(measurementKinds)
        # the properties a measurement must carry to be interrogable at all
        self.measurementWarrants = tuple(measurementWarrants)
        self.knownAtProperty = knownAtProperty
        self.attestationProperty = attestationProperty
        self.singleValued = tuple(singleValued)
        # a zero-argument callable returning a fresh empty graph of the same
        # class, used to probe behaviour without touching the real corpus
        self.emptyGraph = emptyGraph

    def instances(self, kinds):
        found = []
        for kind in kinds:
            found.extend(self.graph.typed(kind))
        return sorted(set(found))


class Verdict:
    def __init__(self, clause, title, verdict, detail, subjects=()):
        self.clause = clause
        self.title = title
        self.verdict = verdict
        self.detail = detail
        self.subjects = list(subjects)

    @property
    def ok(self):
        """A failing clause is the only disqualifying outcome"""
        return self.verdict != FAILS

    def __repr__(self):
        return "%s %-14s %s -- %s" % (self.clause, self.verdict, self.title, self.detail)


def _shrink(graph, term):
    return graph.shrink(term) if hasattr(graph, "shrink") else str(term)


# --------------------------------------------------------------- the clauses

def attribution(manifest):
    """C1 -- every assertion names where it came from"""
    if not manifest.sourceProperty or not manifest.instanceKinds:
        return Verdict("C1", "Attribution", NOT_APPLICABLE,
                       "the manifest declares no source property or instance kinds")
    subjects = manifest.instances(manifest.instanceKinds)
    if not subjects:
        return Verdict("C1", "Attribution", NOT_APPLICABLE,
                       "the corpus holds no instances of the declared kinds")
    unsourced = [s for s in subjects if not manifest.graph.objects(s, manifest.sourceProperty)]
    if unsourced:
        return Verdict("C1", "Attribution", FAILS,
                       "%d of %d instances cite no source" % (len(unsourced), len(subjects)),
                       [_shrink(manifest.graph, s) for s in unsourced])
    return Verdict("C1", "Attribution", HOLDS,
                   "all %d instances carry a source" % len(subjects))


def separation(manifest):
    """C2 -- doctrine and evidence are different kinds of statement"""
    if not manifest.doctrineKinds or not manifest.evidenceKinds:
        missing = "evidence" if manifest.doctrineKinds else "doctrine"
        return Verdict("C2", "Separation", NOT_APPLICABLE,
                       "the corpus declares no %s kinds, so nothing can be conflated" % missing)
    doctrine = set(manifest.instances(manifest.doctrineKinds))
    evidence = set(manifest.instances(manifest.evidenceKinds))
    both = sorted(doctrine & evidence)
    if both:
        return Verdict("C2", "Separation", FAILS,
                       "%d subjects are typed as both doctrine and evidence" % len(both),
                       [_shrink(manifest.graph, s) for s in both])
    return Verdict("C2", "Separation", HOLDS,
                   "%d doctrine and %d evidence subjects, disjoint" % (len(doctrine), len(evidence)))


def warrant(manifest):
    """C3 -- a measurement carries what is needed to weigh it"""
    if not manifest.measurementKinds:
        return Verdict("C3", "Warrant", NOT_APPLICABLE,
                       "the corpus asserts no measurements; its statements are prescriptive")
    subjects = manifest.instances(manifest.measurementKinds)
    if not subjects:
        return Verdict("C3", "Warrant", NOT_APPLICABLE,
                       "measurement kinds are declared but the corpus holds none")
    if not manifest.measurementWarrants:
        return Verdict("C3", "Warrant", FAILS,
                       "measurements exist but the manifest names no warrant properties")
    bare = []
    for subject in subjects:
        absent = [p for p in manifest.measurementWarrants
                  if not manifest.graph.objects(subject, p)]
        if absent:
            bare.append("%s (missing %s)" % (
                _shrink(manifest.graph, subject),
                ", ".join(_shrink(manifest.graph, p) for p in absent)))
    if bare:
        return Verdict("C3", "Warrant", FAILS,
                       "%d of %d measurements are unweighable" % (len(bare), len(subjects)), bare)
    return Verdict("C3", "Warrant", HOLDS,
                   "all %d measurements carry %d warrants" % (len(subjects), len(manifest.measurementWarrants)))


def refusal(manifest):
    """C4 -- the corpus refuses to choose between conflicting statements"""
    if manifest.emptyGraph is None or not manifest.singleValued:
        return Verdict("C4", "Refusal", NOT_APPLICABLE,
                       "the manifest supplies no scratch graph or single-valued properties")
    scratch = manifest.emptyGraph()
    subject = manifest.instances(manifest.instanceKinds)
    probe = subject[0] if subject else "urn:notation:probe"
    predicate = manifest.singleValued[0]
    scratch.add(probe, predicate, 1)
    scratch.add(probe, predicate, 2)
    try:
        chosen = scratch.value(probe, predicate)
    except Exception:
        return Verdict("C4", "Refusal", HOLDS,
                       "a single-valued read over two conflicting statements raises")
    return Verdict("C4", "Refusal", FAILS,
                   "a single-valued read silently returned %r out of two conflicting "
                   "statements; a chosen value must be a recorded act" % (chosen,))


def attestation(manifest):
    """C5 -- a value says whether it is a claim about the world"""
    if not manifest.attestationProperty or not manifest.instanceKinds:
        return Verdict("C5", "Attestation", NOT_APPLICABLE,
                       "the corpus declares no attestation property; nothing in it is "
                       "presented as an observation of the world")
    subjects = manifest.instances(manifest.instanceKinds)
    unattested = [s for s in subjects
                  if not manifest.graph.objects(s, manifest.attestationProperty)]
    if unattested:
        return Verdict("C5", "Attestation", FAILS,
                       "%d of %d instances do not say what they are" % (len(unattested), len(subjects)),
                       [_shrink(manifest.graph, s) for s in unattested])
    return Verdict("C5", "Attestation", HOLDS,
                   "all %d instances declare their attestation" % len(subjects))


def temporality(manifest):
    """C6 -- evidence records when it became knowable"""
    if not manifest.knownAtProperty or not manifest.evidenceKinds:
        return Verdict("C6", "Temporality", NOT_APPLICABLE,
                       "the corpus holds no evidence, so nothing became knowable at a time")
    subjects = manifest.instances(manifest.evidenceKinds)
    if not subjects:
        return Verdict("C6", "Temporality", NOT_APPLICABLE,
                       "evidence kinds are declared but the corpus holds none")
    undated = [s for s in subjects if not manifest.graph.objects(s, manifest.knownAtProperty)]
    if undated:
        return Verdict("C6", "Temporality", FAILS,
                       "%d of %d evidence subjects have no knownAt" % (len(undated), len(subjects)),
                       [_shrink(manifest.graph, s) for s in undated])
    return Verdict("C6", "Temporality", HOLDS,
                   "all %d evidence subjects record when they became knowable" % len(subjects))


CLAUSES = (attribution, separation, warrant, refusal, attestation, temporality)


def check(manifest):
    """Runs every clause, returning the verdicts in clause order"""
    return [clause(manifest) for clause in CLAUSES]


def report(manifest, verdicts=None):
    """A readable conformance report; returns (text, conformant)"""
    verdicts = verdicts if verdicts is not None else check(manifest)
    lines = ["NOTATION SYSTEMS CONFORMANCE -- %s" % manifest.name, "=" * 72]
    for verdict in verdicts:
        lines.append("%-3s %-14s %-13s %s" % (
            verdict.clause, verdict.verdict, verdict.title, verdict.detail))
        for subject in verdict.subjects[:6]:
            lines.append("        %s" % subject)
        if len(verdict.subjects) > 6:
            lines.append("        ... and %d more" % (len(verdict.subjects) - 6))
    failed = [v for v in verdicts if v.verdict == FAILS]
    held = [v for v in verdicts if v.verdict == HOLDS]
    skipped = [v for v in verdicts if v.verdict == NOT_APPLICABLE]
    lines.append("=" * 72)
    lines.append("%d hold, %d fail, %d not applicable" % (len(held), len(failed), len(skipped)))
    return "\n".join(lines), not failed


def main(argv):
    if len(argv) != 2:
        print("usage: python3 -m notation.conformance <module exporting MANIFEST>")
        return 2
    module = importlib.import_module(argv[1])
    manifest = getattr(module, "MANIFEST", None)
    if manifest is None:
        print("%s exports no MANIFEST" % argv[1])
        return 2
    text, conformant = report(manifest() if callable(manifest) else manifest)
    print(text)
    return 0 if conformant else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
