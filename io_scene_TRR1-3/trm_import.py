# v0.4

import bpy
from struct import unpack
import math
import random
import os.path as Path
import subprocess

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
    bl_idname = "io_tombraider.trm_import"
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
            ('3', "III", "")
        ),
        default='1',
    )

    merge_uv: BoolProperty(
        name="Merge by UVs",
        description="Tries to weld non-manifold edges, resulting in mesh welding along UV seams.\n"
                    "Helps with shading and mesh editing",
        default=True
    )

    def execute(self, context):
        addon_prefs = bpy.context.preferences.addons[__package__].preferences

        for f in self.files:
            filepath = Path.join(self.directory, f.name)
            obj_name = str(f.name).removesuffix(self.filename_ext)
            result = self.read_trm_data(context, filepath, addon_prefs, obj_name)
        return result
    
    def draw(self, context):
        addon_prefs = bpy.context.preferences.addons[__package__].preferences
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False  # No animation.

        layout.prop(self, 'scale')
        layout.prop(self, 'mesh_type')
        layout.prop(self, 'merge_uv')
        layout.prop(self, 'use_tex')

        if self.use_tex and addon_prefs.game_path:
            layout.prop(self, 'tex_dir')
    
    def read_trm_data(self, context, filepath, addon_prefs, filename):
        print("IMPORTING...")
        f = open(filepath, 'rb')

        # TRM\x02 marker
        if unpack('>I', f.read(4))[0] != 0x54524d02:
            self.report({'ERROR'}, "Not a TRM file!")
            return {'CANCELLED'}

         # PARTIALLY UNKNOWN, SKIP OVER
        num_shaders = unpack('<I', f.read(4))[0]
        f.seek(num_shaders * 44, 1)

        # TEXTURES
        num_textures = unpack('<I', f.read(4))[0]
        textures = unpack("<%dH" % num_textures, f.read(num_textures * 2))

        # BYTE ALIGN
        if f.tell() % 4: f.read(4 - (f.tell()%4))

        # UNKNOWN, SKIP OVER
        num_unknown1 = unpack('<I', f.read(4))[0]
        if num_unknown1 > 0:
            f.seek(num_unknown1 * 48, 1)
            num_unknown2 = unpack('<I', f.read(4))[0]
            f.seek(num_unknown2 * 8, 1)
            num_unknown3 = unpack('<I', f.read(4))[0]
            f.seek(num_unknown3 * 4, 1)
            num_unknown4 = unpack('<H', f.read(2))[0]
            num_unknown5 = unpack('<H', f.read(2))[0]
            f.seek(num_unknown3 * num_unknown4 * 48, 1)

        # INDICE & VERTICE COUNTS
        num_indices = unpack('<I', f.read(4))[0]
        num_vertices = unpack('<I', f.read(4))[0]

        # READ INDICES
        indices = unpack("<%sH" % num_indices, f.read(num_indices * 2))

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

        trm_mesh.from_pydata(trm_vertices, trm_edges, trm_faces)
        trm_mesh.update()
        
        if self.use_tex:
            if addon_prefs.game_path:
                # List lookup folders, start from the game number, but check also from previous games
                folders = [Path.abspath(f"{addon_prefs.game_path}/{i}/TEX/") for i in range(int(self.tex_dir), 0, -1)]
            else:
                # File folder, these modifications assume we're dealing with files from the Remasters.
                folder = Path.dirname(filepath)

                # Which game is in question?
                game = Path.split(Path.abspath(Path.join(folder, "..")))[-1]
                
                # List lookup folders, start from the game number, but check also from previous games
                folders = [Path.abspath(f"{folder}/../../{i}/TEX/") for i in range(int(game), 0, -1)]
        
        
        # CREATE MATERIALS WITH RANDOM COLOR
        for n in range(num_textures):
            mat_name = str(textures[n])+"_Material"
            if mat_name in bpy.data.materials:
                print(f"Material {mat_name} already exists, using the existing one for this model.") 
                trm.data.materials.append(bpy.data.materials.get(mat_name))
                continue 
                
            mat = bpy.data.materials.new(name=mat_name)
            mat.diffuse_color = (random.random(), random.random(), random.random(), 1)
            
            if self.use_tex:
                tex_conv_path = addon_prefs.dds_tool_filepath
                png_export_path = addon_prefs.tex_conv_directory
                if Path.exists(tex_conv_path) and tex_conv_path.endswith('.exe'):
                    mat.use_nodes = True
                    nodes = mat.node_tree.nodes
                    texture_node = nodes.new('ShaderNodeTexImage')

                    image_path = ""
                    for folder in folders:
                        path_dds = Path.join(folder, f"{str(textures[n])}.dds")
                        if not png_export_path:
                            path_png_dir = Path.join(folder, 'PNGs')
                        else: 
                            path_png_dir = png_export_path

                        path_png = Path.join(path_png_dir, f"{str(textures[n])}.png")
                        
                        if Path.exists(path_dds):
                            print(f"DDS located in: {path_dds}")
                            # Create PNGs folder into "Tombraider Remastered Trilogy\[1,2,3]\TEX\" or other directory specified in prefs
                            target_dir = path_png_dir
                            if not Path.exists(target_dir):
                                print(f"{target_dir} does not exists, creating...")
                                os.mkdir(target_dir)
                            
                            # Convert dds to png, if the dds exists but not the png
                            if not Path.exists(path_png): 
                                result = subprocess.run([tex_conv_path, path_dds, "-nologo", "-o", target_dir, "-ft", "png"])
                            image_path = path_png
                            print(image_path)
                            
                            texture_node.image = bpy.data.images.load(path_png)
                            break
                        
                    if 'Principled BSDF' in nodes:
                        principled_node = nodes['Principled BSDF']
                        mat.node_tree.links.new(texture_node.outputs[0], principled_node.inputs['Base Color'])

                else:
                    self.report({'WARNING'}, f'Wrong DDS Converter path or file type: "{tex_conv_path}", skipping texture import.')
                    
            trm.data.materials.append(mat)

        # ASSIGN MATERIALS
        for n in range(len(trm_mesh.polygons)):
            p = trm_mesh.polygons[n]
            p.material_index = vertices[p.vertices[1]][6] - 1

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

        # initial normals smoothing
        for p in trm_mesh.polygons:
            p.use_smooth = True

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
                if not e.is_manifold:
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

def menu_func_import(self, context):
    self.layout.operator(ImportTRMData.bl_idname, text="Tomb Raider I-III Remastered (.TRM)")

def register():
    bpy.utils.register_class(ImportTRMData)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)

def unregister():
    bpy.utils.unregister_class(ImportTRMData)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)