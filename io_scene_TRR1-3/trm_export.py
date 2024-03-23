# v0.5.1

import bpy, math
from struct import pack
import bmesh

def normalFloat2Byte(x, y, z):
    length = math.sqrt((x * x) + (y * y) + (z * z))
    if length != 0:
        x = (x / length) * 126
        y = (y / length) * 126
        z = (z / length) * 126
        return (round(x + 127), round(y + 127), round(z + 127))
    return (127, 127, 127)

from bpy_extras.io_utils import ExportHelper
from bpy.props import StringProperty, BoolProperty, FloatProperty
from bpy.types import Operator
from mathutils import Vector, Matrix
from . import utils as trm_utils

class ExportTRMData(Operator, ExportHelper):
    """Save object as TRM file"""
    bl_idname = "io_tombraider123r.trm_export"
    bl_label = "Export TRM"

    filename_ext = ".TRM"

    filter_glob: StringProperty(
        default="*.TRM",
        options={'HIDDEN'},
        maxlen=255,
    )

    act_only: BoolProperty(
        name="Active Only",
        description="Export only active object",
        default=False
    )

    scale: FloatProperty(
        name="Scale",
        description="Scale vertices",
        default=100.0,
    )

    apply_mods: BoolProperty(
        name="Apply Modifiers",
        description="Apply modifiers on all exported objects",
        default=False,
    )

    apply_transforms: BoolProperty(
        name="Apply Transforms",
        description="Apply object location, rotation and scale",
        default=True,
    )
 
    def copy_object(self, obj: bpy.types.Object):
        # COPY OBJECT AND MESH
        obj_mesh = obj.data.copy()
        obj_c = obj.copy()
        obj_c.data = obj_mesh
        bpy.context.view_layer.layer_collection.collection.objects.link(obj_c)
        obj.select_set(False)

        if bpy.context.active_object == obj:
            bpy.context.view_layer.objects.active = obj_c

        return obj_c
    
    def clean_copies(self, obj_copies: list[bpy.types.Object]):
        for obj_c in obj_copies:
            bpy.data.meshes.remove(obj_c.data)     
 
    def prepare_mesh(self, obj_c: bpy.types.Object):
        if self.apply_mods:
            bpy.context.view_layer.objects.active = obj_c 
            for mod in obj_c.modifiers:
                if mod.show_viewport:
                    bpy.ops.object.modifier_apply(modifier=mod.name)

        if self.apply_transforms:
            obj_c.data.transform(obj_c.matrix_world)
            obj_c.data.update()

        # TRIANGULATE COPY
        bm = bmesh.new()
        bm.from_mesh(obj_c.data)
        bmesh.ops.triangulate(bm, faces=bm.faces)
        bm.to_mesh(obj_c.data)
        bm.free()

    def get_trm(self, act_obj: bpy.types.Object, sel_obj: list[bpy.types.Object]):
        err_call = {'ERROR'}, "Select a 3D Object!"
        result = {'CANCELLED'}, None, None
        if not self.act_only:
            objs = [self.copy_object(o) for o in sel_obj if o.type == 'MESH']
            if not objs:
                self.report(err_call)
                return result

            for obj_c in objs:
                self.prepare_mesh(obj_c)
                obj_c.select_set(True)
        
            bpy.ops.object.join()
        else:
            if not act_obj or act_obj.type != 'MESH':
                self.report(err_call)
                return result
            obj = self.copy_object(act_obj)
            self.prepare_mesh(obj)
            objs = [obj]
            
        trm = bpy.context.active_object
        result = {'PASS_THROUGH'}, trm, objs
        return result
    
    # VERTEX PACKER
    def PackVertex(self, coordinate, normal, texture, groups, uv):
        vx = -coordinate.x * self.scale
        vy = -coordinate.z * self.scale
        vz = -coordinate.y * self.scale
        nr = normalFloat2Byte(-normal[0], -normal[1], -normal[2])
        nx = nr[0]
        ny = nr[2]
        nz = nr[1]
        tex = texture + 1
        tu = round(uv[0] * 255)
        tv = 255 - round(uv[1] * 255)
        g1 = 0
        w1 = 255
        g2 = 0
        w2 = 0
        g3 = 0
        w3 = 0
        if len(groups) > 0:
            g1 = groups[0].group
            w1 = round(groups[0].weight * 255)
        if len(groups) > 1:
            g2 = groups[1].group
            w2 = round(groups[1].weight * 255)
        if len(groups) > 2:
            g3 = groups[2].group
            w3 = round(groups[2].weight * 255)
        return pack("<fff12B", vx,vy,vz, nx,ny,nz, tex, g1,g2,g3, tu, w1,w2,w3, tv)
    
    def write_trm_data(self, context, trm_mesh: bpy.types.Mesh, filepath):
        print("EXPORTING...")

        trm_mesh.calc_normals_split()

        def uv_offset(x):
            if x > 0.0:
                offset = -(math.ceil(x/1.0)-1)
            else:
                offset = -math.floor(x/1.0)
            return x+offset

        # tex_map = {}
        textures = []
        shader_map = {}
        mat_map = []
        mat_i = 0
        for mat in trm_mesh.materials:
            mat_info = [None, trm_utils.SHADER_SUBTYPES[0], 0]
            if mat:
                # Material name structure = [TextureID, ShaderID, ShaderSubtype, ...]
                mat_name_slice = mat.name.split('_')
                tex_id = trm_utils.str_to_int(mat_name_slice[0])
                if tex_id == None:
                    tex_id = 8000
                # Get correct material slot indices without duplicates for same textures (shader support)
                # if tex_id not in tex_map.keys():
                #     tex_map[tex_id] = mat_i
                if tex_id in textures:
                    mat_info[2] = textures.index(tex_id)
                else:
                    mat_info[2] = len(textures)
                    textures.append(tex_id)

                # Get Shader info from materials, skipping cubemaps (they don't have it)
                if len(mat_name_slice)>1:
                    sh_ID = trm_utils.str_to_int(mat_name_slice[1])
                    if sh_ID == None or not 0 <= sh_ID <= 0xffff:
                        mat_map.append(mat_info)
                        mat_i += 1
                        continue

                    if len(mat_name_slice)>2 and mat_name_slice[2] in trm_utils.SHADER_SUBTYPES:
                        mat_info[1] = mat_name_slice[2]

                    shadernode_inst = trm_utils.find_TRM_shader_inst(mat)
                    if shadernode_inst:           
                        sh_data = []
                        # get all shader data values into a list
                        for st_i, st in enumerate(trm_utils.SHADER_DATA_NAMES):
                            sh_d = shadernode_inst.inputs[st].default_value
                            if st_i > 0: 
                                sh_d = trm_utils.rgba_to_int(sh_d)
                            sh_data.append(int(sh_d))

                        if sh_ID not in shader_map.keys():
                            # create a map of shader and index lists for every shader subtype
                            print(sh_data)
                            shader_map[sh_ID] = {'pack': pack("<5I", *sh_data)}
                            for st in trm_utils.SHADER_SUBTYPES:
                                shader_map[sh_ID][st] = []

                        # shader_map[sh_ID] = {'pack': pack("<5I", sh_type, sh_data1, sh_data2, sh_data3, sh_data4), 'indicesA': [], 'indicesB': [], 'indicesC': []}

                    mat_info[0] = sh_ID
                
            mat_map.append(mat_info)
            mat_i += 1

        # PREPARE INDICES & VERTICES DATA
        vertices = []
        num_vertices = len(vertices)
        uvs = trm_mesh.uv_layers.active
        v_order = [0, 2, 1]

        uv_err_occured = False
        for p in trm_mesh.polygons:
            mat_info = mat_map[p.material_index]
            sh_ID = mat_info[0]
            sh_subtype = mat_info[1]
            tex_id = mat_info[2]
            # tex_id = trm_mesh.materials[p.material_index].name.split('_', 1)[0]
            # mat_index = tex_map[tex_id]
            for i in v_order:
                loop = trm_mesh.loops[p.loop_indices[i]]
                groups = trm_mesh.vertices[loop.vertex_index].groups
                if len(groups) > 3:
                    self.report({'ERROR'}, "Maximum 3 Joints Allowed per Vertex!")
                    return {'CANCELLED'}
                
                uv = uvs.data[p.loop_indices[i]].uv
                uv_out_U = uv[0] < 0 or uv[0] > 1.0
                uv_out_V = uv[1] < 0 or uv[1] > 1.0
                if not uv_err_occured and (uv_out_U or uv_out_V):
                    self.report({'WARNING'}, "UV Out of Bounds! Wrapping around...")
                    uv_err_occured = True

                # offset UVs if they're beyond [0.0, 1.0] range
                uv[0] = uv_offset(uv[0]) if uv_out_U else uv[0]
                uv[1] = uv_offset(uv[1]) if uv_out_V else uv[1]
  
                vertex = self.PackVertex(
                    trm_mesh.vertices[loop.vertex_index].co,
                    loop.normal,
                    tex_id,
                    groups,
                    uv
                )
                indices = shader_map[sh_ID][sh_subtype]
                if vertex in vertices:
                    indices.append(vertices.index(vertex))
                else:
                    indices.append(num_vertices)
                    vertices.append(vertex)
                    num_vertices += 1

            # Define Shaders
            

        # GET ELEMENT COUNTS
        num_textures = len(textures)
        num_vertices = len(vertices)

        f = open(filepath, 'wb')

        # TRM\x02 marker
        f.write(pack(">I", 0x54524d02))

        # SHADER DATA
        indices = []
        f.write(pack("<I", len(shader_map)))
        for s in shader_map.keys():
            shd = shader_map[s]
            f.write(shd['pack'])
            for sh_subtype in trm_utils.SHADER_SUBTYPES:
                f.write(pack("<2I", len(indices), len(shd[sh_subtype])))
                indices.extend(shd[sh_subtype])

        num_indices = len(indices)

        # TEXTURES
        f.write(pack("<I", num_textures))
        for tex in textures:
            if 0 <= tex <= 0xffff:
                f.write(pack("<H", tex))
            else:
                self.report({'ERROR'}, "Invalid Material Prefix: %s!" % f'{tex}')
                return {'CANCELLED'}

        # BYTE ALIGN
        while f.tell() % 4: f.write(b"\x00")

        # JOINTS (CURRENTLY UNKNOWN)
        f.write(pack("<I", 0))

        # INDICE & VERTICE COUNTS
        f.write(pack("<2I", num_indices, num_vertices))

        # WRITE INDICES
        f.write(pack("<%dH" % num_indices, *indices))

        # BYTE ALIGN
        while f.tell() % 4: f.write(b"\x00")

        # WRITE VERTICES
        for v in vertices:
            f.write(v)

        f.close()
        print("%d Textures, %d Indices, %d Vertices" % (num_textures, num_indices, num_vertices))
        print("DONE!")
        self.report({'INFO'}, "Export Completed.")

        return {'FINISHED'}
    
    def execute(self, context):
        active_obj = bpy.context.active_object
        selected_objs = bpy.context.selected_objects

        result, trm, obj_copies = self.get_trm(active_obj, selected_objs)
        if result == {'CANCELLED'}:
            return result

        result = self.write_trm_data(context, trm.data, self.filepath)
        self.clean_copies(obj_copies)

        for ob in selected_objs:
            ob.select_set(True)
        bpy.context.view_layer.objects.active = active_obj
        return result

def menu_func_export(self, context):
    self.layout.operator(ExportTRMData.bl_idname, text="Tomb Raider I-III Remastered (.TRM)")

def register():
    bpy.utils.register_class(ExportTRMData)
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)

def unregister():
    bpy.utils.unregister_class(ExportTRMData)
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)
