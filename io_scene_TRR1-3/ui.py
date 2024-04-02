import bpy
from . import addon_updater_ops, bin_parse, trm_import, trm_export, pose_ops, ops
from . import utils as trm_utils

def update_data_type(self, context, prop, data_type:str):
    """Update displayed values in TRM shader UI panel"""
    obj = context.active_object
    if obj and obj.material_slots:
        mat = obj.active_material
        shader_ntree = trm_utils.find_TRM_shader_ntree()
        if shader_ntree:
            shader_node = trm_utils.find_TRM_shader_node(mat)
            if shader_node:
                data_path = self.path_from_id().split('.')[-1]
                if data_path == 'trm_settings' and prop == 'type':
                    val = int(getattr(mat.trm_settings, prop))
                    if val == -1:
                        return
                    input = shader_node.inputs.get(data_type)
                    input.default_value = val
                    trm_utils.set_mat_TRM_settings(mat, mesh=obj.data, shader_node=shader_node, update_shadertype=False)
                else:
                    data = getattr(mat.trm_settings, data_path)
                    data_name = mat.trm_settings.bl_rna.properties[data_path].name
                
                    val = getattr(data, prop)
                    if data_type == 'mat':
                        if val:
                            val = obj.data.materials.find(val.name)+1
                        else:
                            val = obj.data.materials.find(mat.name)+1
                        data_type = 'float'
                    val = trm_utils.convert_val_to_vector4(val, data_type)
                
                    input = shader_node.inputs.get(data_name)
                    input.default_value = val

class TR123R_PG_ShaderDataPropTypes(bpy.types.PropertyGroup):
    data_type: bpy.props.StringProperty(name="type", default='int')

    def poll_get_material(self, mat):
        obj = bpy.context.active_object
        if obj and obj.type == 'MESH':
            return mat.name in obj.data.materials and obj.active_material != mat

    data_mat: bpy.props.PointerProperty(type=bpy.types.Material, name="Cubemap", poll=poll_get_material,
                                        update=lambda s,c: update_data_type(s,c, 'data_mat', 'mat'))

    data_int: bpy.props.IntProperty(name="Integer", default=0, min=0, max=255,
                                    update=lambda s,c: update_data_type(s,c, 'data_int', 'int'))
    data_float: bpy.props.FloatProperty(name="Float", default=0, min=0.0, max=10.0, soft_max=1.0, precision=7, step=3,
                                        update=lambda s,c: update_data_type(s,c, 'data_float', 'float'))
    data_color: bpy.props.FloatVectorProperty(name="Color (RGBA)",
                                               default=(0,0,0,0),
                                               subtype='COLOR',
                                               min=0.0,
                                               max=1.0,
                                               size=4,
                                               update=lambda s,c: update_data_type(s,c, 'data_color', 'color'))
    data_bool: bpy.props.BoolProperty(name="Boolean", default=0,
                                      update=lambda s,c: update_data_type(s,c, 'data_bool', 'bool'))


class TR123R_PG_ShaderSettings(bpy.types.PropertyGroup):
    type: bpy.props.EnumProperty(
        name=trm_utils.SHADER_DATA_NAMES[0],
        items=(
            ('0', 'Standard', "Standard diffuse shader without additional effects"),
            ('2', 'Unknown2', "???"),
            ('3', 'Glossy', "???"),
            ('6', 'Unknown16', "???"),
            ('12', 'Unknown12', "???"),
            ('14', 'Unknown14', "???"),
            ('18', 'Unknown18', "???"),
            ('19', 'Unknown19', "???"),
            ('-1', 'Other', "Custom value for experimenting")
        ),
        default='0',
        update=lambda s,c: update_data_type(s,c, 'type', trm_utils.SHADER_DATA_NAMES[0])
    )

    data1: bpy.props.PointerProperty(
        type=TR123R_PG_ShaderDataPropTypes,
        name=trm_utils.SHADER_DATA_NAMES[1],
    )

    data2: bpy.props.PointerProperty(
        type=TR123R_PG_ShaderDataPropTypes,
        name=trm_utils.SHADER_DATA_NAMES[2],
    )

    data3: bpy.props.PointerProperty(
        type=TR123R_PG_ShaderDataPropTypes,
        name=trm_utils.SHADER_DATA_NAMES[3],
    )

    data4: bpy.props.PointerProperty(
        type=TR123R_PG_ShaderDataPropTypes,
        name=trm_utils.SHADER_DATA_NAMES[4],
    )


# Generic classes don't get registered in blender's environment
class TRM_PT_ShaderSettings:
    bl_label = "TRM Shader Settings"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "material"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj and obj.type == 'MESH' and obj.active_material
    
    def draw_TRM_error(self, layout: bpy.types.UILayout):
        layout.alert = True
        layout.label(text="Material has no TRM Shader")

    def draw(self, context):
        layout: bpy.types.UILayout = self.layout
        layout.use_property_decorate = False
        layout.use_property_split = True
        col = layout.column(align=False)
        
        obj = context.active_object
        mat = obj.active_material
        shadernode = trm_utils.find_TRM_shader_ntree()
        if shadernode:
            inst_node = trm_utils.find_TRM_shader_node(mat)
            if inst_node:
                op = col.operator(ops.TR123R_OT_CreateShader.bl_idname, text="Swap Shader Instance")
                op.new_instance = False
                op = col.operator(ops.TR123R_OT_CreateShader.bl_idname, text="Create New Shader Instance")
                op.new_instance = True

                # draw Shader Type enum and value preview
                row = col.row()
                row.prop(mat.trm_settings, 'type')
                row = row.row()
                row.prop(inst_node.inputs[0], 'default_value', text="Index:")
                # direct access to value if chosen Shader Type is "Other"
                if int(mat.trm_settings.type) != -1:
                    row.enabled = False

                # TODO: make some actual framework to draw different types based on Shader Type
                if int(mat.trm_settings.type) == 3:
                    col.prop(mat.trm_settings.data1, 'data_mat')
                else:
                    col.prop(mat.trm_settings.data1, 'data_color', text=trm_utils.SHADER_DATA_NAMES[1])
                col.prop(mat.trm_settings.data2, 'data_color', text=trm_utils.SHADER_DATA_NAMES[2])
                if int(mat.trm_settings.type) == 3:
                    col.prop(mat.trm_settings.data3, 'data_float', text="Roughness")
                else:
                    col.prop(mat.trm_settings.data3, 'data_color', text=trm_utils.SHADER_DATA_NAMES[3])
                col.prop(mat.trm_settings.data4, 'data_color', text=trm_utils.SHADER_DATA_NAMES[4])

            else:
                self.draw_TRM_error(col)
                col = layout.column(align=False)
                op = col.operator(ops.TR123R_OT_CreateShader.bl_idname, text="Add Existing Shader Instance")
                op.new_instance = False
                op = col.operator(ops.TR123R_OT_CreateShader.bl_idname, text="Create New Shader Instance")
                op.new_instance = True
        else:
            self.draw_TRM_error(col)
            col = layout.column(align=False)
            col.operator(ops.TR123R_OT_CreateShader.bl_idname)

        addon_updater_ops.update_notice_box_ui(self, context)

class TR123R_PT_ShaderSettings_Cycles(bpy.types.Panel, TRM_PT_ShaderSettings):
    bl_parent_id = "CYCLES_MATERIAL_PT_surface"

class TR123R_PT_ShaderSettings_Eevee(bpy.types.Panel, TRM_PT_ShaderSettings):
    bl_parent_id = "EEVEE_MATERIAL_PT_surface"

class TR123R_MT_ImportMenu(bpy.types.Menu):
    bl_idname = 'TR123R_MT_import'
    bl_label = "Tomb Raider I-III Remastered"

    def draw(self, context):
        layout = self.layout
        layout.operator(trm_import.TR123R_OT_ImportTRM.bl_idname, text=f"TR123R Model ({bin_parse.TRM_FORMAT})")

class TR123R_MT_ExportMenu(bpy.types.Menu):
    bl_idname = 'TR123R_MT_export'
    bl_label = "Tomb Raider I-III Remastered"

    def draw(self, context):
        layout = self.layout
        layout.operator(trm_export.TR123R_OT_ExportTRM.bl_idname, text=f"TR123R Model ({bin_parse.TRM_FORMAT})")
        
class TR123R_PT_UvTools(bpy.types.Panel):
    bl_label = "TR123R Tools"
    bl_space_type = "IMAGE_EDITOR"
    bl_region_type = "UI"
    bl_category = "Tool"

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH'

    def draw(self, context):
        layout = self.layout
        layout.label(text=ops.TR123R_OT_UV_QuantizeVerts.bl_label)
        col = layout.column()
        row = col.row(align=True)
        op = row.operator(ops.TR123R_OT_UV_QuantizeVerts.bl_idname, text="Selection")
        op.only_selected = True
        op = row.operator(ops.TR123R_OT_UV_QuantizeVerts.bl_idname, text="All")
        op.only_selected = False

        addon_updater_ops.update_notice_box_ui(self, context)

class TR123R_PT_PoseTools(bpy.types.Panel):
    bl_label = "TR123R Tools"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Tool"

    @classmethod
    def poll(cls, context):
        obj = bpy.context.active_object
        return obj and obj.type == 'ARMATURE'

    def draw(self, context):     
        layout = self.layout
        box = layout.box()
        col = box.column(align=True)
        col.label(text=pose_ops.TR123R_OT_LoadPose.bl_label)
        row = col.row()
        op = row.operator(pose_ops.TR123R_OT_LoadPose.bl_idname, text="Load Pose")
        op.load_all = False
        row = col.row()
        op = row.operator(pose_ops.TR123R_OT_LoadPose.bl_idname, text="Load All Poses")
        op.load_all = True

        col = box.column(align=True)
        col.label(text=pose_ops.TR123R_OT_SavePose.bl_label)
        row = col.row()
        op = row.operator(pose_ops.TR123R_OT_SavePose.bl_idname, text="Save Current Pose")
        op.save_many = False
        row = col.row()
        op = row.operator(pose_ops.TR123R_OT_SavePose.bl_idname, text="Save Multiple Poses")
        op.save_many = True

        col = box.column(align=True)
        col.label(text=pose_ops.TR123R_OT_PoseSwitchState.bl_label)
        row = col.row()
        op = row.operator(pose_ops.TR123R_OT_PoseSwitchState.bl_idname, text="Enable Poses")
        op.enable = True
        row = col.row()
        op = row.operator(pose_ops.TR123R_OT_PoseSwitchState.bl_idname, text="Disable Poses")
        op.enable = False

        addon_updater_ops.update_notice_box_ui(self, context)

cls =(
    TR123R_MT_ImportMenu,
    TR123R_MT_ExportMenu,
    TR123R_PG_ShaderDataPropTypes,
    TR123R_PG_ShaderSettings,
    TR123R_PT_ShaderSettings_Cycles,
    TR123R_PT_ShaderSettings_Eevee,
    TR123R_PT_UvTools,
    TR123R_PT_PoseTools,
)

_register, _unregister = bpy.utils.register_classes_factory(cls)

def menu_func_import(self, context):
    self.layout.menu(TR123R_MT_ImportMenu.bl_idname, text=f"Tomb Raider I-III Remastered")

def menu_func_export(self, context):
    self.layout.menu(TR123R_MT_ExportMenu.bl_idname, text=f"Tomb Raider I-III Remastered")

def register():
    _register()
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)
    bpy.types.Material.trm_settings = bpy.props.PointerProperty(type=TR123R_PG_ShaderSettings)

def unregister():
    del bpy.types.Material.trm_settings
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)
    _unregister()