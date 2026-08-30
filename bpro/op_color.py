import bpy
import pro
from pro import context


def srgbToLinear(component):
    """
    Converts one sRGB component to linear.

    A rule set writes colours the way everyone writes colours, as sRGB hex,
    and pro.op_color hands them over in that space. Material.diffuse_color is
    linear, so assigning sRGB straight into it renders every colour too light
    -- #553322 arrives roughly three and a half times too bright.
    """
    if component <= 0.04045:
        return component / 12.92
    return ((component + 0.055) / 1.055) ** 2.4


class Color(pro.op_color.Color):
    def execute(self):
        materialManager = context.materialManager
        colorHex = self.colorHex
        material = materialManager.getMaterial(colorHex)
        if material:
            materialIndex = materialManager.getMaterialIndex(colorHex)
        else:
            material = bpy.data.materials.new(colorHex)
            material.diffuse_color = tuple(
                srgbToLinear(component) for component in self.color) + (1.0,)
            materialManager.setMaterial(colorHex, material)
            materialIndex = materialManager.getMaterialIndex(colorHex)
        # assign material to the bmesh face
        shape = context.getState().shape
        shape.clearUVlayers()
        shape.face.material_index = materialIndex
