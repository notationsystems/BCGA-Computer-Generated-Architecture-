import math
import os
import sys
import traceback

bl_info = {
	"name": "BCGA",
	"author": "Vladimir Elistratov <vladimir.elistratov@gmail.com>",
	"version": (1, 0, 0),
	"blender": (4, 2, 0),
	"location": "View3D > Tool Shelf",
	"description": "BCGA: Computer Generated Architecture for Blender",
	"warning": "",
	"doc_url": "https://github.com/vvoovv/bcga/wiki",
	"tracker_url": "https://github.com/vvoovv/bcga/issues",
	"support": "COMMUNITY",
	"category": "BCGA",
}

numFloatParams = 200
numColorParams = 50

# Rule files are ordinary Python modules that start with `from pro import *`,
# and the bpro/pro packages import each other by absolute name, so this
# directory has to be importable no matter how Blender loaded the add-on. The
# previous check looked for the substring "bpro" in existing sys.path entries,
# which never matches the installed directory name, and raised NameError when
# sys.path was empty.
_addonDirectory = os.path.dirname(os.path.abspath(__file__))
if _addonDirectory not in sys.path:
	sys.path.append(_addonDirectory)

import bpy
import bpro

from pro import context as proContext
from pro.base import ParamFloat, ParamColor

from bpro.bl_util import create_rectangle, align_view, first_edge_ymin, newObjectName


def removeObject(context, obj, makeActive=None):
	"""Deletes obj and its mesh, then makes makeActive the active object"""
	bpy.ops.object.select_all(action="DESELECT")
	obj.select_set(True)
	context.view_layer.objects.active = obj
	mesh = obj.data
	bpy.ops.object.delete()
	bpy.data.meshes.remove(mesh)
	if makeActive:
		context.view_layer.objects.active = makeActive


def runRules(operator, function, *args):
	"""
	Runs a BCGA build, reporting any failure in the Blender interface.

	Without this a broken rule set only shows up as a traceback in the system
	console, which most users never have open, and the button looks like it did
	nothing. Returns (result, True) on success and (None, False) on failure.
	"""
	try:
		return function(*args), True
	except bpro.BcgaError as e:
		operator.report({"ERROR"}, str(e))
	except Exception as e:
		# the full traceback still goes to the console, for debugging a rule set
		traceback.print_exc()
		operator.report({"ERROR"}, "The BCGA script failed -- %s: %s" % (type(e).__name__, e))
	return None, False


def getRuleFile(textName, operator, label="Script"):
	"""
	Returns the full path to the BCGA script held by the named text datablock,
	or None if it cannot be used (the reason is reported to the operator).
	"""
	if not textName:
		operator.report({"ERROR"}, "Select a BCGA script in the '%s' field first" % label)
		return None
	text = bpy.data.texts.get(textName)
	if text is None:
		operator.report({"ERROR"}, "The BCGA script '%s' is not open in Blender" % textName)
		return None
	if not text.filepath:
		# a rule set typed into the text editor has never been written to disk,
		# and BCGA can only import it as a module from a real file
		operator.report({"ERROR"}, "Save the BCGA script '%s' to a file first" % textName)
		return None
	ruleFile = os.path.realpath(os.path.expanduser(bpy.path.abspath(text.filepath)))
	if not os.path.isfile(ruleFile):
		operator.report({"ERROR"}, "The BCGA script '%s' was not found" % ruleFile)
		return None
	return ruleFile
	
class CustomFloatProperty(bpy.types.PropertyGroup):
	"""A bpy.types.PropertyGroup descendant for bpy.props.CollectionProperty"""
	value: bpy.props.FloatProperty(name="")

class CustomColorProperty(bpy.types.PropertyGroup):
	"""A bpy.types.PropertyGroup descendant for bpy.props.CollectionProperty"""
	value: bpy.props.FloatVectorProperty(name="", subtype='COLOR', min=0.0, max=1.0)

class BCGA_PT_main(bpy.types.Panel):
	bl_label = "Main"
	bl_space_type = "VIEW_3D"
	bl_region_type = "UI"
	#bl_context = "objectmode"
	bl_category = "BCGA"
	
	def draw(self, context):
		scene = context.scene
		layout = self.layout
		layout.row().operator_menu_enum("object.footprint_set", "size", text="Footprint")
		layout.separator()
		layout.row().prop_search(scene, "bcgaScript", bpy.data, "texts")
		layout.row().operator("object.apply_pro_script")


class BCGA_PT_baking(bpy.types.Panel):
	bl_label = "Baking"
	bl_space_type = "VIEW_3D"
	bl_region_type = "UI"
	bl_category = "BCGA"
	bl_options = {"DEFAULT_CLOSED"}
	
	def draw(self, context):
		scene = context.scene
		layout = self.layout
		layout.row().prop_search(scene, "bakingBcgaScript", bpy.data, "texts")
		self.layout.operator("object.bake_pro_model")


class BCGA_PT_first_edge(bpy.types.Panel):
	bl_label = "First edge"
	bl_space_type = "VIEW_3D"
	bl_region_type = "UI"
	bl_category = "BCGA"
	bl_options = {"DEFAULT_CLOSED"}
	
	def draw(self, context):
		self.layout.operator("object.first_edge_ymin")


class Pro(bpy.types.Operator):
	bl_idname = "object.apply_pro_script"
	bl_label = "Apply"
	bl_options = {"REGISTER", "UNDO"}
	
	collectionFloat: bpy.props.CollectionProperty(type=CustomFloatProperty)
	collectionColor: bpy.props.CollectionProperty(type=CustomColorProperty)
	
	initialized = False
	
	def initialize(self):
		if self.initialized:
			return
		for _ in range(numFloatParams):
			self.collectionFloat.add()
		for _ in range(numColorParams):
			self.collectionColor.add()
		self.initialized = True
	
	def invoke(self, context, event):
		self.initialize()
		proContext.blenderContext = context
		ruleFile = getRuleFile(context.scene.bcgaScript, self)
		if ruleFile:
			# append the directory of the ruleFile to sys.path
			ruleFileDirectory = os.path.dirname(os.path.realpath(os.path.expanduser(ruleFile)))
			if ruleFileDirectory not in sys.path:
				sys.path.append(ruleFileDirectory)

			result, ok = runRules(self, bpro.apply, ruleFile)
			if not ok:
				return {"CANCELLED"}
			module,params = result
			
			#align_view(context.object)
			
			self.module = module
			self.params = params
			numFloats = 0
			numColors = 0
			# for each entry in self.params create a new item in self.collection
			for param in self.params:
				param = param[1]
				if isinstance(param, ParamFloat):
					collectionItem = self.collectionFloat[numFloats]
					numFloats += 1
				elif isinstance(param, ParamColor):
					collectionItem = self.collectionColor[numColors]
					numColors += 1
				collectionItem.value = param.getValue()
				param.collectionItem = collectionItem
		else:
			return {"CANCELLED"}
		return {"FINISHED"}
	
	def execute(self, context):
		if not hasattr(self, "params"):
			# invoke() bailed out, so there is nothing to re-apply
			return {"CANCELLED"}
		proContext.blenderContext = context
		for param in self.params:
			param = param[1]
			param.setValue(getattr(param.collectionItem, "value"))
		_, ok = runRules(self, bpro.apply, self.module)
		if not ok:
			return {"CANCELLED"}
		
		#align_view(context.object)
		
		return {"FINISHED"}
	
	def draw(self, context):
		layout = self.layout
		if hasattr(self, "params"):
			# self.params is a list of tuples: (paramName, instanceofParamClass)
			for param in self.params:
				paramName = param[0]
				row = layout.split()
				row.label(text=paramName + ":")
				row.prop(param[1].collectionItem, "value")


class Bake(bpy.types.Operator):
	bl_idname = "object.bake_pro_model"
	bl_label = "Bake"
	bl_options = {"REGISTER", "UNDO"}

	@classmethod
	def poll(cls, context):
		return context.scene.render.engine == "CYCLES"

	def execute(self, context):
		proContext.blenderContext = context
		lowPolyObject = context.object
		if not lowPolyObject or lowPolyObject.type != "MESH":
			self.report({"ERROR"}, "Select the BCGA mesh to bake onto")
			return {"CANCELLED"}
		# resolve both rule files before anything is duplicated, so that a missing
		# script cannot leave a stray high poly object behind
		highPolyRuleFile = getRuleFile(context.scene.bcgaScript, self, "Script")
		lowPolyRuleFile = getRuleFile(context.scene.bakingBcgaScript, self, "Low poly script")
		if not highPolyRuleFile or not lowPolyRuleFile:
			return {"CANCELLED"}
		bpy.ops.object.select_all(action="DESELECT")
		# remember the original object, it will be used for low poly model
		lowPolyObject.select_set(True)
		bpy.ops.object.duplicate()
		highPolyObject = context.object
		# high poly model
		# convert highPolyParams to a dict paramName->instanceofParamClass
		result, ok = runRules(self, bpro.apply, highPolyRuleFile)
		if not ok:
			removeObject(context, highPolyObject, lowPolyObject)
			return {"CANCELLED"}
		highPolyParams = dict(result[1])

		# low poly model
		context.view_layer.objects.active = lowPolyObject
		name = lowPolyObject.name
		module, ok = runRules(self, bpro.getModule, lowPolyRuleFile)
		if not ok:
			removeObject(context, highPolyObject, lowPolyObject)
			return {"CANCELLED"}
		lowPolyParams = bpro.getParams(module)
		# Apply highPolyParams to lowPolyParams
		# Normally lowPolyParams is a subset of highPolyParams
		for paramName,param in lowPolyParams:
			if paramName in highPolyParams:
				param.setValue(highPolyParams[paramName].getValue())
		_, ok = runRules(self, bpro.apply, module)
		if not ok:
			removeObject(context, highPolyObject, lowPolyObject)
			return {"CANCELLED"}
		# unwrap the low poly model
		bpy.ops.object.mode_set(mode="EDIT")
		bpy.ops.mesh.select_all(action="SELECT")
		bpy.ops.uv.smart_project()
		bpy.ops.object.mode_set(mode="OBJECT")
		# create a new image with default settings for baking
		image = bpy.data.images.new(name=name, width=512, height=512)
		# The bake is written into the active image texture node of the target
		# object's material, so that material has to exist beforehand.
		material = bpy.data.materials.new(name)
		material.use_nodes = True
		nodes = material.node_tree.nodes
		textureNode = nodes.new("ShaderNodeTexImage")
		textureNode.image = image
		textureNode.location = -300, 300
		nodes.active = textureNode
		# The bake is written per face, through the material that face uses, so the
		# many materials of the generated low poly model are replaced by the single
		# baked one -- which is the point of baking in the first place.
		lowPolyMesh = lowPolyObject.data
		lowPolyMesh.materials.clear()
		lowPolyMesh.materials.append(material)
		for polygon in lowPolyMesh.polygons:
			polygon.material_index = 0
		# prepare settings for baking
		highPolyObject.select_set(True)
		lowPolyObject.select_set(True)
		context.view_layer.objects.active = lowPolyObject
		bakeSettings = context.scene.render.bake
		bakeSettings.use_selected_to_active = True
		# bake the plain surface colour, without lighting contributions
		bakeSettings.use_pass_direct = False
		bakeSettings.use_pass_indirect = False
		bakeSettings.use_pass_color = True
		# finally perform baking
		bpy.ops.object.bake(type="DIFFUSE")
		# delete the high poly object and its mesh
		removeObject(context, highPolyObject, lowPolyObject)
		return {"FINISHED"}


class FootprintSet(bpy.types.Operator):
	bl_idname = "object.footprint_set"
	bl_label = "BCGA footprint"
	bl_description = "Set a building footprint for BCGA"
	bl_options = {"REGISTER", "UNDO"}
	
	size: bpy.props.EnumProperty(
		items = [
			("35x15", "rectangle 35x15", "35x15"),
			("20x10", "rectangle 20x10", "20x10"),
			("10x10", "rectangle 10x10", "10x10")
		]
	)

	width: bpy.props.FloatProperty(
		name = "Width",
		description = "Footprint size along the x axis",
		default = 20,
		min = 0.01,
		unit = "LENGTH"
	)

	depth: bpy.props.FloatProperty(
		name = "Depth",
		description = "Footprint size along the y axis",
		default = 10,
		min = 0.01,
		unit = "LENGTH"
	)

	lights: bpy.props.BoolProperty(
		name = "Add lights",
		description = "Add four sun lamps around the footprint",
		default = True
	)

	def draw(self, context):
		# the preset is chosen from the menu; the redo panel adjusts the result
		layout = self.layout
		layout.prop(self, "width")
		layout.prop(self, "depth")
		layout.prop(self, "lights")

	def execute(self, context):
		# A preset from the menu seeds the size, but an explicit width/depth (typed
		# into the redo panel, or passed by a script) always wins.
		if not self.properties.is_property_set("width"):
			self.width, self.depth = [float(i) for i in self.size.split("x")]
		width, depth = self.width, self.depth
		# Replace a footprint BCGA made itself, but never delete anything else --
		# the active object may well be the user's own model.
		active = context.object
		if active and active.type == "MESH" and active.name.startswith(newObjectName):
			removeObject(context, active)
		if self.lights:
			self.addLights(context, width, depth)
		create_rectangle(context, width, depth)
		align_view(context.object)
		return {"FINISHED"}

	def addLights(self, context, width, depth):
		lightOffset = 20
		lightHeight = 20
		rx = math.atan((depth+lightOffset)/lightHeight)
		rz = math.atan((width+lightOffset)/(depth+lightOffset))
		def lamp_add(x, y, rx, rz):
			bpy.ops.object.light_add(
				type="SUN",
				location=((x,y,lightHeight)),
				rotation=(rx, 0, rz)
			)
			context.active_object.data.energy = 0.5
		lamp_add(width+lightOffset, depth+lightOffset, -rx, -rz)
		lamp_add(-width-lightOffset, depth+lightOffset, -rx, rz)
		lamp_add(-width-lightOffset, -depth-lightOffset, rx, -rz)
		lamp_add(width+lightOffset, -depth-lightOffset, rx, rz)


class FirstEdgeYmin(bpy.types.Operator):
	bl_idname = "object.first_edge_ymin"
	bl_label = "Contains min Y"
	bl_description = "The first edge contains the vertex with minimal Y coordinate and has a longer length"
	bl_options = {"REGISTER", "UNDO"}
	
	def execute(self, context):
		first_edge_ymin(context)
		return {"FINISHED"}


classes = (
	CustomColorProperty,
	CustomFloatProperty,
    FirstEdgeYmin,
    FootprintSet,
    Bake,
	Pro,
	BCGA_PT_main,
	BCGA_PT_baking,
	BCGA_PT_first_edge
)
_registerClasses, _unregisterClasses = bpy.utils.register_classes_factory(classes)


def register():
	_registerClasses()
	bpy.types.Scene.bcgaScript = bpy.props.StringProperty(
		name = "Script",
		description = "Path to a BCGA script",
	)
	bpy.types.Scene.bakingBcgaScript = bpy.props.StringProperty(
		name = "Low poly script",
		description = "Path to a BCGA script with a low poly model",
	)


def unregister():
	del bpy.types.Scene.bakingBcgaScript
	del bpy.types.Scene.bcgaScript
	_unregisterClasses()
