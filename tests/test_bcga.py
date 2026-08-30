"""
Regression tests for BCGA against a real Blender.

These drive the add-on through the bpy module, so they catch the kind of
silent API breakage that left BCGA unusable between Blender 2.80 and 4.2.

Requires the bpy module matching the Blender release under test:

    python3 -m pip install bpy==4.2.0     # needs Python 3.11
    python3 tests/test_bcga.py
"""

import os
import shutil
import sys
import tempfile
import traceback

TESTS = os.path.dirname(os.path.abspath(__file__))
ADDON = os.path.dirname(TESTS)

try:
    import bpy
except ImportError:
    sys.exit("bpy is not installed; see the module docstring for how to run these tests")


def stage():
    """
    Copies the add-on into a temporary directory under an importable name and
    the rule files next to a generated texture, then makes both importable.
    """
    tmp = tempfile.mkdtemp(prefix="bcga-tests-")
    package = os.path.join(tmp, "addons", "bcga")
    shutil.copytree(
        ADDON, package,
        ignore=shutil.ignore_patterns(".git", "tests", "__pycache__", "*.pyc")
    )
    rules = os.path.join(tmp, "rules")
    shutil.copytree(os.path.join(TESTS, "rules"), rules)
    # the texture the rule files refer to, written where texture() looks for it
    assets = os.path.join(rules, "assets")
    os.makedirs(assets)
    image = bpy.data.images.new(name="wall", width=8, height=8)
    image.filepath_raw = os.path.join(assets, "wall.png")
    image.file_format = "PNG"
    image.save()
    sys.path.insert(0, os.path.join(tmp, "addons"))
    return tmp, rules, package


TMP, RULES, PACKAGE = stage()

import bcga
import bpro
from pro import context as proContext

RESULTS = []


def check(name, function):
    try:
        RESULTS.append(("PASS", name, function() or ""))
    except Exception as error:
        RESULTS.append(("FAIL", name, "%s: %s" % (type(error).__name__, error)))
        traceback.print_exc()


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def ruleFile(name):
    return os.path.join(RULES, name)


def build(name, size="20x10"):
    """Footprint, then apply a rule file, returning the generated object"""
    reset()
    bpy.ops.object.footprint_set(size=size)
    proContext.blenderContext = bpy.context
    bpro.apply(ruleFile(name))
    return bpy.context.view_layer.objects.active


# --------------------------------------------------------------- registration

def t_register():
    bcga.register()
    assert hasattr(bpy.types.Scene, "bcgaScript"), "scene property missing after register"
    return "registered on Blender %s" % bpy.app.version_string


def t_unregister_is_clean():
    bcga.unregister()
    leaked = [p for p in ("bcgaScript", "bakingBcgaScript") if hasattr(bpy.types.Scene, p)]
    assert not leaked, "properties leaked after unregister: %s" % leaked
    bcga.register()
    return "register/unregister leaves no Scene properties behind"


# ------------------------------------------------------------------ footprint

def t_footprint_at_cursor():
    reset()
    bpy.context.scene.cursor.location = (3.0, -4.0, 5.0)
    assert bpy.ops.object.footprint_set(size="20x10") == {"FINISHED"}
    obj = bpy.context.view_layer.objects.active
    assert obj and obj.type == "MESH", "no active mesh after footprint_set"
    assert len(obj.data.polygons) == 1, "expected 1 polygon, got %d" % len(obj.data.polygons)
    assert obj.select_get(), "the new footprint is not selected"
    location = tuple(round(c, 4) for c in obj.location)
    assert location == (3.0, -4.0, 5.0), "not placed at the 3D cursor: %s" % (location,)
    lamps = [o for o in bpy.data.objects if o.type == "LIGHT"]
    assert len(lamps) == 4, "expected 4 sun lamps, got %d" % len(lamps)
    return "placed at the cursor %s with %d lamps" % (location, len(lamps))


def t_footprint_custom_size():
    reset()
    assert bpy.ops.object.footprint_set(width=7, depth=3, lights=False) == {"FINISHED"}
    obj = bpy.context.view_layer.objects.active
    dimensions = tuple(round(d, 3) for d in obj.dimensions[:2])
    assert dimensions == (7.0, 3.0), "expected 7x3, got %s" % (dimensions,)
    assert not [o for o in bpy.data.objects if o.type == "LIGHT"], "lights added despite lights=False"
    return "custom 7x3 footprint, lights suppressed"


def t_footprint_keeps_user_meshes():
    reset()
    bpy.ops.mesh.primitive_monkey_add()
    mine = bpy.context.object.name
    bpy.ops.object.footprint_set(size="20x10", lights=False)
    assert mine in bpy.data.objects, "footprint_set deleted the user's own mesh %r" % mine
    return "an unrelated active mesh survives the Footprint button"


def t_footprint_replaces_its_own():
    reset()
    bpy.ops.object.footprint_set(size="20x10", lights=False)
    bpy.ops.object.footprint_set(size="10x10", lights=False)
    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    assert len(meshes) == 1, "expected the BCGA footprint to be replaced, got %s" % [o.name for o in meshes]
    return "a previous BCGA footprint is replaced rather than duplicated"


def t_first_edge():
    reset()
    bpy.ops.object.footprint_set(size="20x10")
    assert bpy.ops.object.first_edge_ymin() == {"FINISHED"}
    obj = bpy.context.view_layer.objects.active
    assert len(obj.data.polygons) == 1, "face lost: %d polygons" % len(obj.data.polygons)
    return "bmesh.ops.delete(context='FACES') keeps the face intact"


# --------------------------------------------------------------- rule loading

def t_getmodule():
    proContext.init()  # apply() does this before importing a rule module
    module = bpro.getModule(ruleFile("simple.py"))
    assert hasattr(module, "Begin"), "rule module has no Begin rule"
    assert "simple" not in sys.modules, "rule module leaked into sys.modules"
    return "importlib loader works and does not cache the rule module"


# ------------------------------------------------------------------ geometry

def t_extrude_and_color():
    obj = build("simple.py")
    assert len(obj.data.polygons) > 1, "extrude produced %d polygons" % len(obj.data.polygons)
    assert len(obj.data.materials) >= 2, "expected 2 colour materials, got %d" % len(obj.data.materials)
    return "%d faces, %d materials" % (len(obj.data.polygons), len(obj.data.materials))


def t_split_and_texture():
    obj = build("floors.py")
    assert len(obj.data.polygons) == 17, "expected 17 faces, got %d" % len(obj.data.polygons)
    return "%d faces, %d materials, uv layers %s" % (
        len(obj.data.polygons), len(obj.data.materials),
        [layer.name for layer in obj.data.uv_layers])


def t_matrix_operators():
    obj = build("matrices.py")
    assert len(obj.data.polygons) > 1, "only %d polygons" % len(obj.data.polygons)
    return "%d faces from rectangle() and translate()" % len(obj.data.polygons)


def t_ngon_footprint():
    reset()
    mesh = bpy.data.meshes.new("plot")
    mesh.from_pydata(
        [(0, 0, 0), (12, 0, 0), (14, 7, 0), (6, 11, 0), (-2, 6, 0)], [], [(0, 1, 2, 3, 4)])
    obj = bpy.data.objects.new("plot", mesh)
    bpy.context.scene.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    proContext.blenderContext = bpy.context
    bpro.apply(ruleFile("simple.py"))
    built = bpy.context.view_layer.objects.active
    assert len(built.data.polygons) == 6, "expected 6 faces from a 5-gon plot, got %d" % len(built.data.polygons)
    return "an arbitrary 5-gon plot builds %d faces" % len(built.data.polygons)


def t_second_uv_layer():
    obj = build("uvlayers.py")
    names = [layer.name for layer in obj.data.uv_layers]
    assert "second" in names, "the uv layer requested by the rule set is missing: %s" % names
    return "uv layers created up front: %s" % names


# ------------------------------------------------------------------ materials

def t_texture_material():
    obj = build("floors.py")
    textured = [
        (m, n) for m in obj.data.materials if m and m.use_nodes
        for n in m.node_tree.nodes
        if n.bl_idname == "ShaderNodeTexImage" and n.image
    ]
    assert textured, "no image texture node with an image"
    material, node = textured[0]
    links = [l for l in material.node_tree.links if l.from_node.name == node.name]
    assert links, "the image texture node is not linked to anything"
    target = links[0].to_node
    assert target.bl_idname != "ShaderNodeOutputMaterial", \
        "texture linked straight into the Material Output (the nodes[1] bug)"
    return "engine %s, image -> %s.%s" % (
        bpy.context.scene.render.engine, target.bl_idname, links[0].to_socket.name)


# --------------------------------------------------------------------- guards

def t_apply_keeps_user_meshes():
    reset()
    bpy.ops.mesh.primitive_cube_add()
    cube = bpy.context.object.name
    proContext.blenderContext = bpy.context
    try:
        bpro.apply(ruleFile("simple.py"))
    except bpro.BcgaError as error:
        assert cube in bpy.data.objects, "apply() deleted the user's mesh %r" % cube
        return "a multi-face mesh is reported, not deleted (%s)" % str(error)[:60]
    raise AssertionError("apply() accepted a 6-face cube as a footprint")


def t_broken_rules_are_reported():
    reset()
    bpy.ops.object.footprint_set(size="20x10")
    proContext.blenderContext = bpy.context
    reported = []

    class Reporter:
        def report(self, level, message):
            reported.append(message)

    _, ok = bcga.runRules(Reporter(), bpro.apply, ruleFile("broken.py"))
    assert not ok, "a rule set raising ValueError was treated as success"
    assert reported and "deliberately broken" in reported[0], "unhelpful report: %s" % reported
    return "a failing rule set reports %r" % reported[0][:60]


def t_empty_script_field():
    reset()
    bpy.ops.object.footprint_set(size="20x10")
    bpy.context.scene.bcgaScript = ""
    assert bpy.ops.object.apply_pro_script("INVOKE_DEFAULT") == {"CANCELLED"}
    return "Apply with an empty Script field cancels instead of raising KeyError"


def t_unsaved_text_datablock():
    text = bpy.data.texts.new("internal_rules")
    text.write("from pro import *\n")
    bpy.context.scene.bcgaScript = text.name
    assert bpy.ops.object.apply_pro_script("INVOKE_DEFAULT") == {"CANCELLED"}
    return "Apply on an unsaved text datablock cancels with an explanation"


def t_text_datablock_to_geometry():
    reset()
    bpy.ops.object.footprint_set(size="20x10")
    text = bpy.data.texts.load(ruleFile("simple.py"))
    bpy.context.scene.bcgaScript = text.name

    class Reporter:
        def report(self, level, message):
            self.message = message

    path = bcga.getRuleFile(bpy.context.scene.bcgaScript, Reporter())
    assert path and os.path.isfile(path), "getRuleFile did not resolve the text datablock"
    proContext.blenderContext = bpy.context
    bpro.apply(path)
    obj = bpy.context.view_layer.objects.active
    assert len(obj.data.polygons) > 1, "no geometry generated"
    return "a text datablock resolves to %d faces" % len(obj.data.polygons)


# ----------------------------------------------------------------------- bake

def t_bake():
    reset()
    bpy.ops.preferences.addon_enable(module="cycles")
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 1
    bpy.ops.object.footprint_set(size="20x10")
    scene.bcgaScript = bpy.data.texts.load(ruleFile("simple.py")).name
    scene.bakingBcgaScript = bpy.data.texts.load(ruleFile("lowpoly.py")).name
    assert bpy.ops.object.bake_pro_model() == {"FINISHED"}
    obj = bpy.context.view_layer.objects.active
    images = [
        n.image for m in obj.data.materials if m and m.use_nodes
        for n in m.node_tree.nodes if n.bl_idname == "ShaderNodeTexImage" and n.image
    ]
    assert images, "no baked image texture node on the low poly object"
    assert len([o for o in bpy.data.objects if o.type == "MESH"]) == 1, "high poly duplicate left behind"
    pixels = list(images[0].pixels)
    colours = [(pixels[i], pixels[i + 1], pixels[i + 2]) for i in range(0, len(pixels), 4)]
    lit = [c for c in colours if max(c) > 0.01]
    assert lit, "the baked image is entirely black - nothing was captured"
    assert [c for c in lit if c[0] > 0.5 and c[1] < 0.5], "the facade colour is missing from the bake"
    assert [c for c in lit if c[1] > 0.5 and c[0] < 0.5], "the roof colour is missing from the bake"
    return "baked %d/%d pixels carrying the high poly colours" % (len(lit), len(colours))


def t_bake_without_scripts():
    reset()
    bpy.ops.preferences.addon_enable(module="cycles")
    bpy.context.scene.render.engine = "CYCLES"
    bpy.ops.object.footprint_set(size="20x10")
    bpy.context.scene.bcgaScript = ""
    bpy.context.scene.bakingBcgaScript = ""
    before = len(bpy.data.objects)
    # bpy.ops turns a reported ERROR plus CANCELLED into a Python RuntimeError
    try:
        assert bpy.ops.object.bake_pro_model() == {"CANCELLED"}
    except RuntimeError as error:
        assert "script" in str(error).lower(), "unexpected error: %s" % error
    assert len(bpy.data.objects) == before, "a stray high poly duplicate was left behind"
    return "missing scripts cancel without leaving a duplicate"


# ------------------------------------------------------- the knowledge layer

def t_ontology_drives_the_rules():
    """
    The example rule set states no proportion of its own: it resolves them
    from bcga_onto. So the built geometry is the check on that whole path --
    corpus, resolver, grammar, bmesh -- landing where the canon says.
    """
    from bcga_onto import canon

    width, depth, podium = 20.0, 12.0, 1.5
    reset()
    bpy.ops.object.footprint_set(width=width, depth=depth, lights=False)
    proContext.blenderContext = bpy.context
    bpro.apply(os.path.join(PACKAGE, "examples", "classical_front.py"))
    obj = bpy.context.view_layer.objects.active

    resolver = canon()
    order = resolver.orderFor("houses")
    module = resolver.moduleForSpan(width, 6, "eustyle")
    courses = resolver.elevationBands(order, module=module, spacing="eustyle", podium=podium)

    expected, running = [0.0], 0.0
    for _, height in courses:
        running += height
        expected.append(running)

    built = sorted({round(vertex.co.z, 4) for vertex in obj.data.vertices})
    assert len(built) == len(expected), \
        "expected %d course levels, the mesh has %d: %s" % (len(expected), len(built), built)
    for wanted, got in zip(expected, built):
        assert abs(wanted - got) < 1e-3, \
            "course at %.4f but the canon puts it at %.4f (all: %s)" % (got, wanted, built)

    xs = [vertex.co.x for vertex in obj.data.vertices]
    assert abs((max(xs) - min(xs)) - width) < 1e-3, "the front is %.3f wide, not %.3f" % (
        max(xs) - min(xs), width)
    # 6 columns and 5 voids on each of the four faces, plus the courses and roof
    assert len(obj.data.materials) == 7, [m.name for m in obj.data.materials]
    return "%s chosen by decor, M=%.4f, %d courses at %s" % (
        order, module, len(courses), ", ".join("%.3f" % level for level in built[1:]))


def t_colour_is_linearised():
    """
    color("#553322") must render as #553322.

    Rule sets write sRGB hex, but Material.diffuse_color is linear, so the
    value has to be converted on the way in. Assigning sRGB straight into it
    renders every colour far too light: #553322 came out #9c7c66.
    """
    from bpro.op_color import srgbToLinear

    reset()
    bpy.ops.object.footprint_set(size="20x10")
    proContext.blenderContext = bpy.context
    bpro.apply(ruleFile("simple.py"))
    obj = bpy.context.view_layer.objects.active
    checked = 0
    for material in obj.data.materials:
        if material is None or not material.name.startswith("#"):
            continue
        wanted = [srgbToLinear(component / 255)
                  for component in bytes.fromhex(material.name[-6:])]
        got = list(material.diffuse_color)[:3]
        for expected, actual in zip(wanted, got):
            assert abs(expected - actual) < 1e-6, \
                "%s is %s, expected the linear %s" % (material.name, got, wanted)
        assert abs(material.diffuse_color[3] - 1.0) < 1e-6, \
            "alpha is %r, expected 1.0" % material.diffuse_color[3]
        checked += 1
    assert checked, "no colour materials to check"
    return "%d colour materials hold the linear value of their hex" % checked


def main():
    for name, function in [
        ("register add-on", t_register),
        ("unregister is clean", t_unregister_is_clean),
        ("Footprint places at the 3D cursor", t_footprint_at_cursor),
        ("Footprint honours a custom size", t_footprint_custom_size),
        ("Footprint keeps unrelated meshes", t_footprint_keeps_user_meshes),
        ("Footprint replaces its own", t_footprint_replaces_its_own),
        ("First edge rearranges the face", t_first_edge),
        ("rule modules load via importlib", t_getmodule),
        ("extrude and colour", t_extrude_and_color),
        ("split and texture", t_split_and_texture),
        ("rectangle and translate matrices", t_matrix_operators),
        ("an n-gon plot as a footprint", t_ngon_footprint),
        ("a second uv layer is created", t_second_uv_layer),
        ("texture material node wiring", t_texture_material),
        ("apply keeps unrelated meshes", t_apply_keeps_user_meshes),
        ("a broken rule set is reported", t_broken_rules_are_reported),
        ("Apply with an empty script field", t_empty_script_field),
        ("Apply with an unsaved text", t_unsaved_text_datablock),
        ("a text datablock builds geometry", t_text_datablock_to_geometry),
        ("Bake writes the high poly colours", t_bake),
        ("Bake without scripts cancels", t_bake_without_scripts),
        ("the ontology drives a rule set", t_ontology_drives_the_rules),
        ("colours are linearised for render", t_colour_is_linearised),
    ]:
        check(name, function)

    print("\n" + "=" * 78)
    passed = sum(1 for r in RESULTS if r[0] == "PASS")
    for status, name, detail in RESULTS:
        print("%-4s %-42s %s" % (status, name, detail))
    print("=" * 78)
    print("%d/%d passed on Blender %s" % (passed, len(RESULTS), bpy.app.version_string))
    shutil.rmtree(TMP, ignore_errors=True)
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
