bl_info = {
    "name" : "TRM Format (Tomb Raider I-III Remastered)",
    "author" : "MuruCoder, MaRaider, Czarpos",
    "description" : "Import/Export tool for .TRM files for Tomb Raider Remastered I-III games.",
    "blender" : (4, 0, 0),
    "version" : (0, 6, 3),
    "category": "Import-Export",
	"location": "File > Import/Export",
    "warning" : "Game uses DDS textures, must be handled separately.",
    "doc_url": "https://www.tombraiderforums.com/showthread.php?t=228896",
    "tracker_url": "https://www.tombraiderforums.com/showthread.php?t=228896"
}

# Reload previously loaded modules
if "bpy" in locals():
    from importlib import reload
    if "utils" in locals():
        reload(utils)
    if "trm_parse" in locals():
        reload(trm_parse)
    if "trm_import" in locals():
        reload(trm_import)
    if "trm_export" in locals():
        reload(trm_export)
    if "ops" in locals():
        reload(ops)
    del reload

from . import utils
from . import trm_parse, trm_import, trm_export, ops
import bpy, os

class TRM_PT_Preferences(bpy.types.AddonPreferences):
    bl_idname = __package__

    def make_paths_abs(self, context, key):
        """ Prevent Blender's relative paths of doom """

        prefs = context.preferences.addons[__package__].preferences
        sane_path = lambda p: os.path.abspath(bpy.path.abspath(p))

        if key in prefs and prefs[key].startswith('//'):
            prefs[key] = sane_path(prefs[key])

    dds_tool_filepath: bpy.props.StringProperty(
        name="DDS Converter Path",
        description='Path to "texconv.exe" file"',
        subtype='FILE_PATH',
        update=lambda s,c: s.make_paths_abs(c, 'dds_tool_filepath'),
        default="texconv.exe"
    )

    tex_conv_directory: bpy.props.StringProperty(
        name="Converted PNG Directory",
        description='Directory to save converted PNG textures to.\n'
                    'Leave empty to save in TEX/PNGs folder in game directory',
        subtype='DIR_PATH',
        update=lambda s,c: s.make_paths_abs(c, 'tex_conv_directory'),
        default=""
    )

    game_path: bpy.props.StringProperty(
        name="Game Directory Path",
        description='Tomb Raider I-III Remastered game main directory.\n'
                    'Used to find texture files related to imported model.\n'
                    'Leave empty to automatically look for textures relative to directory the TRM is in',
        subtype='DIR_PATH',
        update=lambda s,c: s.make_paths_abs(c, 'game_path'),
        default=""
    )

    def draw(self, context):
        layout = bpy.types.UILayout(self.layout)
        col = layout.column()

        col.prop(self, 'dds_tool_filepath')
        col.prop(self, 'tex_conv_directory')
        col.prop(self, 'game_path')

        col.separator()
        row = col.row()
        row.label(text='Download "texconv.exe" file from:')
        op = row.operator('wm.url_open', text=" Microsoft's GitHub Releases")
        op.url = "https://github.com/microsoft/DirectXTex/releases"

def update_data_type(self, context, prop, data_type:str):
    """Update displayed values in TRM shader UI panel"""
    obj = context.active_object
    if obj and obj.material_slots:
        mat = obj.active_material
        shader_ntree = utils.find_TRM_shader_ntree()
        if shader_ntree:
            shader_node = utils.find_TRM_shader_node(mat)
            if shader_node:
                data_path = self.path_from_id().split('.')[-1]
                if data_path == 'trm_settings' and prop == 'type':
                    val = int(getattr(mat.trm_settings, prop))
                    if val == -1:
                        return
                    input = shader_node.inputs.get(data_type)
                    input.default_value = val
                    utils.set_mat_TRM_settings(mat, mesh=obj.data, shader_node=shader_node, update_shadertype=False)
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
                    val = utils.convert_val_to_vector4(val, data_type)
                
                    input = shader_node.inputs.get(data_name)
                    input.default_value = val

class TRM_PG_ShaderDataPropTypes(bpy.types.PropertyGroup):
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


class TRM_PG_ShaderSettings(bpy.types.PropertyGroup):
    type: bpy.props.EnumProperty(
        name=utils.SHADER_DATA_NAMES[0],
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
        update=lambda s,c: update_data_type(s,c, 'type', utils.SHADER_DATA_NAMES[0])
    )

    data1: bpy.props.PointerProperty(
        type=TRM_PG_ShaderDataPropTypes,
        name=utils.SHADER_DATA_NAMES[1],
    )

    data2: bpy.props.PointerProperty(
        type=TRM_PG_ShaderDataPropTypes,
        name=utils.SHADER_DATA_NAMES[2],
    )

    data3: bpy.props.PointerProperty(
        type=TRM_PG_ShaderDataPropTypes,
        name=utils.SHADER_DATA_NAMES[3],
    )

    data4: bpy.props.PointerProperty(
        type=TRM_PG_ShaderDataPropTypes,
        name=utils.SHADER_DATA_NAMES[4],
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
        shadernode = utils.find_TRM_shader_ntree()
        if shadernode:
            inst_node = utils.find_TRM_shader_node(mat)
            if inst_node:
                op = col.operator(ops.TRM_OT_CreateShader.bl_idname, text="Swap Shader Instance")
                op.new_instance = False
                op = col.operator(ops.TRM_OT_CreateShader.bl_idname, text="Create New Shader Instance")
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
                    col.prop(mat.trm_settings.data1, 'data_color', text=utils.SHADER_DATA_NAMES[1])
                col.prop(mat.trm_settings.data2, 'data_color', text=utils.SHADER_DATA_NAMES[2])
                if int(mat.trm_settings.type) == 3:
                    col.prop(mat.trm_settings.data3, 'data_float', text="Roughness")
                else:
                    col.prop(mat.trm_settings.data3, 'data_color', text=utils.SHADER_DATA_NAMES[3])
                col.prop(mat.trm_settings.data4, 'data_color', text=utils.SHADER_DATA_NAMES[4])

            else:
                self.draw_TRM_error(col)
                col = layout.column(align=False)
                op = col.operator(ops.TRM_OT_CreateShader.bl_idname, text="Add Existing Shader Instance")
                op.new_instance = False
                op = col.operator(ops.TRM_OT_CreateShader.bl_idname, text="Create New Shader Instance")
                op.new_instance = True
        else:
            self.draw_TRM_error(col)
            col = layout.column(align=False)
            col.operator(ops.TRM_OT_CreateShader.bl_idname)

class TRM_PT_ShaderSettings_Cycles(bpy.types.Panel, TRM_PT_ShaderSettings):
    bl_parent_id = "CYCLES_MATERIAL_PT_surface"

class TRM_PT_ShaderSettings_Eevee(bpy.types.Panel, TRM_PT_ShaderSettings):
    bl_parent_id = "EEVEE_MATERIAL_PT_surface"

class TRM_PT_UvTools(bpy.types.Panel):
    bl_label = "TRM Tools"
    bl_space_type = "IMAGE_EDITOR"
    bl_region_type = "UI"
    bl_category = "Tool"

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH'

    def draw(self, context):
        layout = self.layout
        layout.label(text=ops.TRM_OT_UV_QuantizeVerts.bl_label)
        col = layout.column()
        row = col.row(align=True)
        op = row.operator(ops.TRM_OT_UV_QuantizeVerts.bl_idname, text="Selection")
        op.only_selected = True
        op = row.operator(ops.TRM_OT_UV_QuantizeVerts.bl_idname, text="All")
        op.only_selected = False

cls =(
    TRM_PT_Preferences,
    TRM_PG_ShaderDataPropTypes,
    TRM_PG_ShaderSettings,
    TRM_PT_ShaderSettings_Cycles,
    TRM_PT_ShaderSettings_Eevee,
    TRM_PT_UvTools,
    ops.TRM_OT_CreateShader,
    ops.TRM_OT_UV_QuantizeVerts
)

_register, _unregister = bpy.utils.register_classes_factory(cls)

def register():
    _register()
    bpy.types.Material.trm_settings = bpy.props.PointerProperty(type=TRM_PG_ShaderSettings)
    trm_import.register()
    trm_export.register()

def unregister():
    trm_export.unregister()
    trm_import.unregister()
    del bpy.types.Material.trm_settings
    _unregister()

if __name__ == "__main__":
    register()
