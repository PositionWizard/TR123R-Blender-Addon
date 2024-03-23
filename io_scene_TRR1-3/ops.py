import bpy, bmesh
from .utils import get_TRM_shader, get_TRM_shader_inst, create_TRM_shader_inst, create_TRM_shader_inst_nodegroup

class TRM_OT_CreateShader(bpy.types.Operator):
    bl_idname = "io_tombraider123r.create_shader"
    bl_label = "Create TRM Shader"
    bl_description = "Add TRM Main Shader and Shader Instance to this material"
    bl_options = {'UNDO'}

    new_instance: bpy.props.BoolProperty(
        name = "",
        default = True,
    )

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj and obj.type == 'MESH' and obj.active_material

    def execute(self, context):
        obj = context.active_object
        mat = obj.active_material
        trm_shader = get_TRM_shader()

        if self.new_instance:
            trm_shader_inst = create_TRM_shader_inst(trm_shader, f'{obj.name}: Shader Instance', sh_id=-1)
        else:
            trm_shader_inst = get_TRM_shader_inst(trm_shader, obj.name)

        mat.use_nodes = True
        nodes = mat.node_tree.nodes
        if trm_shader_inst.name not in nodes:
            create_TRM_shader_inst_nodegroup(nodes, trm_shader_inst)
            
        return {"FINISHED"}
    
class TRM_OT_UV_QuantizeVerts(bpy.types.Operator):
    bl_idname = "io_tombraider123r.quantize_uvs"
    bl_label = "Set UV precision to 8-bits"
    bl_description = "Quantize UV coordinates so they can fit in 8-bit of data (multiply by 255)"
    bl_options = {"UNDO"}

    only_selected: bpy.props.BoolProperty(
        name = "",
        default = False,
    )

    def float_to_float8(self, value):
        return round(value*255)/255

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj and obj.type == 'MESH' and context.mode == 'EDIT_MESH'

    def execute(self, context):
        obj = context.active_object
        mesh: bpy.types.Mesh = obj.data

        bm = bmesh.from_edit_mesh(mesh)
        uv_layer = bm.loops.layers.uv.verify()

        for f in bm.faces:
            for l in f.loops:
                uv = l[uv_layer]
                uv_co = l[uv_layer].uv
                if self.only_selected:
                    if uv.select:
                        uv.uv = (self.float_to_float8(uv_co[0]), self.float_to_float8(uv_co[1]))
                else:
                        uv.uv = (self.float_to_float8(uv_co[0]), self.float_to_float8(uv_co[1]))
        
        bmesh.update_edit_mesh(mesh, destructive=False, loop_triangles=False)
        return {"FINISHED"}

