import bpy, math, random, subprocess, time
from struct import unpack
from mathutils import Vector
import os.path as Path
from . import bin_parse
from . import utils as trm_utils
from .pdp_utils import SKELETON_DATA_FILEPATH
import xml.etree.ElementTree as ET

def create_vertex_groups(trm, joints, rig, bones, armature, filename):
    # possible vertex group names, 10 per line for easier counting
    vg_names = [
        "root", "hips", "stomach", "chest", "torso", "neck", "head", "jaw", "jaw_lower", "jaw_upper",
        "hip_L", "thigh_L", "thighB_L", "knee_L", "calf_L", "calfB_L", "ankle_L", "foot_L", "toe_L", "toes_L",
        "hip_R", "thigh_R", "thighB_R", "knee_R", "calf_R", "calfB_R", "ankle_R", "foot_R", "toe_R", "toes_R",
        "shoulder_L", "shoulderB_L", "arm_L", "armB_L", "elbow_L", "elbowB_L", "wrist_L", "hand_L", "thumb_L", "fingers_L",
        "shoulder_R", "shoulderB_R", "arm_R", "armB_R", "elbow_R", "elbowB_R", "wrist_R", "hand_R", "thumb_R", "fingers_R",
        "hair_root", "hair1", "hair2", "hair3", "hair4", "hair5", "hair6", "hair7", "hair8", "hair9",
        "EMPTY", "lip_pull_R",  "lip_pull_L", "lip_side_U_R", "lip_side_U_L", "lip_side_D_R", "lip_side_D_L", "lip_middle_U_R", "lip_middle_U_L", "lip_middle_D_R",
        "lip_middle_D_L", "eyelid_U_R", "eyelid_U_L", "eyelid_D_R", "eyelid_D_L", "brow_outer_R", "brow_outer_L", "brow_middle_R", "brow_middle_L", "brow_inner_R",
        "brow_inner_L", "eye_R", "eye_L", "cheek_R", "cheek_L", "tongue",
        # more to be added here
    ]

    # lists to get names by order
    vg_lists = {
        "Lara_Body": [1, 11, 14, 17, 21, 24, 27, 4, 42, 44, 47, 32, 34, 37, 6],
        "Lara_Hair": [50, 51, 52, 53, 54, 55],
        "Lara_Head": [1, 4, 6, 60, 85, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 7, 71, 72, 73, 74, 75, 76, 77, 78, 79, 80, 81, 82, 83, 84],
    }

    # map for list decision
    vg_names_map = {
        "_HAIR": 'Lara_Hair',
        "OUTFIT_": 'Lara_Body',
        "HOLSTER_": 'Lara_Body',
        "HAND_": 'Lara_Body',
        "_HEAD": "Lara_Head",
        "HEAD_": "Lara_Head",
    }

    # decide which list to use
    if armature == 'AUTO':
        for k in vg_names_map.keys():
            if k in filename:
                armature = vg_names_map[k]
                break

    gl = []
    if armature in vg_lists:
        gl = vg_lists[armature]

    len1 = len(gl)
    len2 = len(vg_names)
    skel_size = len(rig.pose.bones) if rig and bones else 0
    for n in range(joints):
        if n < len1 and gl[n] < len2:
            name = vg_names[gl[n]]
        else:
            name = "Joint" + str(n)
        trm.vertex_groups.new(name=name)
        if skel_size and n < skel_size:
            pb = rig.pose.bones[bones[n]]
            pb.name = name


from bpy_extras.io_utils import ImportHelper
from bpy.props import StringProperty, BoolProperty, EnumProperty, CollectionProperty, FloatProperty
from bpy.types import Operator
import os

class TR123R_OT_ImportTRM(Operator, ImportHelper):
    """Load object from TRM file"""
    bl_idname = "io_tombraider123r.trm_import"
    bl_label = "Import TRM"
    bl_options = {'UNDO'}

    filename_ext = f"{bin_parse.TRM_FORMAT}"

    ###########################################
    # necessary to support multi-file import
    files: CollectionProperty(
        type=bpy.types.OperatorFileListElement,
        options={'HIDDEN', 'SKIP_SAVE'},
    )

    directory: StringProperty(
        subtype='DIR_PATH',
    )
    ##########################################

    filter_glob: StringProperty(
        default=f"*{bin_parse.TRM_FORMAT}",
        options={'HIDDEN'},
        maxlen=255,
    )

    scale: FloatProperty(
        name="Scale",
        description="Scale vertices",
        default=0.01,
    )

    mesh_type: EnumProperty(
        name="Joint Naming",
        description="Vertex Groups naming",
        items=(
            ('AUTO', "AUTO", "Try to pick the best"),
            ('ID', "ID", "Internal joint IDs"),
            ('Lara_Body', "Lara Body", "Lara's body & outfits"),
            ('Lara_Hair', "Lara Hair", "Lara's hair"),
            ('Lara_Head', 'Lara Head', "Lara's head (only HEAD_IDLE)"),
        ),
        default='AUTO',
    )

    use_tex: BoolProperty(
        name="Use Textures",
        description="Convert DDS texture files to PNG, import and apply to mesh",
        default=False
    )

    tex_dir: EnumProperty(
        name="Game",
        description="Specify the game to look for the textures and armatures in.\n"
                    "This is only if game directory path is specified for ambiguous model paths",
        items=(
            ('1', "I", ""),
            ('2', "II", ""),
            ('3', "III", ""),
            ('REL', "Relative", "Relatively to the TRM file")
        ),
        default='1',
    )

    merge_uv: BoolProperty(
        name="Merge by UVs",
        description="Tries to weld non-manifold edges, resulting in mesh welding along UV seams.\n"
                    "Helps with shading and mesh editing",
        default=True
    )

    import_armature: BoolProperty(
        name="Import Armature",
        description="Creates Armatures for imported models.\n\n"
                    "Requires Skeleton Data to be Generated at least once. Happens automatically during a first import.\n"
                    "Valid Game Directory path needs to be provided in addon's preferences in order to generate the data",
        default=True
    )

    connect_bones: BoolProperty(
        name="Force Connect Bones",
        description="Try to connect parent bones to the children bones on imported Armatures.\n\n"
                    "May look weird with some things like breakable floor, glass, etc.\n"
                    "Disabling it will point all bones in the Armature object's direction\n"
                    "which is the original bone orientation for Tomb Raider skeletons.",
        default=True
    )

    auto_orient_bones: BoolProperty(
        name="Auto Bone Orientation",
        description="Try to automatically orient last bones in the chains\n"
                    "according to their parent's orientation",
        default=False
    )

    skip_texconv = False

    def load_png(self, mat: bpy.types.Material, path_png, nodes: bpy.types.Nodes):
        texture_node = nodes.new('ShaderNodeTexImage')
        texture_node.image = bpy.data.images.load(path_png)

        return texture_node

    def import_texture(self, addon_prefs, tex_name, folders: list[tuple[str, int]], mat: bpy.types.Material, nodes):
        tex_conv_path = addon_prefs.dds_tool_filepath
        png_export_path = addon_prefs.tex_conv_directory
        tex_node = None
        if not folders:
            return tex_node
        
        for folder, game_id in folders:
            png_filename = f"{tex_name}.png"
            if not png_export_path:
                path_png_dir = Path.join(folder, 'PNGs')
            else:
                # if texture is not in custom PNG main directory, look for it in custom directory's game ID folder
                if not Path.exists(Path.join(png_export_path, png_filename)):
                    path_png_dir = Path.join(png_export_path, str(game_id))
                else:
                    path_png_dir = png_export_path
            
            path_png = Path.join(path_png_dir, png_filename)
            path_dds = Path.join(folder, f"{tex_name}.dds")

            # Load the texture if PNG already exists
            if Path.exists(path_png):
                print(f"PNG located in: {path_png}")
                tex_node = self.load_png(mat, path_png, nodes)
                break
            elif self.skip_texconv:
                break
            # Convert DDS to PNG, if the DDS exists but not the PNG
            elif Path.exists(path_dds):
                print(f"DDS located in: {path_dds}")

                # Create PNGs folder into "Tombraider Remastered Trilogy\[1,2,3]\TEX\" or other directory specified in prefs
                if not Path.exists(path_png_dir):
                    print(f"{path_png_dir} does not exists, creating...")
                    os.makedirs(path_png_dir)
                        
                subprocess.run([tex_conv_path, path_dds, "-nologo", "-o", path_png_dir, "-ft", "png"])
                tex_node = self.load_png(mat, path_png, nodes)
                break
            else:
                self.report({'INFO'}, f"Texture '{tex_name}' not found in Game [{game_id}] folder!")

        if not tex_node:
            self.report({'WARNING'}, f"Couldn't get texture '{tex_name}'! skipping texture import...")

        return tex_node
    
    def get_tex(self, tex_name:str, mat:bpy.types.Material):
        texture_node = None
        tex = None

        if mat.use_nodes:        
            # look for shader nodes with the texture
            nodes = mat.node_tree.nodes
            for node in nodes:
                if node.type == 'TEX_IMAGE':
                    node: bpy.types.ShaderNodeTexImage
                    if node.image.name.startswith(tex_name) and Path.exists(node.image.filepath):
                        self.report({'INFO'}, f'Node with "{tex_name}" texture already exists, assigning...')
                        node.image.reload()
                        texture_node = node
                        tex = node.image
                        break

        if not texture_node:
            # look for the texture itself
            for tx in bpy.data.images:
                if tx.name.startswith(tex_name) and Path.exists(tx.filepath):
                    self.report({'INFO'}, f'Texture "{tex_name}" already exists, assigning...')
                    tex = tx
                    break

        return texture_node, tex

    def create_material(self, tex_name="", folders="", import_tex=False):
        # Check what game the texture is from to tag a material with it
        mat_suffix = ""
        if import_tex:
            for folder, game_id in folders:
                path_dds = Path.join(folder, f"{tex_name}.dds")
                if Path.exists(path_dds):
                    mat_suffix = "_Game-"+str(game_id)
                    break
                    
        mat_name = tex_name+mat_suffix

        for n in [mat_name, tex_name]:
            mat = bpy.data.materials.get(n)
            if mat:
                print(f'Material "{mat.name}" already exists, using the existing one for this model.') 
                return mat

        if not mat:
            mat = bpy.data.materials.new(name=mat_name)
            mat.diffuse_color = (random.random(), random.random(), random.random(), 1)
            
        return mat
    
    def define_shader(self, index: int, type_name: str, sh_ids: trm_utils.TRM_ShaderIndices, trm_mesh: bpy.types.Mesh, is_single, has_gameID):
        def copy_mat(tex_name, mat_suffix, mat: bpy.types.Material):
            # Don't tag and duplicate the material with shader name if
            # it's from the first range of indices
            mat_newname = tex_name
            if type_name == trm_utils.SHADER_SUBTYPES[0]:
                mat_newname += f'_{index}'
            else:
                mat_newname += f'_{index}_{type_name}'
            
            if mat_suffix:
                mat_newname += f'_{mat_suffix}'

            mat_basename = tex_name+f'_{mat_suffix}' if has_gameID else tex_name

            # swap imported material in the same slot, with correct one still in memory
            swap_mats = mat.name == mat_basename or mat.name == mat_newname
            if mat_newname in bpy.data.materials:
                if swap_mats:
                    prev_mat_id = trm_mesh.materials.find(mat.name)
                    bpy.data.materials.remove(mat)
                    mat = bpy.data.materials.get(mat_newname)
                    trm_mesh.materials[prev_mat_id] = mat
                else:
                    mat = bpy.data.materials.get(mat_newname)
                    trm_mesh.materials.append(mat)
            else:
                if not swap_mats:
                    mat = mat.copy()
                    trm_mesh.materials.append(mat)
                mat.name = mat_newname
            return mat
        
        poly_start = int(sh_ids.offset/3)
        poly_stop = int((sh_ids.offset+sh_ids.length)/3)
        added_mats = {}
        # Find polygons in the given shader indices range and either rename
        # or duplicate their exisitng materials, tagging them with shader index and subtype
        for p in trm_mesh.polygons[poly_start:poly_stop]:
            mat = trm_mesh.materials[p.material_index]
            mat_name_slice = mat.name.split('_',4)
            tex_name, mat_suffix = [mat_name_slice[0], mat_name_slice[-1] if len(mat_name_slice)>1 and has_gameID else ""]
            tex_sh = f'{tex_name}_{index}'
            # Save the operation in memory to avoid excess material duplication
            if tex_sh in added_mats.keys():
                mat = added_mats[tex_sh]
            else:
                mat = copy_mat(tex_name, mat_suffix, mat)
                added_mats[tex_sh] = mat
            p.material_index = trm_mesh.materials.find(mat.name)

        return added_mats.values()

    def setup_materials(self, shader_inst: bpy.types.ShaderNodeTree, type_name: str, trm_mesh, mats: list[bpy.types.Material], folders, addon_prefs):
        for mat in mats:
            mat.use_nodes = True
            nodes = mat.node_tree.nodes
            if shader_inst.name in nodes:
                shader_inst_node = nodes.get(shader_inst.name)
                nodes_to_align = [n for n in nodes]
            else:
                nodes.clear()
                mat_output = nodes.new('ShaderNodeOutputMaterial')
                # Link the shader instance to every material of this shader
                shader_inst_node = trm_utils.create_TRM_shader_inst_node(nodes, shader_inst)
                nodes_to_align = [shader_inst_node, mat_output]

                trm_utils.connect_nodes(mat.node_tree, mat_output, 'Surface', shader_inst_node, 'Shader')     

            # setup material's TRM UI settings from shader
            trm_utils.set_mat_TRM_settings(mat, shader_inst_node, trm_mesh)

            # Get or import texture and link it to shader instance
            if self.use_tex:
                tex_name = mat.name.split('_', 1)[0]
                tex_node, tex = self.get_tex(tex_name, mat)
                if not tex_node:
                    if tex:
                        tex_node = nodes.new('ShaderNodeTexImage')
                        tex_node.image = tex
                    else:
                        tex_node = self.import_texture(addon_prefs, tex_name, folders, mat, nodes)

                if tex_node:
                    nodes_to_align.insert(0, tex_node)
                    trm_utils.connect_nodes(mat.node_tree, shader_inst_node, 'Base Color', tex_node, 0)

            if type_name in trm_utils.SHADER_SUBTYPES[1:]:
                mat.blend_method = "BLEND"
                if self.use_tex and tex_node:
                    trm_utils.connect_nodes(mat.node_tree, shader_inst_node, 'Alpha', tex_node, 1)

            trm_utils.space_out_nodes(nodes_to_align)

    def create_armature(self, filename:str, skeldata_path:str, game_id:str, trm:bpy.types.Object):
        def setup_armature(rig, existing=False):
            trm.parent = rig
            mod = None
            mod_name = 'TRM Armature'
            if existing:
                mod = next(iter([m for m in trm.modifiers if m.type == 'ARMATURE' and m.name == mod_name]), None)
            if not mod:
                mod = trm.modifiers.new(mod_name, 'ARMATURE')
            mod.object = rig

        lara_paths = {"OUTFIT_HANDS_", "OUTFIT_TR", "HOLSTER_", "HAND_"}
        #TODO: Replace entity names with TRM names in the xml
        # get TRM substirng and name, and map as Lara's model if name matches path in the set
        trm_name = next(iter(['LARA' for subname in lara_paths if subname in filename]), filename)

        if trm_name == 'OUTFIT_HAIR':
            game_id = 2
        elif not game_id.isdigit():
            return None, None
        
        skeldata = ET.parse(skeldata_path)
        skeldata_root = skeldata.getroot()

        # try to find TRM by its filename and cancel if not found
        skeldata_arm = skeldata_root.find(f"./Game/[@ID='{game_id}']/Armature/[@name='{trm_name}']")
        if not skeldata_arm:
            self.report({'WARNING'}, f'Could not find Skeleton Data for "{trm_name}" in Game {game_id}. Skipping Armature creation...')
            return None, None
        
        # Look for a first armature with a name having the same substring as one found in TRM name
        rig_name = f'Rig_{trm_name}'
        ob_name = next(iter([ob.name for ob in bpy.context.collection.objects if rig_name == ob.name and ob.type == 'ARMATURE']), "")
        if ob_name:
            rig = bpy.context.collection.objects.get(ob_name)
            setup_armature(rig, True)
            return rig, None
            
        saved_active = bpy.context.active_object
        armature = bpy.data.armatures.new(rig_name)
        rig = bpy.data.objects.new(rig_name, armature)
        bpy.context.collection.objects.link(rig)
        setup_armature(rig)

        bpy.context.view_layer.objects.active = rig
        saved_mode = bpy.context.mode
        bpy.ops.object.mode_set(mode='EDIT')
        e_bones = armature.edit_bones

        default_bone_length = 64
        bone_names = []
        skeldata_bones = skeldata_arm.findall("./Bone")
        for skeldata_bone in skeldata_bones:
            p_ID = int(skeldata_bone.attrib['p_ID'])
            skeldata_bone_head = skeldata_bone.find("./Data/[@type='HEAD']")
            skeldata_bone_tail = skeldata_bone.find("./Data/[@type='TAIL']")

            bone = e_bones.new(f'Bone')
            b_data_head = Vector(eval(skeldata_bone_head.attrib['Vector']))
            b_head = Vector((b_data_head.x, b_data_head.z, b_data_head.y)) * -self.scale
            if self.connect_bones and skeldata_bone_tail is not None:
                b_data_tail = Vector(eval(skeldata_bone_tail.attrib['Vector']))
                b_tail = Vector((b_data_tail.x, b_data_tail.z, b_data_tail.y)) * -self.scale
            else:
                b_tail = Vector((0, default_bone_length, 0)) * self.scale

            b_tail += b_head

            if p_ID > -1:
                bone.parent = e_bones[p_ID]
                if self.auto_orient_bones and self.connect_bones and skeldata_bone_tail is None:
                    parent_bone_direction = Vector(bone.parent.tail - bone.parent.head).normalized()
                    b_tail = parent_bone_direction * default_bone_length * self.scale
                    b_tail += b_head

                bone.head = b_head
                bone.tail = b_tail
                bone.translate(bone.parent.head)
            else:
                bone.head = b_head
                bone.tail = b_tail

            bone_names.append(bone.name)

        bpy.ops.object.mode_set(mode=saved_mode)
        bpy.context.view_layer.objects.active = saved_active

        return rig, bone_names
    
    def normal_byte_to_float(self, xyz:tuple[int, int, int]):
        vec = Vector([b-127 for b in xyz])
        vec.normalize()
        vec.negate()
        return vec
    
    def read_trm_data(self, context, filepath, addon_prefs, filename, skeldata_path):
        print("IMPORTING...")
        f = open(filepath, 'rb')

        # TRM\x02 marker
        if unpack('>I', f.read(4))[0] != bin_parse.TRM_HEADER:
            self.report({'ERROR'}, "Not a TRM file!")
            return {'CANCELLED'}

        # SHADERS
        shaders: list[trm_utils.TRM_Shader] = []
        num_shaders = bin_parse.read_uint32(f)
        for n in range(num_shaders):
            sh_type = bin_parse.read_uint32(f)
            sh_uks = []
            # 4 unknown pieces of data
            for i in range(4):
                uks_floats = [round(v/255, 4) for v in bin_parse.read_uint8_tuple(f, 4)]
                sh_uks.append(uks_floats)

            sh_ids_list = []
            # 3 pieces of indice data
            for i in range(3):
                sh_ids = bin_parse.read_uint32_tuple(f, 2)
                sh_ids_list.append(trm_utils.TRM_ShaderIndices(sh_ids[0], sh_ids[1]))
            shader = trm_utils.TRM_Shader(sh_type, sh_uks[0], sh_uks[1], sh_uks[2], sh_uks[3], sh_ids_list[0], sh_ids_list[1], sh_ids_list[2])
            shaders.append(shader)
            # print(f"Shader[{n}]: {shader}\n")

        # TEXTURES
        num_textures = bin_parse.read_uint32(f)
        textures = bin_parse.read_ushort16_tuple(f, num_textures)

        # BYTE ALIGN
        if f.tell() % 4: f.read(4 - (f.tell()%4))

        # UNKNOWN ANIMATION DATA - STORE IN SEPARATE FILE
        num_anim_bones = bin_parse.read_uint32(f)
        if num_anim_bones > 0:
            anim_bones = tuple(bin_parse.read_float_tuple(f, 12) for n in range(num_anim_bones))
                
            num_anim_unknown2 = bin_parse.read_uint32(f)
            anim_unknown2 = tuple(bin_parse.read_uint32_tuple(f, 2) for n in range(num_anim_unknown2))
            
            num_anim_unknown3 = bin_parse.read_uint32(f)
            anim_unknown3 = bin_parse.read_uint32_tuple(f, num_anim_unknown3) # Frame numbers?
            
            # print(f'num unknown 4 offset: {hex(f.tell())}')
            num_anim_unknown4 = bin_parse.read_ushort16(f)
            # print(f'num unknown 5 offset: {hex(f.tell())}')
            num_anim_unknown5 = bin_parse.read_ushort16(f)  # this is unused, still unknown
            # print(f'unknown 3x4 offset: {hex(f.tell())}')
            anim_unknown4 = tuple(bin_parse.read_float_tuple(f, 12) for n in range(num_anim_unknown3 * num_anim_unknown4))
            # anim_unknown4 = unpack('<%df' % (num_anim_unknown4*num_anim_unknown3*12), f.read(48*num_anim_unknown4*num_anim_unknown3))
            # print(f'end of anim data offset: {hex(f.tell())}')

            trm_anim_filepath = f'{self.directory}{filename}{bin_parse.TRM_ANIM_FORMAT}'
            print("-------------------------------------------------")
            print(f'SAVING UNKNOWN ANIM DATA TO "{trm_anim_filepath}" FILE...')
            from struct import pack
            with open(trm_anim_filepath, 'w+b') as f_anim:
                # TRM\x02 marker
                f_anim.write(pack(">I", bin_parse.TRM_HEADER))

                f_anim.write(pack("<I", num_anim_bones))
                f_anim.write(pack("<%df" % (12*num_anim_bones), *[x for y in anim_bones for x in y]))
                f_anim.write(pack("<I", num_anim_unknown2))
                f_anim.write(pack("<%dI" % (2*num_anim_unknown2), *[x for y in anim_unknown2 for x in y]))
                f_anim.write(pack("<I", num_anim_unknown3))
                f_anim.write(pack("<%dI" % num_anim_unknown3, *anim_unknown3))
                f_anim.write(pack("<H", num_anim_unknown4))
                f_anim.write(pack("<H", num_anim_unknown5))
                f_anim.write(pack("<%df" % (12*num_anim_unknown3 * num_anim_unknown4), *[x for y in anim_unknown4 for x in y]))
            del pack
            self.report({'INFO'}, f'Animation data extracted to "{trm_anim_filepath}". Use this file to export this model back to the game.')
            
            # DEBUG
            if False:
                print(f'Bone amount: {num_anim_bones}')
                n = 0
                if n > -1:
                    print(f'Bone data at [{n}]: {anim_bones[n]}')
                else:
                    print(f'Bone data: {anim_bones}')

                print(f'Animation Data2: {num_anim_unknown2}')
                n = -1
                if n > -1:
                    print(f'Unknown data 2 at [{n}]: {anim_unknown2[n]}')
                else:
                    print(f'Unknown data 2: {anim_unknown2}')

                print(f'Animation Data3: {num_anim_unknown3}')
                n = -1
                if n > -1:
                    print(f'Unknown data 3 at [{n}]: {anim_unknown3[n]}')
                else:
                    print(f'Unknown data 3: {anim_unknown3}')

                print(f'Animation Data4: {num_anim_unknown4}')
                print(f'Animation Data5: {num_anim_unknown5}')
                n = 0
                if n > -1:
                    print(f'Unknown data 4 at [{n}]: {anim_unknown4[n]}')
                else:
                    print(f'Unknown data 4: {anim_unknown4}')


        # INDICE & VERTICE COUNTS
        num_indices = bin_parse.read_uint32(f)
        num_vertices = bin_parse.read_uint32(f)

        # READ INDICES
        indices = bin_parse.read_ushort16_tuple(f, num_indices)

        # BYTE ALIGN
        if f.tell() % 4: f.read(4 - (f.tell()%4))

        # READ VERTICES
        vertices = []
        max_joint = 0
        for n in range(num_vertices):
            vertex = unpack("<fff12B", f.read(24))
            vertices.append(vertex)
            max_joint = max(vertex[7], vertex[8], vertex[9], max_joint)

        f.close()

        print("%d Shaders, %d Textures, %d Indices, %d Vertices, %d Bones" % (num_shaders, num_textures, num_indices, num_vertices, max_joint + 1))

        # CREATE OBJECT
        trm_mesh = bpy.data.meshes.new(f'{filename}_Mesh')
        trm = bpy.data.objects.new(filename, trm_mesh)

        trm_vertices = []
        trm_edges = []
        trm_faces = []

        for n in range(num_vertices):
            v = vertices[n]
            trm_vertices.append([-v[0] * self.scale, -v[2] * self.scale, -v[1] * self.scale])

        for n in range(0, num_indices, 3):
            trm_faces.append([indices[n], indices[n+2], indices[n+1]])

        trm_mesh.from_pydata(trm_vertices, trm_edges, trm_faces, shade_flat=False)
        trm_mesh.update()

        # Get folders in game's or relative TRM path
        folders = None
        if self.use_tex or self.import_armature:
            if self.tex_dir == 'REL':
                # File folder, these modifications assume we're dealing with files from the Remasters.
                folder = Path.dirname(filepath)
                game_dir = f"{folder}/../.."

                # Which game is in question?
                game_id = Path.split(Path.abspath(Path.join(folder, "..")))[-1]
            else:
                game_id = self.tex_dir
                game_dir = addon_prefs.game_path
            
            # List lookup folders, start from the game number, but check also from previous games          
            try:
                folders = [(Path.abspath(f"{game_dir}/{i}/"), i) for i in range(int(game_id), 0, -1)]
                if self.use_tex:
                    folders = [(Path.abspath(f"{p}/TEX/"), i) for p, i in folders]
                
                if not any([Path.exists(p[0]) for p in folders]):
                    raise Exception
    
            except Exception as e:
                self.report({'WARNING'}, f'{type(e).__name__}, Invalid Path: "{Path.abspath(game_dir)}" for filepath "{filepath}" is not in directory with correct game structure!\nSkipping armature and texture import...')
                folders = None

        import_tex = self.use_tex and bool(folders)
        
        # CREATE MATERIALS WITH RANDOM COLOR
        for n in range(num_textures):
            tex_name = str(textures[n])
            mat = self.create_material(tex_name, folders, import_tex)
            trm_mesh.materials.append(mat)

        # ASSIGN MATERIALS
        for p in trm_mesh.polygons:
            p.material_index = vertices[p.vertices[1]][6] - 1

        # DEFINE SHADERS
        mat_shaders = set()
        shader_node_master = trm_utils.get_TRM_shader_ntree()
        for i, sh in enumerate(shaders):
            is_single_shader = num_shaders == 1
            shader_inst_node = trm_utils.get_TRM_shader_inst_ntree(shader_node_master, filename, sh, i)
            if sh.indices1.length > 0:
                mats = self.define_shader(i, trm_utils.SHADER_SUBTYPES[0], sh.indices1, trm_mesh, is_single_shader, import_tex)
                self.setup_materials(shader_inst_node, trm_utils.SHADER_SUBTYPES[0], trm_mesh, mats, folders, addon_prefs)
                mat_shaders.update(mats)
                is_single_shader = False
            if sh.indices2.length > 0:
                mats = self.define_shader(i, trm_utils.SHADER_SUBTYPES[1], sh.indices2, trm_mesh, is_single_shader, import_tex)
                self.setup_materials(shader_inst_node, trm_utils.SHADER_SUBTYPES[1], trm_mesh, mats, folders, addon_prefs)
                mat_shaders.update(mats)
                is_single_shader = False
            if sh.indices3.length > 0:
                mats = self.define_shader(i, trm_utils.SHADER_SUBTYPES[2], sh.indices3, trm_mesh, is_single_shader, import_tex)
                self.setup_materials(shader_inst_node, trm_utils.SHADER_SUBTYPES[2], trm_mesh, mats, folders, addon_prefs)
                mat_shaders.update(mats)
        
        # CUBEMAPS
        for mat in trm_mesh.materials:
            if mat not in mat_shaders and self.use_tex:
                tex_name = mat.name.split('_', 1)[0]
                tex = self.get_tex(tex_name, mat)[1]
                if not tex:
                    mat.use_nodes = True
                    self.import_texture(addon_prefs, tex_name, folders, mat, mat.node_tree.nodes)

        # CREATE UV DATA
        trm_mesh.uv_layers.new()
        uvs = trm_mesh.uv_layers.active
        for p in trm_mesh.polygons:
            for i in p.loop_indices:
                v = trm_mesh.loops[i].vertex_index
                uvs.data[i].uv = (vertices[v][10] / 255, (255 - vertices[v][14]) / 255)
        
        # CREATE ARMATURE
        if skeldata_path:
            rig, bone_names = self.create_armature(filename, skeldata_path, game_id, trm)
        else:
            rig, bone_names = None, None

        # CREATE & ASSIGN VERTEX GROUPS
        create_vertex_groups(trm, max_joint + 1, rig, bone_names, self.mesh_type, filename)
        for n in range(num_vertices):
            g = trm.vertex_groups
            v = vertices[n]
            for v_i, v_w in enumerate(range(11, 14), 7):
                g_weight = v[v_w]
                g_id = v[v_i]
                if g_weight > 0:
                    g[g_id].add([n], g_weight/255, 'ADD')

        # CREATE NORMALS
        trm_normals = []

        for n in range(num_vertices):
            v = vertices[n]
            normal = self.normal_byte_to_float((v[3], v[5], v[4]))
            trm_normals.append(normal)

        trm_mesh.normals_split_custom_set_from_vertices(trm_normals)
        if bpy.app.version < (4,1):
            trm_mesh.use_auto_smooth = True
            trm_mesh.calc_normals_split()
        trm_mesh.update()

        # merge edges along UV seams
        if self.merge_uv:
            split_normals = []
            for l in trm_mesh.loops:
                split_normals.append(l.normal.copy())

            import bmesh

            trm_bmesh = bmesh.new()
            trm_bmesh.from_mesh(trm_mesh)
            verts_to_merge = set()

            for e in trm_bmesh.edges:
                if e.is_boundary:
                    e.seam = True
                    for v in e.verts:
                        verts_to_merge.add(v)
            bmesh.ops.remove_doubles(trm_bmesh, verts=list(verts_to_merge), dist=0.0001)

            for e in trm_bmesh.edges:
                if not e.is_manifold:
                    e.seam = False

            trm_bmesh.to_mesh(trm_mesh)
            trm_bmesh.free()

            try:
                trm_mesh.normals_split_custom_set(split_normals)
            except Exception as e:
                self.report({'ERROR'}, f'{e}\nCould not merge mesh by UV seams for "{filename}".\nDisable "Merge by UVs" and try again.')
                # cleanup created data
                # (some will remain, it's more work than it's worth to track everything down)
                for mat in trm_mesh.materials:
                    bpy.data.materials.remove(mat)
                bpy.data.meshes.remove(trm_mesh)
                if rig:
                    bpy.data.armatures.remove(rig.data)
                return {'CANCELLED'}
            trm_mesh.update()

        trm_mesh.validate()

        bpy.context.collection.objects.link(trm)

        print("DONE!")
        return {'FINISHED'}

    def execute(self, context):
        start_time = time.process_time()
        if len(self.files) == 1:
            self.report({'INFO'}, "Importing TRM...%r" % self.filepath)
        else:
            self.report({'INFO'}, "Importing TRM files...")

        addon_prefs = bpy.context.preferences.addons[__package__].preferences
        texconv_path = addon_prefs.dds_tool_filepath
        if self.use_tex and (not Path.exists(texconv_path) or not texconv_path.endswith('.exe')):
            self.report({'WARNING'}, f'Wrong DDS Converter path or file type: "{texconv_path}", skipping texture conversion...')
            self.skip_texconv = True

        if self.import_armature:
            addon_dir = os.path.dirname(__file__)
            skeldata_path = os.path.join(addon_dir, SKELETON_DATA_FILEPATH)
            # Generate missing SkeletonData.xml on a first import that can create an armature
            # TODO: Support more/all TRMs - this will require pairing TRM names with model IDs
            if not os.path.exists(skeldata_path):
                print("Generating Skeleton Data...")
                result = bpy.ops.io_tombraider123r.generate_skeleton_data()
                if result == {'CANCELLED'}:
                    self.report({'ERROR'}, "Could not generate Skeleton Data!\nCheck if Game Directory path in addon's preferences is provided. Armature not imported.")
                    skeldata_path = None
        else:
            skeldata_path = None

        for f in self.files:
            filepath = Path.join(self.directory, f.name)
        
            obj_name = str(f.name).removesuffix(self.filename_ext)
            result = self.read_trm_data(context, filepath, addon_prefs, obj_name, skeldata_path)

        end_time = time.process_time() - start_time
        if result != {'CANCELLED'}:
            self.report({'INFO'}, "Import finished in %.4f sec." % (end_time))
        return result
    
    def draw_warning(self, layout: bpy.types.UILayout, msg: str):
        col = layout.column()
        col.scale_y = .5
        col.alert = True
        col.label(text="Warning!")
        col.label(text=msg)

        col = layout.column()
        col.scale_y = .5
        col.label(text="Make sure you're importing")
        col.label(text="from the game files or have mirrored")
        col.label(text="the original ITEM and TEX folder structure.")
    
    def draw(self, context):
        addon_prefs = bpy.context.preferences.addons[__package__].preferences
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False  # No animation.

        layout.prop(self, 'scale')
        layout.prop(self, 'mesh_type')
        layout.prop(self, 'merge_uv')
        layout.prop(self, 'import_armature')
        if self.import_armature:
            layout.prop(self, 'connect_bones')
            if self.connect_bones:
                layout.prop(self, 'auto_orient_bones')
        layout.prop(self, 'use_tex')

        if self.use_tex or self.import_armature:
            col = layout.column()
            if addon_prefs.game_path:
                use_texdir = True                
                # Set the game directory number if path in preferences was provided
                if Path.exists(f'{addon_prefs.game_path}/tomb123.exe'):
                    for i in range(1,4):
                        if Path.abspath(f'{addon_prefs.game_path}/{i}') in Path.abspath(self.directory):
                            use_texdir = False
                            self.tex_dir = str(i)
                            break
                # Fallback to relative path for bad game directory
                else:
                    self.draw_warning(layout, "Game path is wrong!")
                    self.tex_dir = 'REL'
                    col.enabled = False
                    
                if use_texdir:
                    col.prop(self, 'tex_dir')
            else:
                self.draw_warning(layout, "Game path is not provided!")
                col.prop(self, 'tex_dir')
                self.tex_dir = 'REL'
                col.enabled = False

def register():
    bpy.utils.register_class(TR123R_OT_ImportTRM)

def unregister():
    bpy.utils.unregister_class(TR123R_OT_ImportTRM)