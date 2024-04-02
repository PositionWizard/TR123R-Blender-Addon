import bpy, os
from mathutils import Vector, Euler, Matrix
from math import tau
from .utils import TRM_SCALE

POSE_ANGLE_SCALE = 1024
POSE_ROTATION_ORDER = 'YXZ'

class TR123R_OT_PoseHandler:
    addon_prefs: bpy.types.AddonPreferences = None
    pose_path_exists = False

    is_custom_path: bpy.props.BoolProperty(
        name = "Use Explicit Path",
        description  = "Use POSE.txt from custom Photo Mode Poses filepath provided in addon prefernces.\n\n"
                        "Disale to use one from Game Directory",
        default=False,
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
    
    def exec_pose(self, pose_path:str):
        return {'FINISHED'}

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
        result = self.exec_pose(pose_path)

        return result
    
    def draw_extra(self, context: bpy.types.Context, col:bpy.types.UILayout):
        pass
    
    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False  # No animation.

        flow = layout.grid_flow()
        col = flow.column_flow()
        row = col.row()
        row.prop(self, 'is_custom_path')
        row.enabled = self.pose_path_exists

        self.draw_extra(context, col)

    def invoke(self, context, event):
        self.addon_prefs = bpy.context.preferences.addons[__package__].preferences
        pose_path_ext = os.path.splitext(self.addon_prefs.pose_filepath)[1]
        self.pose_path_exists = os.path.exists(self.addon_prefs.pose_filepath) and pose_path_ext.casefold() == '.txt'
        if not self.pose_path_exists:
            self.is_custom_path = False

        return context.window_manager.invoke_props_dialog(self)

class TR123R_OT_LoadPose(bpy.types.Operator, TR123R_OT_PoseHandler):
    bl_idname = "io_tombraider123r.pose_load"
    bl_label = "Load Photo Mode Pose"
    bl_description = "Loads a chosen Lara's pose to active Armature from POSE.txt.\nPath can be set in addon preferences"
    bl_options = {'UNDO'}

    only_selected: bpy.props.BoolProperty(
        name = "Only Selected Bones",
        description = "Load Poses only to selected Pose Bones",
        default = False,
    )

    load_all: bpy.props.BoolProperty(
        name = "Load All as Animation",
        description  = "Import all Poses into an Action, each one on a different frame",
        default=False
    )

    ignore_disabled: bpy.props.BoolProperty(
        name = "Skip Disabled Poses",
        description  = "Ignores Poses that are present in the file but were disabled.\n\n"
                        "Disabling this option will always make Pose Number represent what's visible in the game",
        default=True
    )

    auto_key: bpy.props.BoolProperty(
        name = "Auto-Key",
        description  = "Automatically Insert Keyframes for imported pose into an active or a new Action",
        default=False
    )

    def process_pose(self, rig, pose_data, frame, add_keys):
        p_bones = rig.pose.bones
        sel_p_bones = bpy.context.selected_pose_bones_from_active_object

        # bone rotations
        angles = pose_data[3].split(', ')
        max_bones = min(len(angles), len(rig.data.bones))

        # key hips's location
        if not self.only_selected or (self.only_selected and p_bones[0] in sel_p_bones):
            root_loc = Vector((int(pose_data[0])/-TRM_SCALE, int(pose_data[2])/-TRM_SCALE, int(pose_data[1])/-TRM_SCALE))
            root_mat = p_bones[0].bone.matrix_local.inverted() @ Matrix.Translation(root_loc)
            root_loc = root_mat.translation
            p_bones[0].location = root_loc
            if add_keys:
                p_bones[0].keyframe_insert(data_path="location", frame=frame, group=p_bones[0].name)

        for f in range(0, max_bones):
            if self.only_selected and p_bones[f] not in sel_p_bones:
                continue
            if angles[f].startswith('ZYX('):
                a = angles[f][4:-1].split(',')
                rot = []
                for axis in reversed(a):
                    v = -int(axis.strip()) % POSE_ANGLE_SCALE
                    v = (v / POSE_ANGLE_SCALE) * tau
                    rot.append(v)
                x,y,z = rot
            else:
                # TODO: INTEGER PROCESS LATER !!!
                x,y,z = [0]*3
            
            # Rotation order doesn't swap values between channels, it's just a gimbal definition
            # but it turns out 'YXZ' is the correct rotation order.
            # Y and Z values still need to be swapped according to the game's coordinate system.
            trm_rot_e = Euler((x,z,y), POSE_ROTATION_ORDER)
            
            arm_b = p_bones[f].bone
            # Create a posebone matrix rotated in armature-space
            # Bones are actually made up from objects with default orientations,
            # which means to get correct results, bones would either need to have their orientation
            # be the same as armature object iteslf or matrix transformation in armature's object space needs to be made on values
            mat =  arm_b.matrix_local.inverted() @ trm_rot_e.to_matrix().to_4x4() @ arm_b.matrix_local
            pb_rot_e = mat.to_euler(POSE_ROTATION_ORDER)
            
            p_bones[f].rotation_mode = POSE_ROTATION_ORDER
            p_bones[f].rotation_euler = pb_rot_e
            
            if add_keys:
                p_bones[f].keyframe_insert(data_path="rotation_euler", frame=frame, group=p_bones[f].name)
    
    def process_line(self, line):
        line = line.strip().upper()
        # handle disabled poses
        if line.startswith('//') or line.startswith('\\'):
            if self.ignore_disabled:
                return None
            line = line[2:].strip()

        l = line.split(',', 3)
        for i, data in enumerate(l):
            l[i] = data.strip()

        # Ignore BEGIN and END tags
        if len(l) < 3:
            return None
        
        return l
    
    def load_pose(self, filepath:str):
        add_keys = self.load_all or (self.auto_key and not self.load_all)

        rig = bpy.context.active_object
        if add_keys:
            anim = rig.animation_data
            if not anim:
                anim = rig.animation_data_create()
            if not anim.action:
                action = bpy.data.actions.new('PhotoMode_Poses')
                rig.animation_data.action = action

        bpy.context.scene.frame_start = 1
        if self.load_all:
            frame = 1
        else:
            frame = bpy.context.scene.frame_current

        poses = []
        with open(filepath, 'r') as f:
            for line in f:
                pose_data = self.process_line(line)
                if pose_data is not None:
                    if self.load_all:
                        self.process_pose(rig, pose_data, frame, add_keys)
                        frame += 1
                    else:
                        poses.append(pose_data)

            # load single pose
            if not self.load_all:
                pose_count = len(poses)
                if self.pose_id > pose_count:
                    self.report({'ERROR'}, f'Pose Number: "{self.pose_id}" does not exist. Number of available Poses: "{pose_count}"')
                    return {'CANCELLED'}
                pose_data = poses[self.pose_id-1]
                self.process_pose(rig, pose_data, frame, add_keys)

        return {'FINISHED'}
    
    def draw_extra(self, context, col):
        row = col.row()
        row.prop(self, 'ignore_disabled')
        if not self.load_all:
            row = col.row()
            row.prop(self, 'pose_id')
            row = col.row()
            row.prop(self, 'auto_key')
        row = col.row()
        row.prop(self, 'only_selected')
        if context.mode != 'POSE':
            row.enabled = False

    exec_pose = load_pose

class TR123R_OT_SavePose(bpy.types.Operator, TR123R_OT_PoseHandler):
    bl_idname = "io_tombraider123r.pose_save"
    bl_label = "Save Photo Mode Pose"
    bl_description = "Saves current Pose or Action of active Armature to POSE.txt.\nPath can be set in addon preferences"

    save_many: bpy.props.BoolProperty(
        name = "Save from Action",
        description  = "Export Poses from current Action, replacing Poses by frame numbers that keyframes are on",
        default=False
    )

    add_new: bpy.props.BoolProperty(
        name = "Add Pose to Existing",
        description  = "Saves as a new Pose.\n\n"
                        "Disabling it will save by replacing the Pose on either a current frame number or a specified Pose Number option",
        default=True
    )

    def upd_start(self, context):
        if self.frame_end <= self.frame_start:
            self.frame_end = self.frame_start+1

    def upd_end(self, context):
        if self.frame_start >= self.frame_end:
            self.frame_start = self.frame_end-1

    frame_start: bpy.props.IntProperty(
            name="From:",
            description="Frame the first Pose is on",
            default=1,
            min=0,
            update=upd_start
            )

    frame_end: bpy.props.IntProperty(
            name="To:",
            description="Frame the last Pose is on",
            default=30,
            min=1,
            update=upd_end
            )
    
    def write_pose(self, filepath, poses:list):
        with open(filepath, 'r+') as f:
            f_data = f.readlines()
            f.seek(0)

            # filter out pose lines and tag them by 'enabled' sign
            pose_lines = []
            num_poses_enabled = 0
            for line in f_data:
                l = line.strip().upper()
                line_state = dict()
                line_state['data'] = l

                # Skip disabled lines
                if l.startswith('//') or l.startswith('\\'):
                    line_state['enabled'] = False
                    pose_lines.append(line_state)
                    continue

                l = l.split(',', 3)
                for str_i, substr in enumerate(l):
                    l[str_i] = substr.strip()

                # Skip BEGIN and END tags
                if len(l) < 3:
                    continue

                line_state['enabled'] = True
                num_poses_enabled += 1
                pose_lines.append(line_state)

            if not self.add_new and self.pose_id > num_poses_enabled:
                self.report({'ERROR'}, f'Pose Number: "{self.pose_id}" does not exist. Number of available Poses: "{num_poses_enabled}"')
                return {'CANCELLED'}
            
            f.write('BEGIN\n')
            pose_num = 1
            n = 0
            replaced_poses = 0
            while n < len(pose_lines):
                l = pose_lines[n]['data']

                # replace pose on the correct ID
                if pose_lines[n]['enabled'] and (pose_num == self.pose_id) and not self.add_new:
                    # replace a sequence of enabled poses starting at ID
                    if self.save_many:
                        # Loop through poses to save and advance in parallel
                        # the main pose list to replace enabled lines only
                        # and add ones at the end of file if went beyond original range
                        j = 0
                        while j < len(poses):
                            # write original disabled pose if found
                            # and wait for the enabled one or the list's end
                            if n < len(pose_lines) and not pose_lines[n]['enabled']:
                                f.write(pose_lines[n]['data']+'\n')
                            # write next pose and advance to next
                            else:
                                f.write(poses[j]+'\n')
                                replaced_poses+=1
                                j+=1
                            # advance main pose list
                            n+=1
                        # retreat main pose list to keep it on track with current line
                        n-=1
                        if n >= len(pose_lines):
                            break
                    # otherwise replace a single pose
                    else:
                        f.write(poses[0]+'\n')
                        replaced_poses+=1
                # otherwise write the original line
                else:
                    f.write(pose_lines[n]['data']+'\n')

                # skip disabled poses for proper indexing
                if not pose_lines[n]['enabled']:
                    n+=1
                    continue

                pose_num+=1
                n+=1

            # add new poses to the list's end
            if self.add_new:
                if self.save_many:
                    for p in poses:
                        f.write(p+'\n')
                else:
                    f.write(poses[0]+'\n')
            f.write('END')
            f.truncate()

            if self.add_new:
                self.report({'INFO'}, f'Successfully Added {len(poses)} Poses')
            else:
                if replaced_poses == 1:
                    self.report({'INFO'}, f'Successfully Replaced Pose "{self.pose_id}"')
                elif replaced_poses > 1:
                    frame_num = self.frame_end-self.frame_start
                    self.report({'INFO'}, f"Successfully Replaced {replaced_poses} Poses ({self.pose_id} to {self.pose_id+frame_num})")

    def process_pose(self, rig:bpy.types.Object):
        p_bones = rig.pose.bones
        root_loc = [str(round(v*-TRM_SCALE)) for v in p_bones[0].matrix.translation]
        root_loc = [root_loc[0], root_loc[2], root_loc[1]]
        
        bone_rots = []
        for pb in p_bones:
            if pb.bone.use_deform:
                mat = pb.bone.matrix_local @ pb.matrix_basis @ pb.bone.matrix_local.inverted()
                pb_rot_e = mat.to_euler(POSE_ROTATION_ORDER)
                # remap euler's radians range from [-π, π] to [0, 2π]
                rot = [r % tau for r in pb_rot_e]
                # remap rotations from [0, 2π] float range to [1024, 0] integer range
                for i in range(len(rot)):
                    val = rot[i]
                    val = round((val / tau) * POSE_ANGLE_SCALE)
                    rot[i] = -val % POSE_ANGLE_SCALE

                # axes get saved in ZYX order with Z and Y swapped
                bone_rots.append('ZYX(%d,%d,%d)' % (rot[1], rot[2], rot[0]))
                
        return ', '.join(root_loc + bone_rots)

    def save_pose(self, filepath):
        rig = bpy.context.active_object
        poses = []
        if self.save_many:
            sc = bpy.context.scene
            saved_frame = sc.frame_current
            for f in range(self.frame_start, self.frame_end+1):
                sc.frame_set(f)
                poses.append(self.process_pose(rig))
            sc.frame_set(saved_frame)
        else:
            poses.append(self.process_pose(rig))

        self.write_pose(filepath, poses)
        return {'FINISHED'}
    
    exec_pose = save_pose
    
    def draw_extra(self, context, col):
        row = col.row()
        row.prop(self, 'add_new')

        if self.save_many:
            row = col.row()
            rowsplit = row.split(factor = 0.4)
            rowsplit.alignment = 'RIGHT'
            rowsplit.label(text="From Frame Range:")
            props = rowsplit.split(factor=0.5, align=True)
            props.use_property_split = False
            props.prop(self, 'frame_start')
            props.prop(self, 'frame_end')

            pose_id_text="Replace at Pose"
        else:
            pose_id_text="Replace Pose"

        row = col.row()
        row.prop(self, 'pose_id', text=pose_id_text)
        row.enabled = not self.add_new

class TR123R_OT_PoseSwitchState(bpy.types.Operator, TR123R_OT_PoseHandler):
    bl_idname = "io_tombraider123r.pose_switch_state"
    bl_label = "Photo Mode Poses State"
    bl_description = "Enable or Disable a Photo Mode Pose"

    enable: bpy.props.BoolProperty(
        name = "",
        default=True
    )

    switch_all: bpy.props.BoolProperty(
        name = "Switch All Poses",
        description  = "Enables or Disables all Poses in the file",
        default=True
    )

    def exec_pose(self, filepath):
        with open(filepath, 'r+') as f:
            f_data = f.readlines()
            f.seek(0)

            # filter out pose lines and tag them by 'enabled' sign
            poses = []
            num_poses = 0
            poses_enabled = []
            for line in f_data:
                l = line.strip().upper()

                l = l.split(',', 3)
                for str_i, substr in enumerate(l):
                    l[str_i] = substr.strip()

                # Skip BEGIN and END tags
                if len(l) < 3:
                    continue

                num_poses += 1

                if not (line.startswith('//') or line.startswith('\\')):
                    poses_enabled.append(num_poses)

                poses.append(line)

            if not self.switch_all and self.pose_id > num_poses:
                self.report({'ERROR'}, f'Pose Number: "{self.pose_id}" does not exist. Number of available Poses: "{num_poses}"')
                return {'CANCELLED'}
                
            f.write('BEGIN\n')
            num_switched_poses = 0
            pose_game_id = 1
            stop_count = False
            for i, line in enumerate(poses, 1):
                # handle disabled poses
                is_disabled = line.startswith('//') or line.startswith('\\')
                if self.switch_all or (not self.switch_all and i == self.pose_id):
                    if self.enable and is_disabled:
                        line = line[2:]
                        num_switched_poses+=1
                        stop_count = True
                    elif not self.enable and not is_disabled:
                        line = '//'+line
                        num_switched_poses+=1
                        stop_count = True
                    
                if not (stop_count or is_disabled):
                    pose_game_id += 1

                f.write(line)
            f.write('END')
            f.truncate()

            msg_state = "Enabled" if self.enable else "Disabled"
            if num_switched_poses > 0:
                smaller_existing = next(iter([i for i, p in enumerate(poses_enabled) if p > self.pose_id]), None)
                if self.switch_all:
                    self.report({'INFO'}, f"Successfully {msg_state} {num_switched_poses} Poses")
                elif smaller_existing and self.enable:
                    self.report({'INFO'}, f'Successfully {msg_state} Pose between Numbers "{smaller_existing}" and "{smaller_existing+1}"')
                else:
                    self.report({'INFO'}, f'Successfully {msg_state} Pose at Number "{pose_game_id}", Line "{self.pose_id}"')
            else:
                self.report({'WARNING'}, f"No Poses were {msg_state}")
        
        return {'FINISHED'}
    
    def draw_extra(self, context: bpy.types.Context, col:bpy.types.UILayout):
        row = col.row()
        row.prop(self, 'switch_all')
        row = col.row()
        row.prop(self, 'pose_id', text="Pose Line")
        row.enabled = not self.switch_all

cls = (
    TR123R_OT_LoadPose,
    TR123R_OT_SavePose,
    TR123R_OT_PoseSwitchState,
)

_register, _unregister = bpy.utils.register_classes_factory(cls)