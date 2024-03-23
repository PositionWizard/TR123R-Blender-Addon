bl_info = {
    "name" : "TRM Format (Tomb Raider I-III Remastered)",
    "author" : "MuruCoder, MaRaider, Czarpos",
    "description" : "Import/Export tool for .TRM files for Tomb Raider Remastered I-III games.",
    "blender" : (4, 0, 0),
    "version" : (0, 4, 1),
    "category": "Import-Export",
	"location": "File > Import/Export",
    "warning" : "Game uses DDS textures, must be handled separately.",
    "doc_url": "https://www.tombraiderforums.com/showthread.php?t=228896",
    "tracker_url": "https://www.tombraiderforums.com/showthread.php?t=228896"
}

if "bpy" in locals():
    from importlib import reload
    if "trm_import" in locals():
        reload(trm_import)
    if "trm_export" in locals():
        reload(trm_export)
    del reload

from . import trm_import, trm_export
import bpy, os

def make_paths_abs(key):
    """ Prevent Blender's relative paths of doom """

    prefs = bpy.context.preferences.addons[__package__].preferences
    sane_path = lambda p: os.path.abspath(bpy.path.abspath(p))

    if key in prefs and prefs[key].startswith('//'):
        prefs[key] = sane_path(prefs[key])

class PT_TRM_Preferences(bpy.types.AddonPreferences):
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


def register():
    bpy.utils.register_class(PT_TRM_Preferences)
    trm_import.register()
    trm_export.register()

def unregister():
    trm_export.unregister()
    trm_import.unregister()
    bpy.utils.unregister_class(PT_TRM_Preferences)

if __name__ == "__main__":
    register()
