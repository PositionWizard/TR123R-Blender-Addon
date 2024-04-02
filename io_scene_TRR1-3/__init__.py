bl_info = {
    "name" : "Tomb Raider I-III Remastered - Tools (.TRM, POSE.txt)",
    "author" : "MuruCoder, MaRaider, Czarpos",
    "description" : "Tools to handle .TRM and POSE.txt files for Tomb Raider Remastered I-III games.",
    "blender" : (4, 0, 0),
    "version" : (0, 6, 3),
    "category": "Import-Export",
	"location": "File > Import/Export; Material Properties > Surface; UV > N-Panel",
    "warning" : "Game uses DDS textures, must be handled separately.",
    "doc_url": "https://github.com/PositionWizard/TR123R-Blender-Addon",
    "tracker_url": "https://github.com/PositionWizard/TR123R-Blender-Addon/issues"
}

# Reload previously loaded modules
if "bpy" in locals():
    from importlib import reload
    if "addon_updater_ops" in locals():
        reload(addon_updater_ops)
    if "utils" in locals():
        reload(utils)
    if "pdp_utils" in locals():
        reload(pdp_utils)
    if "bin_parse" in locals():
        reload(bin_parse)
    if "trm_import" in locals():
        reload(trm_import)
    if "trm_export" in locals():
        reload(trm_export)
    if "pose_ops" in locals():
        reload(pose_ops)
    if "ops" in locals():
        reload(ops)
    if "ui" in locals():
        reload(ui)
    del reload

from . import addon_updater_ops, utils, pdp_utils, bin_parse, trm_import, trm_export, pose_ops, ops, ui
import bpy, os

@addon_updater_ops.make_annotations
class TR123R_PT_Preferences(bpy.types.AddonPreferences):
    bl_idname = __package__

    def make_paths_abs(self, context, key):
        """ Prevent Blender's relative paths of doom """

        prefs = context.preferences.addons[__package__].preferences
        sane_path = lambda p: os.path.abspath(bpy.path.abspath(p))

        if key in prefs and prefs[key].startswith('//'):
            prefs[key] = sane_path(prefs[key])

    dds_tool_filepath: bpy.props.StringProperty(
        name="DDS Converter",
        description='Path to "texconv.exe" file"',
        subtype='FILE_PATH',
        update=lambda s,c: s.make_paths_abs(c, 'dds_tool_filepath'),
        default="texconv.exe"
    )

    tex_conv_directory: bpy.props.StringProperty(
        name="Converted Directory",
        description='Directory to save converted PNG textures to.\n\n'
                    'Leave empty to save in TEX/PNGs folder in game directory',
        subtype='DIR_PATH',
        update=lambda s,c: s.make_paths_abs(c, 'tex_conv_directory'),
        default=""
    )

    game_path: bpy.props.StringProperty(
        name="Game Directory",
        description='Tomb Raider I-III Remastered game main directory.\n\n'
                    'Used to find texture files related to imported model.\n'
                    'Leave empty to automatically look for textures relatively to directory the TRM is in',
        subtype='DIR_PATH',
        update=lambda s,c: s.make_paths_abs(c, 'game_path'),
        default=""
    )

    pose_filepath: bpy.props.StringProperty(
        name="Photo Mode Poses",
        description='Tomb Raider I-III Remastered POSE.txt filepath for Lara photo mode poses.\n'
                    'File located in "[Game Directory]/1/DATA/POSE.txt"\n\n'
                    'Optional field for working outside of game files.\n'
                    'Path is necessary if Game Directory is not provided!!!\n'
                    'Leave empty to use POSE.txt based on Game Directory path.',
        subtype='FILE_PATH',
        update=lambda s,c: s.make_paths_abs(c, 'pose_filepath'),
        default="POSE.txt"
    )

    # --------------------- Addon updater preferences --------------------- #

    auto_check_update = bpy.props.BoolProperty(
		name="Auto-check for Update",
		description="If enabled, auto-check for updates using an interval",
		default=False)

    updater_interval_months = bpy.props.IntProperty(
		name='Months',
		description="Number of months between checking for updates",
		default=0,
		min=0)

    updater_interval_days = bpy.props.IntProperty(
		name='Days',
		description="Number of days between checking for updates",
		default=7,
		min=0,
		max=31)

    updater_interval_hours = bpy.props.IntProperty(
		name='Hours',
		description="Number of hours between checking for updates",
		default=0,
		min=0,
		max=23)

    updater_interval_minutes = bpy.props.IntProperty(
		name='Minutes',
		description="Number of minutes between checking for updates",
		default=0,
		min=0,
		max=59)

    # --------------------------------------------------------------------- #

    def draw(self, context):
        layout = bpy.types.UILayout(self.layout)
        col = layout.column()

        col.prop(self, 'dds_tool_filepath')
        col.prop(self, 'tex_conv_directory')
        col.prop(self, 'game_path')
        col.prop(self, 'pose_filepath')

        col.separator()

        row = col.row()
        row.label(text='Download DDS Converter (texconv.exe) from:')
        op = row.operator('wm.url_open', text="Microsoft's GitHub Releases")
        op.url = "https://github.com/microsoft/DirectXTex/releases"

        row = col.row()
        row.label(text='Generate Bone Data for TRMs:')
        row.operator('io_tombraider123r.generate_skeleton_data')

        col.separator()

        row = col.row()
        row.label(text='Join the discussion, contribute to community:')
        op = row.operator('wm.url_open', text='TombRaiderForums Thread')
        op.url = "https://www.tombraiderforums.com/showthread.php?t=228896"

        addon_updater_ops.update_settings_ui(self,context)

cls =(
    TR123R_PT_Preferences,
)

_register, _unregister = bpy.utils.register_classes_factory(cls)

def register():
    addon_updater_ops.register(bl_info)
    _register()
    trm_import.register()
    trm_export.register()
    pose_ops._register()
    ops._register()
    ui.register()

def unregister():
    ui.unregister()
    ops._unregister()
    pose_ops._unregister()
    trm_export.unregister()
    trm_import.unregister()
    _unregister()
    addon_updater_ops.unregister()

if __name__ == "__main__":
    register()
