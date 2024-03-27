import bpy, math, bmesh, time, os
from struct import pack

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
from . import utils as trm_utils
from .bin_parse import TRM_HEADER, TRM_FORMAT, TRM_ANIM_FORMAT

class TRM_OT_ExportTRM(Operator, ExportHelper):
    """Save object as TRM file"""
    bl_idname = "io_tombraider123r.trm_export"
    bl_label = "Export TRM"

    filename_ext = f"{TRM_FORMAT}"

    filter_glob: StringProperty(
        default=f"*{TRM_FORMAT}",
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
        description="Apply object location, rotation and scale.\n\n"
                    "Broken with parented objects!",
        default=True,
    )

    export_anim: BoolProperty(
        name="Export Animated",
        description=f"Export face animation data using a path to '{TRM_ANIM_FORMAT}' file.\n\n"
                    f"Use only with {TRM_FORMAT} files that have extracted this data!!!",
        default=False,
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
        
            if len(objs)>1:
                bpy.ops.object.join()
        else:
            if not act_obj or act_obj.type != 'MESH':
                self.report(err_call)
                return result
            obj = self.copy_object(act_obj)
            self.prepare_mesh(obj)
            objs = [obj]
            
        trm = bpy.context.active_object
        trm.data.calc_normals_split()
        if trm.vertex_groups:
            bpy.ops.object.vertex_group_normalize_all(group_select_mode='ALL', lock_active=False)

        if self.apply_transforms:
            trm.data.transform(trm.matrix_world)
            trm.matrix_local.identity()
            trm.data.update()

        result = {'PASS_THROUGH'}, trm, objs
        return result
    
    # VERTEX PACKER
    def PackVertex(self, coordinate: list, normal, texture, groups, uv):
        # negate and pack normals in XZY order
        nrs = normalFloat2Byte(-normal[0], -normal[2], -normal[1])

        # vertices in XZY order
        vs = []
        for i in [0, 2, 1]:
            vs.append(-coordinate[i] * self.scale)
            
        # vertex groups and weights
        gs, ws = [0, 0, 0], [255, 0, 0]
        for i in range(3):
            if len(groups) > i:
                gr = groups[i].group
                w = round(groups[i].weight * 255)
                gs[i], ws[i] = gr, w

        # texture and UV
        tex = texture + 1
        tu = round(uv[0] * 255)
        tv = 255 - round(uv[1] * 255)
        return pack("<fff12B", *vs, *nrs, tex, *gs, tu, *ws, tv)
    
    def uv_offset(self, x):
        if x > 0.0:
            offset = -(math.ceil(x/1.0)-1)
        else:
            offset = -math.floor(x/1.0)
        return x+offset
    
    def save_shader_data(self, shader_map, id=0, data = [0,0,0,0,0]):
        shader_map[id] = {'pack': pack("<5I", *data)}
        for st in trm_utils.SHADER_SUBTYPES:
            shader_map[id][st] = []
        
        return shader_map
    
    def write_trm_data(self, context, trm: bpy.types.Object, filepath):
        trm_mesh: bpy.types.Mesh = trm.data

        textures = []
        shader_map = {}
        mat_map = []
        mat_i = 0
        for mat in trm_mesh.materials:
            mat_info = {'ShaderID': 0,
                        'ShaderSubtype': trm_utils.SHADER_SUBTYPES[0],
                        'TexID': 8000}
            if mat:
                # Material name structure = [TextureID, ShaderID, ShaderSubtype, ...]
                mat_name_slice = mat.name.split('_')
                tex_id = trm_utils.str_to_int(mat_name_slice[0])
                if tex_id == None:
                    tex_id = mat_info['TexID']
                    self.report({'WARNING'}, f'"{mat_name_slice[0]}" in material name is not a texture ID! Falling back to default: "{tex_id}"')
                # Get correct material slot indices without duplicates for same textures (shader support)
                if tex_id in textures:
                    mat_info['TexID'] = textures.index(tex_id)
                else:
                    mat_info['TexID'] = len(textures)
                    textures.append(tex_id)

                # Get Shader info from materials, skipping cubemaps (they don't have it)
                if len(mat_name_slice)>1:
                    sh_ID = trm_utils.str_to_int(mat_name_slice[1])
                    if sh_ID == None or not 0 <= sh_ID <= 0xffff:
                        self.report({'WARNING'}, f'"{mat_name_slice[1]}" in material name is not a Shader Instance number! Falling back to default: "{mat_info["ShaderID"]}"')
                        mat_map.append(mat_info)
                        mat_i += 1
                        continue

                    if len(mat_name_slice)>2 and mat_name_slice[2] in trm_utils.SHADER_SUBTYPES:
                        mat_info['ShaderSubtype'] = mat_name_slice[2]

                    shadernode_inst = trm_utils.find_TRM_shader_node(mat)
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
                            shader_map = self.save_shader_data(shader_map, sh_ID, sh_data)

                    mat_info['ShaderID'] = sh_ID
                else:
                    self.report({'WARNING'}, f'"{mat.name}" material has no Shader definitions ([texID]_[shaderID]_["B"/"C"]), falling back to default..."')
                
            mat_map.append(mat_info)
            mat_i += 1

        # fallback to a default shader
        if not shader_map:
            shader_map = self.save_shader_data(shader_map)

        # PREPARE INDICES & VERTICES DATA
        vertices = []
        num_vertices = len(vertices)
        uvs = trm_mesh.uv_layers.active
        v_order = [0, 2, 1]

        uv_err_occured = False
        for p in trm_mesh.polygons:
            mat_info = mat_map[p.material_index]
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
                uv[0] = self.uv_offset(uv[0]) if uv_out_U else uv[0]
                uv[1] = self.uv_offset(uv[1]) if uv_out_V else uv[1]
  
                vertex = self.PackVertex(
                    trm_mesh.vertices[loop.vertex_index].co,
                    loop.normal,
                    mat_info['TexID'],
                    groups,
                    uv
                )
                indices = shader_map[mat_info['ShaderID']][mat_info['ShaderSubtype']]
                if vertex in vertices:
                    indices.append(vertices.index(vertex))
                else:
                    indices.append(num_vertices)
                    vertices.append(vertex)
                    num_vertices += 1

        # GET ELEMENT COUNTS
        num_textures = len(textures)
        num_vertices = len(vertices)

        f = open(filepath, 'wb')

        # TRM\x02 marker
        f.write(pack(">I", TRM_HEADER))

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

        # BONE ANIM DATA INJECTION
        num_anim_bones = 0
        if self.export_anim:
            filepath_split = self.filepath.rsplit('\\', 1)
            filename = filepath_split[-1].removesuffix(self.filename_ext)
            # print(f'Directory: {filepath_split[0]}\\')
            # print(f'Filename: {filename}')
            trm_anim_filepath = f'{filepath_split[0]}\\{filename}{TRM_ANIM_FORMAT}'
            # print(trm_anim_filepath)
            if os.path.exists(trm_anim_filepath):
                print("-------------------------------------------------")
                print(f'INJECTING ANIM DATA FROM "{trm_anim_filepath}" FILE...')
                from . import bin_parse
                with open(trm_anim_filepath, 'rb') as f_anim:
                    # check for TRM\x02 marker
                    if bin_parse.is_TRM_header(f_anim):
                        num_anim_bones = bin_parse.read_uint32(f_anim)
                        if num_anim_bones > 0:
                            anim_bones = tuple(bin_parse.read_float_tuple(f_anim, 12) for n in range(num_anim_bones))
                                
                            num_anim_unknown2 = bin_parse.read_uint32(f_anim)
                            anim_unknown2 = tuple(bin_parse.read_uint32_tuple(f_anim, 2) for n in range(num_anim_unknown2))
                            
                            num_anim_unknown3 = bin_parse.read_uint32(f_anim)
                            anim_unknown3 = bin_parse.read_uint32_tuple(f_anim, num_anim_unknown3) # Frame numbers?
                            
                            num_anim_unknown4 = bin_parse.read_ushort16(f_anim)
                            num_anim_unknown5 = bin_parse.read_ushort16(f_anim)  # this is unused, still unknown
                            anim_unknown4 = tuple(bin_parse.read_float_tuple(f_anim, 12) for n in range(num_anim_unknown3 * num_anim_unknown4))

                            f.write(pack("<I", num_anim_bones))
                            f.write(pack("<%df" % (12*num_anim_bones), *[x for y in anim_bones for x in y]))
                            f.write(pack("<I", num_anim_unknown2))
                            f.write(pack("<%dI" % (2*num_anim_unknown2), *[x for y in anim_unknown2 for x in y]))
                            f.write(pack("<I", num_anim_unknown3))
                            f.write(pack("<%dI" % num_anim_unknown3, *anim_unknown3))
                            f.write(pack("<H", num_anim_unknown4))
                            f.write(pack("<H", num_anim_unknown5))
                            f.write(pack("<%df" % (12*num_anim_unknown3 * num_anim_unknown4), *[x for y in anim_unknown4 for x in y]))

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
                    else:
                        self.report({'ERROR'}, f'"{filename}{TRM_ANIM_FORMAT}" file is not a {TRM_ANIM_FORMAT} file! Skipping anim data...')
                del bin_parse
            else:
                self.report({'WARNING'}, f'{TRM_ANIM_FORMAT} file not found at "{trm_anim_filepath}"! Skipping anim data...')

        # BONE ANIM DATA FALLBACK (CURRENTLY UNKNOWN)
        if num_anim_bones == 0:
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
        print("%d Textures, %d Indices, %d Vertices, %d Bones" % (num_textures, num_indices, num_vertices, len(trm.vertex_groups)))
        print("DONE!")

        return {'FINISHED'}
    
    def execute(self, context):
        start_time = time.process_time()
        self.report({'INFO'}, "Exporting TRM...%r" % self.filepath)

        active_obj = bpy.context.active_object
        selected_objs = bpy.context.selected_objects

        
        result, trm, obj_copies = self.get_trm(active_obj, selected_objs)
        if result == {'CANCELLED'}:
            return result

        try:
            result = self.write_trm_data(context, trm, self.filepath)
        except:
            result = {'CANCELLED'}

        self.clean_copies(obj_copies)

        for ob in selected_objs:
            ob.select_set(True)
        bpy.context.view_layer.objects.active = active_obj

        end_time = time.process_time() - start_time
        if result == {'FINISHED'}:
            self.report({'INFO'}, "Export finished in %.4f sec." % (end_time))
        return result

def executre(self, context):
    return {'FINISHED'}

def menu_func_export(self, context):
    self.layout.operator(TRM_OT_ExportTRM.bl_idname, text=f"Tomb Raider I-III Remastered ({TRM_FORMAT})")

def register():
    bpy.utils.register_class(TRM_OT_ExportTRM)
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)

def unregister():
    bpy.utils.unregister_class(TRM_OT_ExportTRM)
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)
