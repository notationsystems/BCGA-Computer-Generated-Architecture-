"""
The vocabulary used by the BCGA knowledge graph.

Terms are IRIs so the corpus is real linked data: it can be handed to rdflib,
queried with SPARQL and aligned with other vocabularies. Nothing here depends
on rdflib or on Blender.

Change BCGA below if the project takes a different namespace; every term is
derived from it, and the corpus files declare it in their @context.
"""


class IRI(str):
    """
    An identifier, as opposed to a literal.

    Subclassing str keeps the graph comfortable to work with -- terms compare
    and print like the strings they are -- while letting the serialisers tell
    a reference apart from a piece of text.
    """

    __slots__ = ()

    def __repr__(self):
        return "IRI(%s)" % str.__repr__(self)


class Namespace:
    """Builds IRIs in a namespace: BCGA.columnHeight -> <...#columnHeight>"""

    def __init__(self, prefix, base):
        self.prefix = prefix
        self.base = base

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        return IRI(self.base + name)

    def __getitem__(self, name):
        return IRI(self.base + name)

    def shrink(self, iri):
        """Returns the compact form (bcga:Order) for an IRI in this namespace"""
        if iri.startswith(self.base):
            return "%s:%s" % (self.prefix, iri[len(self.base):])
        return iri


BCGA = Namespace("bcga", "https://notationsystems.github.io/bcga/ns#")
RDFS = Namespace("rdfs", "http://www.w3.org/2000/01/rdf-schema#")
RDF = Namespace("rdf", "http://www.w3.org/1999/02/22-rdf-syntax-ns#")
DCTERMS = Namespace("dcterms", "http://purl.org/dc/terms/")

NAMESPACES = {ns.prefix: ns for ns in (BCGA, RDFS, RDF, DCTERMS)}

# the handful of terms the resolver and the audit rely on by name
TYPE = RDF.type
LABEL = RDFS.label
COMMENT = RDFS.comment
SOURCE = DCTERMS.source
