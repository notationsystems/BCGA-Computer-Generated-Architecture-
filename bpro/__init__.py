import ast
import importlib.util
import os
import inspect
import bpy
import bmesh

from pro import context

from .material import MaterialManager

from .util import VertexRegistry, BcgaError

from .op_decompose import Decompose
from .op_split import Split
from .op_extrude import Extrude
from .op_extrude2 import Extrude2
from .op_color import Color
from .op_material import Material
from .op_texture import Texture
from .op_delete import Delete
from .op_join import Join
from .op_inset import Inset
from .op_inset2 import Inset2
from .op_rectangle import Rectangle
from .op_hip_roof import HipRoof
from .op_copy import Copy
from .op_translate import Translate

from pro.base import Param

from .shape import getInitialShape

from .join import JoinManager


def buildFactory():
    factory = context.factory
    factory["Decompose"] = Decompose
    factory["Split"] = Split
    factory["Extrude"] = Extrude
    factory["Extrude2"] = Extrude2
    factory["Color"] = Color
    factory["Material"] = Material
    factory["Texture"] = Texture
    factory["Delete"] = Delete
    factory["Join"] = Join
    factory["Inset"] = Inset
    factory["Inset2"] = Inset2
    factory["Rectangle"] = Rectangle
    factory["HipRoof"] = HipRoof
    factory["Copy"] = Copy
    factory["Translate"] = Translate


def getUVlayerNames(path):
    """
    Returns the uv layer names a rule file asks for through the layer= argument
    of texture(..).

    The layers have to exist before the bmesh is built: adding one later
    reallocates the loop data, which invalidates every BMLoop reference the
    shapes are holding, so they cannot be created on demand while rules run.
    """
    names = set()
    try:
        with open(path, encoding="utf-8") as ruleSource:
            tree = ast.parse(ruleSource.read(), path)
    except (OSError, SyntaxError):
        # a rule file that cannot be read or parsed fails loudly when imported
        return names
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            for keyword in node.keywords:
                if keyword.arg == "layer" and isinstance(keyword.value, ast.Constant) \
                        and isinstance(keyword.value.value, str):
                    names.add(keyword.value.value)
    return names


def apply(ruleFile, startRule="Begin"):
    from .bl_util import create_rectangle

    blenderContext = context.blenderContext
    obj = blenderContext.object
    if obj:
        bpy.ops.object.mode_set(mode="OBJECT")

    if not obj or obj.type != "MESH":
        # nothing usable is selected, so start from a default footprint
        create_rectangle(blenderContext, 20, 10)
    elif len(obj.data.polygons) != 1:
        # Any single face works as a footprint, including an n-gon. Anything
        # else is someone's model: report it rather than deleting their work.
        raise BcgaError(
            "BCGA builds on a footprint of exactly one face, but '%s' has %d. "
            "Press Footprint to create one, or select a single-face polygon."
            % (obj.name, len(obj.data.polygons)))
    # apply all transformations to the active Blender object
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    # setting the path to the rule for context
    context.ruleFile = ruleFile if isinstance(
        ruleFile, str) else ruleFile.__file__
    params = None
    mesh = blenderContext.object.data
    # Give the mesh its default uv layer plus every layer the rule set names,
    # all before the bmesh is built (see getUVlayerNames for why).
    for layerName in [Texture.defaultLayer] + sorted(getUVlayerNames(context.ruleFile)):
        if layerName not in mesh.uv_layers:
            mesh.uv_layers.new(name=layerName)
    # initialize the context
    context.init()
    # initializing bmesh instance
    bm = bmesh.new()
    bm.from_mesh(mesh)
    if hasattr(bm.faces, "ensure_lookup_table"):
        bm.faces.ensure_lookup_table()
    context.addAttribute("bm", bm)
    # list of unused faces for removal
    context.addAttribute("facesForRemoval", [])
    # set up the material registry
    context.addAttribute("materialManager", MaterialManager())
    # set up vertex registry to ensure vertex uniqueness
    context.addAttribute("vertexRegistry", VertexRegistry())
    # set a constructor for join manager, it may be replaced by actual instance of the join manager
    context.addAttribute("joinManager", JoinManager)

    # push the initial state with the initial shape to the execution stack
    context.pushState(shape=getInitialShape(bm))

    if isinstance(ruleFile, str):
        module = getModule(ruleFile)

        # prepare context internal stuff
        context.prepare()
        # params is a list of tuples: (paramName, instanceofParamClass)
        params = getParams(module)
    else:
        # ruleFile is actually a module
        module = ruleFile

    # setting the current operator to a dummy one to avoid an exception
    class dummy:
        def addChildOperator(self, o): pass

        def removeChildOperators(self, numParts): pass
    context.operator = dummy()
    # evaluate the rule set
    getattr(module, startRule)().execute()

    # remove unused faces from context.facesForRemoval
    bmesh.ops.delete(bm, geom=context.facesForRemoval, context='FACES')
    # there still may be some doubles, inspite of the use of util.VertexMaterial
    #bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.0001)

    # clean up context.facesForRemoval
    context.facesForRemoval = []
    context.executeDeferred()
    # remove unused faces from context.facesForRemoval
    bmesh.ops.delete(bm, geom=context.facesForRemoval, context='FACES')

    # write everything back to the mesh
    bm.to_mesh(mesh)
    # cleaning context from blender specific members
    context.removeAttributes()

    return (module, params)


def isParam(member):
    """A predicate for the inspect.getmembers call"""
    return isinstance(member, Param)


def getModule(ruleFile):
    """Returns Python module object given a path to the rule file"""
    # remove extension from ruleFile if it was provided
    ruleFile = os.path.splitext(ruleFile)[0]
    moduleName = os.path.basename(ruleFile)
    path = ruleFile + ".py"
    # the rule file is loaded straight from its path and deliberately not cached in
    # sys.modules, so that editing a rule set and pressing Apply again re-reads it
    spec = importlib.util.spec_from_file_location(moduleName, path)
    if spec is None or spec.loader is None:
        raise ImportError("Cannot load the BCGA rule file '%s'" % path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def getParams(module):
    """Returns a list of tuples: (paramName, instanceofParamClass)"""
    return [m for m in inspect.getmembers(module, isParam)]


buildFactory()
