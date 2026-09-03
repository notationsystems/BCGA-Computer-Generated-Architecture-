# Notation Systems — the discipline its apparatuses are built to

> Notation Systems builds and operates provenance-bearing computational corpora.

That sentence is only worth something if it is checkable. This document is the
checkable form of it: six clauses, an executable checker in `notation/`, and a
`Manifest` by which each apparatus declares how the clauses bind to its own
vocabulary.

`notation/` imports nothing outside the standard library and knows about no
particular domain. An apparatus over architectural doctrine and an apparatus
over freight movements are checked by the same code.

## What an apparatus is

An **apparatus** is a system that holds a corpus and answers questions from it.
It is not defined by its subject or its interface. It is defined by the fact
that every value it returns can be interrogated back to its warrant, and that
it declines rather than guesses when it cannot.

Three things follow, and they are what the clauses formalise.

1. **A number without a warrant is not an answer.** It is a rumour with
   arithmetic applied.
2. **Prescription and observation are different kinds of statement.** What a
   rule says and what a thing measures cannot share a type without destroying
   the only question worth asking, which is the distance between them.
3. **Absence has kinds.** "No result" and "not applicable" and "refused" are
   three different facts about the world, and collapsing them into an empty
   list loses the one the reader needed.

## The clauses

Each returns **HOLDS**, **FAILS**, or **NOT APPLICABLE** — never a bare pass.
An apparatus that asserts nothing a clause governs has not passed that clause,
and saying so is the difference between an instrument and a rubber stamp.

### C1 · Attribution — every assertion names where it came from

Each instance carries a source. Enforced, not encouraged: a corpus where 95% of
values are attributed is a corpus where you must check every value by hand,
which is the same as none.

### C2 · Separation — doctrine and evidence are distinct kinds

Prescriptive statements ("the rule is 9 diameters", "the promised transit is
four days") and empirical ones ("this measures 9.4", "it arrived in five") must
be different types with different query paths. Collapse them and the deviation
between them — the thing that compounds in value over time — becomes
uncomputable. Most systems lose this by overwriting the promise with the
outcome.

### C3 · Warrant — a measurement carries what is needed to weigh it

An observation needs more than a citation. It needs its **unit**, its
**tolerance**, its **method**, and whether it was **asserted or derived**.
A citation says which book; the method says whether the figure was surveyed or
scaled off a drawing, and those are not the same claim. Method strength and
freshness are orthogonal axes: a stale fact can outrank a fresh guess.

### C4 · Refusal — the corpus does not choose between conflicting statements

Where two sources disagree, both are kept and attributed. Never averaged: an
averaged measurement is a number nobody observed, attributable to nobody, and
it erases the disagreement that was the signal. A single-valued read over
conflicting statements must raise. Selecting a winner is permitted, but only as
an explicit act with a recorded reason.

This clause is checked behaviourally, against a scratch graph — a corpus that
silently returns the first of two conflicting values fails it.

### C5 · Attestation — a value says whether it is a claim about the world

Synthetic, representative and demonstration data carry their status in the same
field that real data will carry its source. A banner on a screen is
forgettable; a field is queryable, and stays true when mock and real data sit
side by side.

### C6 · Temporality — evidence records when it became knowable

`knownAt` is separate from the period a value describes. Without it you can
reconstruct what is true, but not what was known — and "what did we know when
we priced this" is unanswerable.

## Declaring an apparatus

```python
from notation import Manifest

def MANIFEST():
    return Manifest(
        name="...",
        graph=loadCorpus(),          # any object with triples/objects/subjects/value
        sourceProperty=DCTERMS.source,
        instanceKinds=(...),
        doctrineKinds=(...),
        evidenceKinds=(...),
        measurementKinds=(...),
        measurementWarrants=(...),
        knownAtProperty=...,
        attestationProperty=...,
        singleValued=(...),
        emptyGraph=Graph,
    )
```

Then:

```
python3 -m notation bcga_onto
```

Every binding is optional, and an absent binding yields NOT APPLICABLE rather
than a pass — so an apparatus cannot earn conformance by declining to describe
itself.

## Where BCGA stands

BCGA is the first apparatus built to these clauses. Its corpus is **entirely
doctrinal**: it records what Vitruvius and Palladio state, with citations, and
asserts nothing about any particular building.

```
C1  HOLDS          Attribution   all 39 instances carry a source
C2  NOT APPLICABLE Separation    the corpus declares no evidence kinds
C3  NOT APPLICABLE Warrant       the corpus asserts no measurements
C4  HOLDS          Refusal       a single-valued read over conflicts raises
C5  NOT APPLICABLE Attestation   nothing here is presented as an observation
C6  NOT APPLICABLE Temporality   the corpus holds no evidence
```

Two hold, four abstain. That is the honest reading, and the four abstentions
are precisely the gap a precedent corpus of measured buildings would close —
which is a schema problem before it is a data problem, and blocked on a
precedent source and its licence rather than on engineering.

## Status of this document

These clauses are the discipline **this repository** is built to, written down
so another apparatus can adopt them deliberately rather than by imitation. They
are not a ratified company standard, and nothing here has been reviewed outside
this repository. Treat the numbering as stable and the wording as revisable.
