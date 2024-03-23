bl_info = {
    "name" : "TRM Format (Tomb Raider I-III Remastered)",
    "author" : "MuruCoder, MaRaider, Czarpos",
    "description" : "Import/Export tool for .TRM files for Tomb Raider Remastered I-III games.",
    "blender" : (4, 0, 0),
    "version" : (0, 6, 0),
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
    if "trm_import" in locals():
        reload(trm_import)
    if "trm_export" in locals():
        reload(trm_export)
    if "ops" in locals():
        reload(ops)
    del reload

from .utils import find_TRM_shader, find_TRM_shader_inst
from . import trm_import, trm_export, ops
import bpy, os

def make_paths_abs(key):
    """ Prevent Blender's relative paths of doom """

    prefs = bpy.context.preferences.addons[__package__].preferences
    sane_path = lambda p: os.path.abspath(bpy.path.abspath(p))

    if key in prefs and prefs[key].startswith('//'):
        prefs[key] = sane_path(prefs[key])

class TRM_PT_Preferences(bpy.types.AddonPreferences):
    bl_idname = __package__

    dds_tool_filepath: bpy.props.StringProperty(
        name="DDS Converter Path",
        description='Path to "texconv.exe" file"',
        subtype='FILE_PATH',
        update=lambda s,c: make_paths_abs('dds_tool_filepath'),
        default="texconv.exe"
    )

    tex_conv_directory: bpy.props.StringProperty(
        name="Converted PNG Directory",
        description='Directory to save converted PNG textures to.\n'
                    'Leave empty to save in TEX/PNGs folder in game directory',
        subtype='DIR_PATH',
        update=lambda s,c: make_paths_abs('tex_conv_directory'),
        default=""
    )

    game_path: bpy.props.StringProperty(
        name="Game Directory Path",
        description='Tomb Raider I-III Remastered game main directory.\n'
                    'Used to find texture files related to imported model.\n'
                    'Leave empty to automatically look for textures relative to directory the TRM is in',
        subtype='DIR_PATH',
        update=lambda s,c: make_paths_abs('game_path'),
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

class TRM_PT_ShaderSettings(bpy.types.Panel):
    bl_label = "TRM Shader Settings"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "material"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        # result = self.get_main_shader(self, obj)
        return obj and obj.type == 'MESH' and obj.active_material
    
    def draw_TRM_error(self, layout: bpy.types.UILayout):
        layout.alert = True
        layout.label(text="Material has no TRM Shader")

    def draw(self, context):
        layout = self.layout
        layout.use_property_decorate = False
        layout.use_property_split = True
        col = layout.column(align=False)
        
        obj = context.active_object
        shadernode = find_TRM_shader()
        if shadernode:
            inst_node = find_TRM_shader_inst(obj.active_material)
            if inst_node:
                for input in inst_node.inputs:
                    if not input.links:
                        col.prop(input, 'default_value', text=input.name)
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
    TRM_PT_ShaderSettings,
    TRM_PT_UvTools,
    ops.TRM_OT_CreateShader,
    ops.TRM_OT_UV_QuantizeVerts
)

_register, _unregister = bpy.utils.register_classes_factory(cls)

def register():
    _register()
    trm_import.register()
    trm_export.register()

def unregister():
    trm_export.unregister()
    trm_import.unregister()
    _unregister()

if __name__ == "__main__":
    register()
