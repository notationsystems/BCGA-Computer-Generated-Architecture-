"""
A small triple store with JSON-LD input and output.

Blender add-ons cannot install packages, so the knowledge layer has to work
with nothing but the standard library. This module is that floor: enough RDF
to hold the corpus, query it and hand it to real tooling.

It is deliberately NOT a full JSON-LD 1.1 processor. The supported subset is:

  * a top level object with "@context" and "@graph"
  * "@context" mapping prefixes to namespace strings
  * "@graph" holding node objects
  * a node with "@id", optional "@type" (one IRI or a list)
  * property values that are scalars (literals), {"@id": ...} (references),
    or lists of either

That covers everything in bcga_onto/corpus and stays honest about its limits.
Anything richer should go through rdflib, which toRDFLib() hands off to.
"""

import json
import os

from .vocab import IRI, NAMESPACES, TYPE


class Graph:
    """An unordered set of (subject, predicate, object) triples"""

    def __init__(self):
        self._triples = set()
        self.context = {prefix: ns.base for prefix, ns in NAMESPACES.items()}

    # ------------------------------------------------------------- building

    def add(self, subject, predicate, obj):
        self._triples.add((IRI(subject), IRI(predicate), obj))

    def __len__(self):
        return len(self._triples)

    def __contains__(self, triple):
        return triple in self._triples

    # -------------------------------------------------------------- reading

    def triples(self, subject=None, predicate=None, obj=None):
        """Yields the triples matching a pattern; None matches anything"""
        for statement in self._triples:
            if subject is not None and statement[0] != subject:
                continue
            if predicate is not None and statement[1] != predicate:
                continue
            if obj is not None and statement[2] != obj:
                continue
            yield statement

    def objects(self, subject, predicate):
        return [statement[2] for statement in self.triples(subject, predicate)]

    def subjects(self, predicate=None, obj=None):
        return sorted({statement[0] for statement in self.triples(None, predicate, obj)})

    def value(self, subject, predicate, default=None):
        """
        Returns the single object of subject/predicate.

        Raises if the graph holds more than one, because silently picking one
        of several conflicting values is how knowledge bases start lying.
        """
        found = self.objects(subject, predicate)
        if not found:
            return default
        if len(found) > 1:
            raise ValueError(
                "%s %s has %d values (%s); use objects() when that is expected"
                % (subject, predicate, len(found), found))
        return found[0]

    def typed(self, classIRI):
        """Returns the subjects of rdf:type classIRI, in a stable order"""
        return self.subjects(TYPE, IRI(classIRI))

    # ------------------------------------------------------------- JSON-LD

    def expand(self, term):
        """Expands a compact IRI (bcga:Order) using the loaded context"""
        if not isinstance(term, str) or term.startswith(("http://", "https://", "urn:")):
            return IRI(term)
        prefix, _, rest = term.partition(":")
        base = self.context.get(prefix)
        return IRI(base + rest) if base else IRI(term)

    def parse(self, document):
        """Loads a JSON-LD document (a dict, or a path to a .jsonld file)"""
        if isinstance(document, str):
            with open(document, encoding="utf-8") as source:
                document = json.load(source)
        for prefix, base in (document.get("@context") or {}).items():
            if isinstance(base, str):
                self.context[prefix] = base
        for node in document.get("@graph", []):
            self._parseNode(node)
        return self

    def _parseNode(self, node):
        if "@id" not in node:
            raise ValueError("every node in @graph needs an @id: %r" % (node,))
        subject = self.expand(node["@id"])
        for key, value in node.items():
            if key == "@id":
                continue
            predicate = TYPE if key == "@type" else self.expand(key)
            for item in (value if isinstance(value, list) else [value]):
                self.add(subject, predicate, self._parseValue(key, item))

    def _parseValue(self, key, item):
        if isinstance(item, dict):
            if "@id" in item:
                return self.expand(item["@id"])
            if "@value" in item:
                return item["@value"]
            raise ValueError("a value object needs @id or @value: %r" % (item,))
        # @type is always a reference; everything else scalar is a literal
        return self.expand(item) if key == "@type" else item

    def toJSONLD(self):
        """Serialises the graph back to the same JSON-LD subset"""
        nodes = {}
        for subject, predicate, obj in sorted(self._triples, key=lambda t: (t[0], t[1], str(t[2]))):
            node = nodes.setdefault(subject, {"@id": self.shrink(subject)})
            key = "@type" if predicate == TYPE else self.shrink(predicate)
            value = self.shrink(obj) if isinstance(obj, IRI) else obj
            if key != "@type" and isinstance(obj, IRI):
                value = {"@id": value}
            if key in node:
                if not isinstance(node[key], list):
                    node[key] = [node[key]]
                node[key].append(value)
            else:
                node[key] = value
        used = {prefix: base for prefix, base in self.context.items()
                if any(str(term).startswith(base)
                       for triple in self._triples for term in triple
                       if isinstance(term, IRI))}
        return {"@context": used or self.context,
                "@graph": [nodes[key] for key in sorted(nodes)]}

    def shrink(self, iri):
        """Returns the compact form of an IRI if a known prefix covers it"""
        best = None
        for prefix, base in self.context.items():
            if iri.startswith(base) and (best is None or len(base) > len(best[1])):
                best = (prefix, base)
        return "%s:%s" % (best[0], iri[len(best[1]):]) if best else str(iri)

    def toTurtle(self):
        """Serialises to Turtle, so the corpus can be read by anything"""
        lines = ["@prefix %s: <%s> ." % (prefix, base)
                 for prefix, base in sorted(self.context.items())]
        lines.append("")
        for subject in sorted({triple[0] for triple in self._triples}):
            statements = []
            for predicate in sorted({t[1] for t in self.triples(subject)}):
                terms = ", ".join(
                    self._turtleTerm(obj)
                    for obj in sorted(self.objects(subject, predicate), key=str))
                name = "a" if predicate == TYPE else "<%s>" % predicate
                statements.append("    %s %s" % (name, terms))
            lines.append("<%s>\n%s ." % (subject, " ;\n".join(statements)))
            lines.append("")
        return "\n".join(lines)

    @staticmethod
    def _turtleTerm(obj):
        if isinstance(obj, IRI):
            return "<%s>" % obj
        if isinstance(obj, bool):
            return "true" if obj else "false"
        if isinstance(obj, (int, float)):
            return repr(obj)
        return json.dumps(str(obj))

    # ------------------------------------------------------------- handoff

    def toRDFLib(self):
        """
        Returns an rdflib.Graph of the same triples, for SPARQL and reasoning.

        rdflib is never required: it is simply used when the environment has
        it, which outside Blender it usually does.
        """
        try:
            import rdflib
        except ImportError:
            raise ImportError(
                "rdflib is not installed. The BCGA knowledge layer works "
                "without it; install rdflib only if you want SPARQL or OWL.")
        graph = rdflib.Graph()
        for prefix, base in self.context.items():
            graph.bind(prefix, rdflib.Namespace(base))
        for subject, predicate, obj in self._triples:
            graph.add((
                rdflib.URIRef(subject),
                rdflib.URIRef(predicate),
                rdflib.URIRef(obj) if isinstance(obj, IRI) else rdflib.Literal(obj),
            ))
        return graph


CORPUS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "corpus")


def loadCorpus(*names):
    """
    Loads the bundled corpus, or only the named files, into one graph.

    >>> graph = loadCorpus()
    >>> len(graph) > 0
    True
    """
    graph = Graph()
    files = ["%s.jsonld" % name for name in names] if names else sorted(
        name for name in os.listdir(CORPUS) if name.endswith(".jsonld"))
    for name in files:
        graph.parse(os.path.join(CORPUS, name))
    return graph
