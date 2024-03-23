# v0.4

import bpy, math
from struct import pack
import bmesh

def NormalFLOAT2BYTE(x, y, z):
    length = math.sqrt((x * x) + (y * y) + (z * z))
    x = (x / length) * 126
    y = (y / length) * 126
    z = (z / length) * 126
    return (round(x + 127), round(y + 127), round(z + 127))

from bpy_extras.io_utils import ExportHelper
from bpy.props import StringProperty, BoolProperty, FloatProperty
from bpy.types import Operator
from mathutils import Vector

class ExportTRMData(Operator, ExportHelper):
    """Save object as TRM file"""
    bl_idname = "io_tombraider.trm_export"
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

    apply_scale: BoolProperty(
        name="Apply Mesh Scale",
        description="Exports objects with visually the same scale.\n"
                    "Disable if you want the exported object's scale to be reset to 1.0",
        default=True,
    )

    def execute(self, context):
        active_obj = bpy.context.active_object
        selected_objs = bpy.context.selected_objects

        if not self.act_only:
            objs = [self.copy_objects(o) for o in bpy.context.selected_objects if o.type == 'MESH']
            if not objs:
                self.report({'ERROR'}, "Select a 3D Object!")
                return {'CANCELLED'}

            for obj_c in objs:
                self.prepare_mesh(obj_c)
                obj_c.select_set(True)
        
            bpy.ops.object.join()
        else:
            if not active_obj or active_obj.type != 'MESH':
                self.report({'ERROR'}, "Select a 3D Object!")
                return {'CANCELLED'}
            obj = self.copy_objects(active_obj)
            self.prepare_mesh(obj)
            
        trm = bpy.context.active_object

        if self.apply_scale:
            trm_scale = trm.scale
        else:
            trm_scale = Vector((1.0, 1.0, 1.0))

        result = self.write_trm_data(context, trm.data, trm_scale, self.filepath)

        if not self.act_only:
            for obj_c in objs:
                bpy.data.meshes.remove(obj_c.data)
            for ob in selected_objs:
                ob.select_set(True)
        else:
            bpy.data.meshes.remove(trm.data)
            active_obj.select_set(True)
        bpy.context.view_layer.objects.active = active_obj
        return result
    
    def copy_objects(self, obj: bpy.types.Object):
        # COPY OBJECT AND MESH
        obj_mesh = obj.data.copy()
        obj_c = bpy.types.Object(obj.copy())
        obj_c.data = obj_mesh
        bpy.context.view_layer.layer_collection.collection.objects.link(obj_c)
        obj.select_set(False)

        if bpy.context.active_object == obj:
            bpy.context.view_layer.objects.active = obj_c

        return obj_c
    
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
    
    def write_trm_data(self, context, trm_mesh: bpy.types.Mesh, ob_scale: Vector, filepath):
        print("EXPORTING...")

        trm_mesh.calc_normals_split()

        # VERTEX PACKER
        def PackVertex(coordinate, normal, texture, groups, uv):
            vx = -coordinate.x * self.scale * ob_scale.x
            vy = -coordinate.z * self.scale * ob_scale.y
            vz = -coordinate.y * self.scale * ob_scale.z
            nr = NormalFLOAT2BYTE(-normal[0], -normal[2], -normal[1])
            nx = nr[0]
            ny = nr[1]
            nz = nr[2]
            tex = texture + 1
            tu = int(uv[0] * 255)
            tv = 255 - int(uv[1] * 255)
            if len(groups) > 0:
                g1 = groups[0].group
                w1 = int(groups[0].weight * 255)
            else:
                g1 = 0
                w1 = 255
            if len(groups) > 1:
                g2 = groups[1].group
                w2 = int(groups[1].weight * 255)
            else:
                g2 = 0
                w2 = 0
            if len(groups) > 2:
                g3 = groups[2].group
                w3 = int(groups[2].weight * 255)
            else:
                g3 = 0
                w3 = 0
            return pack("<fff12B", vx,vy,vz, nx,ny,nz, tex, g1,g2,g3, tu, w1,w2,w3, tv)

        # PREPARE INDICES & VERTICES DATA
        indices = []
        vertices = []

        uvs = trm_mesh.uv_layers.active
        v_order = [0, 2, 1]

        for p in trm_mesh.polygons:
            for i in v_order:
                loop = trm_mesh.loops[p.loop_indices[i]]
                groups = trm_mesh.vertices[loop.vertex_index].groups
                if len(groups) > 3:
                    self.report({'ERROR'}, "Maximum 3 Joints Allowed per Vertex!")
                    return {'CANCELLED'}
                uv = uvs.data[p.loop_indices[i]].uv
                if uv[0] < 0 or uv[0] > 1.0 or uv[1] < 0 or uv[1] > 1.0:
                    self.report({'ERROR'}, "UV Out of Bounds!")
                    return {'CANCELLED'}
                vertex = PackVertex(
                    trm_mesh.vertices[loop.vertex_index].co,
                    loop.normal,
                    p.material_index,
                    groups,
                    uv
                )
                if vertex in vertices:
                    indices.append(vertices.index(vertex))
                else:
                    indices.append(len(vertices))
                    vertices.append(vertex)

        # GET ELEMENT COUNTS
        num_textures = len(trm_mesh.materials)
        num_indices = len(indices)
        num_vertices = len(vertices)
        print("%d Textures, %d Indices, %d Vertices" % (num_textures, num_indices, num_vertices))

        f = open(filepath, 'wb')

        # TRM\x02 marker
        f.write(pack(">I", 0x54524d02))

        # SHADER DATA FILL
        f.write(pack("<12I", 1, 0, 0, 0, 0, 0, 0, num_indices, num_indices, 0, num_indices, 0))

        # TEXTURES
        f.write(pack("<I", num_textures))
        for n in range(num_textures):
            mat = trm_mesh.materials[n]
            tex = int(mat.name.split("_",1)[0])
            if 0 <= tex <= 0xffff:
                f.write(pack("<H", tex))
            else:
                self.report({'ERROR'}, "Invalid Material Name: %s!" % mat.name)
                return {'CANCELLED'}

        # BYTE ALIGN
        while f.tell() % 4: f.write(b"\x00")

        # UNKNOWN and INDICE & VERTICE COUNTS
        f.write(pack("<3I", 0, num_indices, num_vertices))

        # WRITE INDICES
        f.write(pack("<%dH" % num_indices, *indices))

        # BYTE ALIGN
        while f.tell() % 4: f.write(b"\x00")

        # WRITE VERTICES
        for n in range(len(vertices)):
            f.write(vertices[n])

        f.close()
        print("DONE!")
        self.report({'INFO'}, "Export Completed.")

        return {'FINISHED'}

def menu_func_export(self, context):
    self.layout.operator(ExportTRMData.bl_idname, text="Tomb Raider I-III Remastered (.TRM)")

def register():
    bpy.utils.register_class(ExportTRMData)
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)

def unregister():
    bpy.utils.unregister_class(ExportTRMData)
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)
