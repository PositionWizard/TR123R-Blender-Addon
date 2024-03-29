import bpy, os
from mathutils import Vector, Euler, Matrix
from math import radians
from .utils import TRM_SCALE

POSE_ANGLE_SCALE = 1024

class TR123R_OT_LoadPose(bpy.types.Operator):
    bl_idname = "io_tombraider123r.pose_load"
    bl_label = "Load Photo Mode Pose"
    bl_description = "Loads a chosen Lara's pose to active Armature from POSE.txt.\nPath can be set in addon preferences"
    bl_options = {'UNDO'}

    addon_prefs: bpy.types.AddonPreferences = None
    pose_path_exists = False

    only_selected: bpy.props.BoolProperty(
        name = "",
        default = False,
    )

    is_custom_path: bpy.props.BoolProperty(
        name = "Use Explicit Path",
        description  = "Load POSE.txt from custom Photo Mode Poses filepath provided in addon prefernces.\n\n"
                        "Disale to load from Game Directory",
        default=False,
    )

    load_all: bpy.props.BoolProperty(
        name = "Load All as Animation",
        description  = "Import all Poses into an Action, each one on a different frame",
        default=False
    )

    pose_id: bpy.props.IntProperty(
        name = "Pose Number",
        description="Pose number in Photo Mode",
        default = 1,
        min = 1
    )

    @classmethod
    def poll(cls, context):
        obj = bpy.context.active_object
        return obj and obj.type == 'ARMATURE'
    
    def process_pose(self, rig, pose_data, frame):
        p_bones = rig.pose.bones

        # bone rotations
        angles = pose_data[3].split(', ')
        max_bones = min(len(angles), len(rig.data.bones))

        # key hips's location
        root_loc = Vector((int(pose_data[0])/-TRM_SCALE, int(pose_data[2])/-TRM_SCALE, int(pose_data[1])/-TRM_SCALE))
        root_mat = p_bones[0].bone.matrix_local.inverted() @ Matrix.Translation(root_loc)
        root_loc = root_mat.translation
        p_bones[0].location = root_loc
        p_bones[0].keyframe_insert(data_path="location", frame=frame)

        for f in range(0, max_bones):
            if angles[f].startswith('ZYX('):
                a = angles[f][4:-1].split(',')
                rot = []
                for axis in reversed(a):
                    v = POSE_ANGLE_SCALE - (int(axis.strip()) % POSE_ANGLE_SCALE)
                    v = (v / POSE_ANGLE_SCALE) * 360
                    rot.append(v)
                x,y,z = rot
            else:
                # TODO: INTEGER PROCESS LATER !!!
                x,y,z = [0]*3
            
            rot_order = 'YXZ'
            # Rotation order doesn't swap values between channels, it's just a gimbal definition
            # but it turns out 'YXZ' is the correct rotation order.
            # Y and Z values still need to be swapped according to the game's coordinate system.
            trm_rot_e = Euler((radians(x), radians(z), radians(y)), rot_order)
            
            arm_b = p_bones[f].bone
            # Create a posebone matrix rotated in armature-space
            # Bones are actually made up from objects with default orientations,
            # which means to get correct results, bones would either need to have their orientation
            # be the same as armature object iteslf or matrix transformation in armature's object space needs to be made on values
            mat =  arm_b.matrix_local.inverted() @ trm_rot_e.to_matrix().to_4x4() @ arm_b.matrix_local
            pb_rot_q = mat.decompose()[1]
            pb_rot_e = pb_rot_q.to_euler(rot_order)
            
            p_bones[f].rotation_mode = rot_order
            p_bones[f].rotation_euler = pb_rot_e
            
            p_bones[f].keyframe_insert(data_path="rotation_euler", frame=frame)
    
    def process_line(self, line):
        line = line.strip().upper()
        # get disabled poses
        if line.startswith('//') or line.startswith('\\'):
            line = line[2:].strip()

        l = line.split(',', 3)
        for i, data in enumerate(l):
            l[i] = data.strip()

        if len(l) < 3:
            print("\nIGNORING: ", line)
            return None
        else:
            return l
    
    def load_pose(self, filepath:str):
        rig = bpy.context.active_object
        bpy.context.scene.frame_start = 1
        if self.load_all:
            frame = 1
        else:
            frame = bpy.context.scene.frame_current

        lines = []
        with open(filepath, 'r') as f:
            for line in f:
                if self.load_all:
                    pose_data = self.process_line(line)
                    if pose_data is not None:
                        self.process_pose(rig, pose_data, frame)
                        frame += 1
                else:
                    lines.append(line)

            if not self.load_all:
                pose_data = self.process_line(lines[self.pose_id])
                if pose_data is not None:
                    self.process_pose(rig, pose_data, frame)

    def execute(self, context):
        if self.is_custom_path:
            pose_path = self.addon_prefs.pose_filepath
            if not self.pose_path_exists:
                self.report({'ERROR'}, f'Could not find "POSE.txt" file.\nWrong Photo Mode Poses path: "{self.addon_prefs.pose_filepath}"\nCheck your paths in addon preferences.')
                return {'CANCELLED'}
        else:
            pose_path = os.path.join(self.addon_prefs.game_path, '1/DATA/POSE.TXT')
            if not os.path.exists(pose_path):
                self.report({'ERROR'}, f'Could not find "POSE.txt" file.\n"{self.addon_prefs.game_path}" is not a Game Directory!\nCheck your paths in addon preferences.')
                return {'CANCELLED'}
            
        pose_path = os.path.abspath(pose_path)
        self.load_pose(pose_path)

        return {'FINISHED'}
    
    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False  # No animation.

        flow = layout.grid_flow()
        col = flow.column_flow()
        row = col.row()
        row.prop(self, 'is_custom_path')
        if not self.pose_path_exists:
            row.enabled = False

        row = col.row()
        row.prop(self, 'load_all')
        row = col.row()
        row.prop(self, 'pose_id')
        if self.load_all:
            row.enabled = False

    def invoke(self, context, event):
        self.addon_prefs = bpy.context.preferences.addons[__package__].preferences
        pose_path_ext = os.path.splitext(self.addon_prefs.pose_filepath)[1]
        self.pose_path_exists = os.path.exists(self.addon_prefs.pose_filepath) and pose_path_ext.casefold() == '.txt'
        if not self.pose_path_exists:
            self.is_custom_path = False

        return context.window_manager.invoke_props_dialog(self)


def register():
    bpy.utils.register_class(TR123R_OT_LoadPose)

def unregister():
    bpy.utils.unregister_class(TR123R_OT_LoadPose)