### BCGA (Computer Generated Architecture for Blender)

BCGA is a procedural and iterative approach to generate architectural 3D models. A set of small Python functions called rules is used to generate 3D models of buildings. Each subsequent rule refines the model and adds additional details. The concept of BCGA was inspired by CGA shape grammar developed in ETH Zurich.

Here is a brief description of the 3D model generation process on a simple example. The process starts from a 2D building outline. Its extrusion is created with the desired height. The extruded 3D shape is decomposed into a number of vertical rectangles corresponding to building facades and the upper polygon used as the base for the building roof. Floors are cut for each facade. Each floor is cut into sections with windows. Each section can be refined further.

Some parameters of the set of rules can be defined as accessible from outside. They can be changed in the Blender panel. The resulting changes in the generated 3D model are shown interactively in the Blender 3D View window.

BCGA can be used to code existing buildings from a number of photos as well as to generate imaginary cities with desired styles of buildings.

Example sets of BCGA rules:
* [simple01.py](https://github.com/vvoovv/bcga-examples/blob/master/examples/simple01.py), [video](https://www.youtube.com/watch?v=GixKhqrdANs)
* [house_01.py](https://github.com/vvoovv/bcga-examples/blob/master/examples/house_01.py), [video](http://www.youtube.com/watch?v=ZJDHtPAF9d8)

The basic concepts of BCGA are explained in the [tutorial](https://github.com/vvoovv/bcga/wiki/Tutorial).

twitter: [@prokitektura](https://twitter.com/prokitektura)

Thread at blenderartists.org: http://blenderartists.org/forum/showthread.php?351081-Addon-BCGA-Computer-Generated-Architecture-for-Blender-3D-buildings-with-Python


## The knowledge layer (`bcga_onto`)

BCGA already separates the abstract shape grammar (`pro`) from its Blender
backend (`bpro`). `bcga_onto` sits on the other side of the grammar: a graph of
architectural knowledge, with its sources, that resolves into the parameters a
rule set builds from. **Proportions live in the corpus, not in the rules** —
correct a source and every model built from it changes.

It depends on nothing but the standard library, because a Blender add-on cannot
install packages. `rdflib` is used only if it happens to be present.

```python
from bcga_onto import canon, Audit

front = canon().templeFront(columns=6, module=0.9, purpose="libraries")
front["order"]["order"]           # 'Ionic' — chosen by decor, not by taste
front["colonnade"]["positions"]   # column centres about the axis
front["order"]["sources"]         # ['Vitruvius, De architectura I.2', ...]

text, ok = Audit.report(Audit().templeFront(front))
```

`examples/classical_front.py` is a rule set that states no proportion of its
own: the order, the bay rhythm and the courses of the entablature are all
resolved from the graph. Point the Script field at it and press Apply.

### What the corpus contains

| File | Holds |
|---|---|
| `orders.jsonld` | The five orders — column height, entablature ratio and its 3:3:4 division, fluting, diminution, and the purposes each order suits |
| `intercolumniation.jsonld` | The five named spacings with their clear space and Vitruvius' slenderness correction; the portico column counts |
| `rooms.jsonld` | Palladio's seven room shapes and the three means for ceiling height |
| `composition.jsonld` | The triad, the six principles, and the Palladian villa composition rules |
| `citations.jsonld` | The sources everything else points at |

Every instance node carries a `dcterms:source`, and a test enforces it: a
knowledge base without provenance is just numbers someone typed.

### Generation and audit read the same graph

The resolver produces something canonical by construction; the audit checks a
design that came from anywhere else. Because both read the same corpus they
cannot drift apart. The audit is not decorative — it catches real conflicts:

```
FAIL symmetria: the bays are not all the same width (2.925, 3.6), so the
metopes cannot all be square. Doric and a widened centre bay cannot both be
satisfied: fix the bay, not the frieze
```

### Honest limits

- **The corpus is the canon, not a corpus of measured buildings.** It encodes
  what Vitruvius and Palladio state, with citations. It contains no dimensions
  of specific villas, because inventing them would be worse than omitting them.
  Ingesting a real precedent dataset is the obvious next step and needs a
  source to point at.
- **`graph.py` is not a full JSON-LD 1.1 processor.** It reads the subset the
  corpus uses, which its docstring states exactly. Anything richer should go
  through `toRDFLib()`.
- One note is recorded in `orders.jsonld` where a source's own wording is
  self-inconsistent (the pediment ratio), with the reasoning for the reading
  taken. Where the sources disagree with themselves, the corpus says so rather
  than quietly picking.

### Tests

```
python3 tests/test_onto.py     # the knowledge layer, no Blender needed
python3 tests/test_bcga.py     # the add-on, needs `pip install bpy==4.2.0`
```

## Donations
If you like BCGA, please consider making a donation:

[![Please donate](https://www.paypalobjects.com/en_US/GB/i/btn/btn_donateCC_LG.gif)](https://www.paypal.com/cgi-bin/webscr?cmd=_s-xclick&hosted_button_id=ZZ7CHNYKWYYZE)
