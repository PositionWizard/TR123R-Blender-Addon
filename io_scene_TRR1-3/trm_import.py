import bpy
from struct import unpack
import math
import random
import os.path as Path
import subprocess
from . import trm_parse
from . import utils as trm_utils

def NormalBYTE2FLOAT(x, y, z):
    x = x - 127
    y = y - 127
    z = z - 127
    length = math.sqrt((x * x) + (y * y) + (z * z))
    return (x / length, y / length, z / length)

def CreateVertexGroups(trm, joints, armature, filepath):
    # possible vertex group names, 10 per line for easier counting
    vg_names = [
        "root", "hips", "stomach", "chest", "torso", "neck", "head", "jaw", "jaw_lower", "jaw_upper",
        "hip_L", "thigh_L", "thighB_L", "knee_L", "calf_L", "calfB_L", "ankle_L", "foot_L", "toe_L", "toes_L",
        "hip_R", "thigh_R", "thighB_R", "knee_R", "calf_R", "calfB_R", "ankle_R", "foot_R", "toe_R", "toes_R",
        "shoulder_L", "shoulderB_L", "arm_L", "armB_L", "elbow_L", "elbowB_L", "wrist_L", "hand_L", "thumb_L", "fingers_L",
        "shoulder_R", "shoulderB_R", "arm_R", "armB_R", "elbow_R", "elbowB_R", "wrist_R", "hand_R", "thumb_R", "fingers_R",
        "hair_root", "hair1", "hair2", "hair3", "hair4", "hair5", "hair6", "hair7", "hair8", "hair9",
        # more to be added here
    ]

    # lists to get names by order
    vg_lists = {
        "Lara_Body": [1, 11, 14, 17, 21, 24, 27, 4, 42, 44, 47, 32, 34, 37, 6],
        "Lara_Hair": [50, 51, 52, 53, 54, 55],
    }

    # map for list decision
    vg_names_map = {
        "_HAIR": 'Lara_Hair',
        "OUTFIT_": 'Lara_Body',
        "HOLSTER_": 'Lara_Body',
        "HAND_": 'Lara_Body',
    }

    # decide which list to use
    if armature == 'AUTO':
        for k in vg_names_map.keys():
            if k in filepath:
                armature = vg_names_map[k]
                break

    gl = []
    if armature in vg_lists:
        gl = vg_lists[armature]

    len1 = len(gl)
    len2 = len(vg_names)
    for n in range(joints):
        if n < len1 and gl[n] < len2:
            name = vg_names[gl[n]]
        else:
            name = "Joint" + str(n)
        trm.vertex_groups.new(name=name)


from bpy_extras.io_utils import ImportHelper
from bpy.props import StringProperty, BoolProperty, EnumProperty, CollectionProperty, FloatProperty
from bpy.types import Operator
import os

class ImportTRMData(Operator, ImportHelper):
    """Load object from TRM file"""
    bl_idname = "io_tombraider123r.trm_import"
    bl_label = "Import TRM"
    bl_options = {'UNDO'}

    filename_ext = ".TRM"

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
        default="*.TRM",
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
        description="Specify the game to look for the textures in.\n"
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

    def load_png(self, mat: bpy.types.Material, path_png, nodes: bpy.types.Nodes):
        texture_node = nodes.new('ShaderNodeTexImage')
        texture_node.image = bpy.data.images.load(path_png)

        return texture_node

    def import_texture(self, addon_prefs, tex_name, folders: list[tuple[str, int]], mat: bpy.types.Material, nodes):
        tex_conv_path = addon_prefs.dds_tool_filepath
        png_export_path = addon_prefs.tex_conv_directory
        tex_node = None
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
            # Convert DDS to PNG, if the DDS exists but not the PNG
            elif Path.exists(path_dds):
                print(f"DDS located in: {path_dds}")
                if not Path.exists(tex_conv_path) or not tex_conv_path.endswith('.exe'):
                    self.report({'WARNING'}, f'Wrong DDS Converter path or file type: "{tex_conv_path}", skipping texture import...')
                    break
                
                # Create PNGs folder into "Tombraider Remastered Trilogy\[1,2,3]\TEX\" or other directory specified in prefs
                if not Path.exists(path_png_dir):
                    print(f"{path_png_dir} does not exists, creating...")
                    os.makedirs(path_png_dir)
                        
                subprocess.run([tex_conv_path, path_dds, "-nologo", "-o", path_png_dir, "-ft", "png"])
                tex_node = self.load_png(mat, path_png, nodes)
                break
            else:
                self.report({'WARNING'}, f"No texture found in Game [{game_id}] folder. trying next game...")

        if not tex_node:
            self.report({'WARNING'}, f"No DDS or PNG texture found for '{tex_name}'! skipping texture import...")

        return tex_node
    
    def get_tex(self, tex_name:str, mat:bpy.types.Material, folders:str, addon_prefs):
        nodes = mat.node_tree.nodes
        texture_node = None
        tex = None
        
        # look for shader nodes with the texture
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

    def create_material(self, tex_name="", folders=""):
        # Check what game the texture is from to tag a material with it
        mat_suffix = ""
        if self.use_tex:
            for folder, game_id in folders:
                path_dds = Path.join(folder, f"{tex_name}.dds")
                if Path.exists(path_dds):
                    mat_suffix = "_Game-"+str(game_id)
                    break
                    
        mat_name = tex_name+mat_suffix

        if mat_name in bpy.data.materials:
            print(f'Material "{mat_name}" already exists, using the existing one for this model.') 
            mat = bpy.data.materials.get(mat_name)
        else:
            mat = bpy.data.materials.new(name=mat_name)
            mat.diffuse_color = (random.random(), random.random(), random.random(), 1)

        return mat
    
    def define_shader(self, index: int, type_name: str, sh_ids: trm_utils.TRM_ShaderIndices, trm_mesh: bpy.types.Mesh, is_single, has_tex):
        def copy_mat(tex_name, mat_suffix, mat: bpy.types.Material):
            # Don't tag and duplicate the material with shader name if
            # it's from the first range of indices
            if type_name == trm_utils.SHADER_SUBTYPES[0]:
                tex_name += f'_{index}'
            else:
                tex_name += f'_{index}_{type_name}'
            
            if mat_suffix:
                tex_name += f'_{mat_suffix}'

            # swap imported material in the same slot, with correct one still in memory
            swap_mats = type_name == trm_utils.SHADER_SUBTYPES[0] or is_single
            if tex_name in bpy.data.materials:
                if swap_mats:
                    prev_mat_id = trm_mesh.materials.find(mat.name)
                    mat = bpy.data.materials.get(tex_name)
                    trm_mesh.materials[prev_mat_id] = mat
                else:
                    mat = bpy.data.materials.get(tex_name)
                    trm_mesh.materials.append(mat)
            else:
                if not swap_mats:
                    mat = mat.copy()
                    trm_mesh.materials.append(mat)
                mat.name = tex_name
            return mat
        
        poly_start = int(sh_ids.offset/3)
        poly_stop = int((sh_ids.offset+sh_ids.length)/3)
        added_mats = {}
        # Find polygons in the given shader indices range and either rename
        # or duplicate their exisitng materials, tagging them with shader index and subtype
        for p in trm_mesh.polygons:
            if poly_start <= p.index < poly_stop:
                mat = trm_mesh.materials[p.material_index]
                mat_name_slice = mat.name.split('_')
                tex_name, mat_suffix = [mat_name_slice[0], mat_name_slice[-1] if len(mat_name_slice)>1 and has_tex else ""]
                # Save the operation in memory to avoid excess material duplication
                if tex_name in added_mats.keys():
                    mat = added_mats[tex_name]
                else:
                    mat = copy_mat(tex_name, mat_suffix, mat)
                    added_mats[tex_name] = mat
                p.material_index = trm_mesh.materials.find(mat.name)

        return added_mats.values()

    def setup_materials(self, shader_inst: bpy.types.ShaderNodeTree, type_name: str, mats: list[bpy.types.Material], folders, addon_prefs):
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
                shader_inst_node = trm_utils.create_TRM_shader_inst_nodegroup(nodes, shader_inst)
                nodes_to_align = [shader_inst_node, mat_output]

                trm_utils.connect_nodes(mat.node_tree, mat_output, 'Surface', shader_inst_node, 'Shader')     

            # Get or import texture and link it to shader instance
            if self.use_tex:
                tex_name = mat.name.split('_', 1)[0]
                tex_node, tex = self.get_tex(tex_name, mat, folders, addon_prefs)
                if not tex_node:
                    if tex:
                        tex_node = nodes.new('ShaderNodeTexImage')
                        tex_node.image = tex
                    else:
                        tex_node = self.import_texture(addon_prefs, tex_name, folders, mat, nodes)

                nodes_to_align.insert(0, tex_node)
                trm_utils.connect_nodes(mat.node_tree, shader_inst_node, 'Base Color', tex_node, 0)

            if type_name == trm_utils.SHADER_SUBTYPES[2]:
                mat.blend_method = "BLEND"
                if self.use_tex and tex_node:
                    trm_utils.connect_nodes(mat.node_tree, shader_inst_node, 'Alpha', tex_node, 1)
                            
            if type_name == trm_utils.SHADER_SUBTYPES[1]:
                shader_inst_node.inputs[2].default_value = True

            trm_utils.space_out_nodes(nodes_to_align)

    def read_trm_data(self, context, filepath, addon_prefs, filename):
        print("IMPORTING...")
        f = open(filepath, 'rb')

        # TRM\x02 marker
        if unpack('>I', f.read(4))[0] != 0x54524d02:
            self.report({'ERROR'}, "Not a TRM file!")
            return {'CANCELLED'}

        # SHADERS
        shaders: list[trm_utils.TRM_Shader] = []
        num_shaders = trm_parse.read_uint32(f)
        for n in range(num_shaders):
            sh_type = trm_parse.read_uint32(f)
            sh_uks = []
            # 4 unknown pieces of data
            for i in range(4):
                uks_floats = [round(v/255, 4) for v in trm_parse.read_uint8_tuple(f, 4)]
                sh_uks.append(uks_floats)

            sh_ids_list = []
            # 3 pieces of indice data
            for i in range(3):
                sh_ids = trm_parse.read_uint32_tuple(f, 2)
                sh_ids_list.append(trm_utils.TRM_ShaderIndices(sh_ids[0], sh_ids[1]))
            shader = trm_utils.TRM_Shader(sh_type, sh_uks[0], sh_uks[1], sh_uks[2], sh_uks[3], sh_ids_list[0], sh_ids_list[1], sh_ids_list[2])
            shaders.append(shader)
            print(f"Shader[{n}]: {shader}\n")

        # TEXTURES
        num_textures = trm_parse.read_uint32(f)
        textures = trm_parse.read_ushort16_tuple(f, num_textures)

        # BYTE ALIGN
        if f.tell() % 4: f.read(4 - (f.tell()%4))

        # UNKNOWN, SKIP OVER
        num_unknown1 = trm_parse.read_uint32(f)
        if num_unknown1 > 0:
            f.seek(num_unknown1 * 48, 1)
            num_unknown2 = trm_parse.read_uint32(f)
            f.seek(num_unknown2 * 8, 1)
            num_unknown3 = trm_parse.read_uint32(f)
            f.seek(num_unknown3 * 4, 1)
            num_unknown4 = trm_parse.read_ushort16(f)
            num_unknown5 = trm_parse.read_ushort16(f)
            f.seek(num_unknown3 * num_unknown4 * 48, 1)

        # INDICE & VERTICE COUNTS
        num_indices = trm_parse.read_uint32(f)
        num_vertices = trm_parse.read_uint32(f)

        # READ INDICES
        indices = trm_parse.read_ushort16_tuple(f, num_indices)

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

        print("%d Shaders, %d Textures, %d Indices, %d Vertices, %d Joints" % (num_shaders, num_textures, num_indices, num_vertices, max_joint + 1))

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
        if self.use_tex:
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
                folders = [(Path.abspath(f"{game_dir}/{i}/TEX/"), i) for i in range(int(game_id), 0, -1)]
            except Exception as e:
                self.report({'ERROR'}, f'{type(e).__name__}, Invalid Path: "{self.filename_ext}" is not in directory with correct game structure!')
                return {'CANCELLED'}
        else:
            folders = None
        
        
        # CREATE MATERIALS WITH RANDOM COLOR
        for n in range(num_textures):
            tex_name = str(textures[n])
            mat = self.create_material(tex_name, folders)
            trm_mesh.materials.append(mat)

        # ASSIGN MATERIALS
        for p in trm_mesh.polygons:
            p.material_index = vertices[p.vertices[1]][6] - 1

        shader_node_master = trm_utils.get_TRM_shader()
        for i, sh in enumerate(shaders):
            is_single_shader = num_shaders == 1
            shader_inst_node = trm_utils.get_TRM_shader_inst(shader_node_master, trm.name, sh, i)
            if sh.indices1.length > 0:
                mats = self.define_shader(i, trm_utils.SHADER_SUBTYPES[0], sh.indices1, trm_mesh, is_single_shader, self.use_tex)
                self.setup_materials(shader_inst_node, trm_utils.SHADER_SUBTYPES[0], mats, folders, addon_prefs)
                is_single_shader = False
            if sh.indices2.length > 0:
                mats = self.define_shader(i, trm_utils.SHADER_SUBTYPES[1], sh.indices2, trm_mesh, is_single_shader, self.use_tex)
                self.setup_materials(shader_inst_node, trm_utils.SHADER_SUBTYPES[1], mats, folders, addon_prefs)
                is_single_shader = False
            if sh.indices3.length > 0:
                mats = self.define_shader(i, trm_utils.SHADER_SUBTYPES[2], sh.indices3, trm_mesh, is_single_shader, self.use_tex)
                self.setup_materials(shader_inst_node, trm_utils.SHADER_SUBTYPES[2], mats, folders, addon_prefs)

        # CREATE UV DATA
        trm_mesh.uv_layers.new()
        uvs = trm_mesh.uv_layers.active
        for p in trm_mesh.polygons:
            for i in p.loop_indices:
                v = trm_mesh.loops[i].vertex_index
                uvs.data[i].uv = (vertices[v][10] / 255, (255 - vertices[v][14]) / 255)

        # CREATE & ASSIGN VERTEX GROUPS
        CreateVertexGroups(trm, max_joint + 1, self.mesh_type, filepath)
        for n in range(num_vertices):
            g = trm.vertex_groups
            v = vertices[n]
            if v[11] > 0:
                g[v[7]].add([n], v[11]/255, 'ADD')
            if v[12] > 0:
                g[v[8]].add([n], v[12]/255, 'ADD')
            if v[13] > 0:
                g[v[9]].add([n], v[13]/255, 'ADD')

        # CREATE NORMALS
        trm_normals = []

        for n in range(num_vertices):
            v = vertices[n]
            normal = NormalBYTE2FLOAT(v[3], v[5], v[4])
            trm_normals.append(( -normal[0], -normal[1], -normal[2] ))

        trm_mesh.use_auto_smooth = True
        trm_mesh.normals_split_custom_set_from_vertices(trm_normals)
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

            trm_mesh.normals_split_custom_set(split_normals)
            trm_mesh.update()

        trm_mesh.validate()

        bpy.context.collection.objects.link(trm)

        print("DONE!")
        self.report({'INFO'}, "Import Completed.")

        return {'FINISHED'}

    def execute(self, context):
        addon_prefs = bpy.context.preferences.addons[__package__].preferences
        for f in self.files:
            filepath = Path.join(self.directory, f.name)
            obj_name = str(f.name).removesuffix(self.filename_ext)
            result = self.read_trm_data(context, filepath, addon_prefs, obj_name)
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
        layout.prop(self, 'use_tex')

        if self.use_tex:
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

def menu_func_import(self, context):
    self.layout.operator(ImportTRMData.bl_idname, text="Tomb Raider I-III Remastered (.TRM)")

def register():
    bpy.utils.register_class(ImportTRMData)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)

def unregister():
    bpy.utils.unregister_class(ImportTRMData)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)