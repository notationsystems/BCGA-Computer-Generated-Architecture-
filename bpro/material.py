import bpy

from pro import context


class MaterialManager:

    def __init__(self):
        # a dict materialName->materialIndex, where materialIndex is the material index for the active Blender object
        self.reg = {}
        # Every engine Blender still ships builds materials out of shader nodes,
        # and the EEVEE identifier has changed more than once ("BLENDER_EEVEE" in
        # 2.80-4.1, "BLENDER_EEVEE_NEXT" in 4.2-4.5, "BLENDER_EEVEE" again from
        # 5.0), so dispatch on a default instead of enumerating engine names.
        self.render = NodeRender()

    def getMaterial(self, name):
        """
        Returns Blender material for the specified name or None if the material doesn't exist
        for the given name
        """
        material = None
        reg = self.reg
        objectMaterials = bpy.context.object.data.materials
        allMaterials = bpy.data.materials
        if name in reg:
            # we have already met that material before
            materialIndex = reg[name]
            material = objectMaterials[materialIndex]
        elif name in objectMaterials:
            # The material was set for the active Blender object before
            # the current rule set had been applied to it
            material = objectMaterials[name]
            # find materialIndex
            for materialIndex in range(len(objectMaterials)):
                if objectMaterials[materialIndex] == material:
                    break
            reg[name] = materialIndex
        elif name in allMaterials:
            # The material is already available, but not yet used by the active Blender object
            material = allMaterials[name]
            self.setMaterial(name, material)
        return material

    def setMaterial(self, name, material):
        """
        Appends the material to the active Blender object and register it with self.reg
        """
        objectMaterials = bpy.context.object.data.materials
        materialIndex = len(objectMaterials)
        objectMaterials.append(material)
        self.reg[name] = materialIndex

    def getMaterialIndex(self, name):
        if not name in self.reg:
            self.getMaterial(name)
        return self.reg[name]

    def createMaterial(self, name, textures):
        """
        Creates a new material and calls self.setMaterial(...)
        """
        try:
            material = self.render.createMaterial(name, textures)
        except RuntimeError:
            # a texture file that cannot be loaded must not abort the whole build
            material = None
        else:
            self.setMaterial(name, material)
        return material

    def setPreviewTexture(self, shape, materialIndex):
        # a slot for the texture
        materials = bpy.context.object.data.materials
        if len(materials) == 0:
            return
        # slot = materials[materialIndex].texture_slots[0]
        # if slot:
        #     shape.face[context.bm.faces.layers.tex.active].image = slot.texture.image


class NodeRender:
    """Builds a shader-node material, as used by both Cycles and EEVEE"""

    def createMaterial(self, name, textures):
        texture = textures[0]
        material = bpy.data.materials.new(name)
        material.use_nodes = True
        nodes = material.node_tree
        links = nodes.links
        nodes = nodes.nodes
        # The default node tree holds a shader and an output node, but their order
        # is not guaranteed (the shader is nodes[0] on 4.x), so follow the link
        # into the material output rather than indexing the collection blindly.
        shader = None
        output = next((n for n in nodes if n.bl_idname == "ShaderNodeOutputMaterial"), None)
        if output and output.inputs["Surface"].links:
            shader = output.inputs["Surface"].links[0].from_node
        if shader is None:
            shader = next((n for n in nodes if n.bl_idname != "ShaderNodeOutputMaterial"), None)
        if shader is None:
            raise RuntimeError("The new material '%s' has no shader node" % name)

        # create ShaderNodeTexImage
        textureNode = nodes.new("ShaderNodeTexImage")
        textureNode.image = bpy.data.images.load(texture.path)
        textureNode.location = -200, 300
        # connect textureNode and the shader (inputs[0] is Base Color on the
        # Principled BSDF, Color on the older Diffuse BSDF)
        links.new(textureNode.outputs[0], shader.inputs[0])

        # create ShaderNodeUVMap
        uvNode = nodes.new("ShaderNodeUVMap")
        uvNode.uv_map = texture.layer
        uvNode.location = -400, 300
        # connect uvNode and textureNode
        links.new(uvNode.outputs[0], textureNode.inputs[0])

        return material
