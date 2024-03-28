import bpy, bmesh, os, pathlib
from . import utils as trm_utils
from . import pdp_utils

class TRM_OT_CreateShader(bpy.types.Operator):
    bl_idname = "io_tombraider123r.create_shader"
    bl_label = "Create TRM Shader"
    bl_description = "Add TRM Main Shader and Shader Instance to this material"
    bl_options = {'UNDO'}

    node_tree_name: bpy.props.StringProperty(
        name="ShaderGroup",
        default=""
    )

    new_instance: bpy.props.BoolProperty(
        name = "",
        default = True,
    )

    use_instance: bpy.props.EnumProperty(
        items=(
            ('ADD', "Add Existing", "Add instance existing in this blend project"),
            ('CREATE', "Create new Instance", "Create a new instance to be defined as a custom shader"),
            ('SWAP', "Swap with another", "Swap existing shader instance with another that exists"),
        ),
        default='CREATE'
    )

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj and obj.type == 'MESH' and obj.active_material

    def execute(self, context):
        if "TRM Master Shader" in self.node_tree_name:
            self.report({'ERROR'}, "Usage of TRM Master Shader is not supported, use Shader Instances.")
            return {'CANCELLED'}
        
        obj = context.active_object
        mat = obj.active_material
        trm_shader_ntree = trm_utils.get_TRM_shader_ntree()

        mat.use_nodes = True
        nodes = mat.node_tree.nodes

        # create or get node tree
        if self.new_instance:
            trm_shader_inst_ntree = trm_utils.create_TRM_shader_inst_ntree(trm_shader_ntree, obj.name, sh_id=-1)
        else:
            trm_shader_inst_ntree = trm_utils.get_TRM_shader_inst_ntree(trm_shader_ntree, self.node_tree_name, is_fullname=True)

        # set up node in material
        sh_ID = trm_shader_inst_ntree.name.rsplit(' ',1)[-1]
        trm_shader_inst_node = trm_utils.find_TRM_shader_inst_node(mat)
        if trm_shader_inst_node:
            trm_shader_inst_node.node_tree = trm_shader_inst_ntree
            # replace instance number on the label with one from nodetree
            trm_shader_inst_node.label = f"{trm_shader_inst_node.label.rsplit(' ',1)[0]} {sh_ID}"
        else:
            trm_shader_inst_node = trm_utils.create_TRM_shader_inst_node(nodes, trm_shader_inst_ntree)

        # set up Shader ID in the material name
        mat_name_slice = mat.name.split('_',2)
        if len(mat_name_slice) > 1:
            if trm_utils.str_to_int(mat_name_slice[1]) == None:
                # move the suffix to the end of the slice
                mat_name_slice.append(mat_name_slice[1])

            mat_name_slice[1] = sh_ID
            mat.name = "_".join(mat_name_slice)
        else:
            mat.name += f'_{sh_ID}'

        trm_utils.set_mat_TRM_settings(mat, trm_shader_inst_node, obj.data)

        mat_out = trm_utils.get_material_output(nodes)
        trm_utils.connect_nodes(mat.node_tree, mat_out, 0, trm_shader_inst_node, 0)
            
        return {"FINISHED"}
    
    def invoke(self, context, event):
        if not self.new_instance:
            return context.window_manager.invoke_props_dialog(self)
        else:
            return self.execute(context)
        
    def draw(self, context):
        layout = self.layout
        col = layout.column()
        row = col.row()
        row.label(text="Choose existing instance")
        row = col.row()
        row.prop_search(self, 'node_tree_name', bpy.data, 'node_groups', text="")
        if "TRM Master Shader" in self.node_tree_name:
            row = col.row()
            row.alert = True
            row.label(text="Do not use the Master Shader!")
            row = col.row()
            row.label(text="Use one of Shader Instances instead!")
    
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
                if not self.only_selected or self.only_selected and uv.select:
                    uv.uv = (self.float_to_float8(uv_co[0]), self.float_to_float8(uv_co[1]))
        
        bmesh.update_edit_mesh(mesh, destructive=False, loop_triangles=False)
        return {"FINISHED"}

class TRM_OT_GenerateSkeletonData(bpy.types.Operator):
    bl_idname = "io_tombraider123r.generate_skeleton_data"
    bl_label = "Generate Skeleton Data"
    bl_description = "Generates Bone data inside addon's directory, for each model in the game based on .PHD files from DATA folders.\nRequires Game Directory to be provided."

    op_result = None
    op_result_msg = []

    @classmethod
    def poll(cls, context):
        prefs = context.preferences.addons[__package__].preferences
        if 'game_path' in prefs:
            return os.path.exists(prefs.game_path)

    def execute(self, context):
        # Skip another execution on popup's 'OK' button
        if self.op_result != None:
            return self.op_result
        
        prefs = context.preferences.addons[__package__].preferences
        game_path = prefs.game_path

        # Loop through game folders in game directory and check for any existence of .PDP files
        path_valid = False
        for i in range(1,4):
            gamedata_path = pathlib.Path(game_path).joinpath(f'{i}/DATA')
            if any([True for x in pathlib.Path.glob(gamedata_path, '*.PDP')]):
                path_valid = True
                break

        if not path_valid:
            self.op_result = {'CANCELLED'}
            self.op_result_msg = ["Wrong Game Directory!", "Couldn't find .PDP files in DATA folders."]
            return self.op_result
        
        pdp_utils.xml_write_skeleton(game_path)

        self.op_result = {"FINISHED"}
        self.op_result_msg = ["Success!", "Skeleton Data generated successfully.", "TRMs can create armatures now.", "NOTE: WIP - for now only Lara meshes are supported!"]
        return self.op_result

    
    def invoke(self, context, event):
        # Execute script, dialog box acts only as a message box for results
        # Hitting OK should skip another execution via operator result stored in var
        self.execute(context)
        return context.window_manager.invoke_props_dialog(self)
    
    def draw(self, context):
        layout = self.layout
        flow = layout.grid_flow()
        col = flow.column_flow()
        
        res_icon = "CANCEL" if 'CANCELLED' in self.op_result else "INFO"
        row = col.row()
        row.label(text=self.op_result_msg[0], icon=res_icon)
        for line in self.op_result_msg[1:]:
            row = col.row()
            row.label(text=line)
    
cls = (
    TRM_OT_CreateShader,
    TRM_OT_UV_QuantizeVerts,
    TRM_OT_GenerateSkeletonData
)
_register, _unregister = bpy.utils.register_classes_factory(cls)