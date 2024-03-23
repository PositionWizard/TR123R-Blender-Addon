import bpy
from typing import NamedTuple

SHADER_SUBTYPES = ["A", "B", "C"]
"""List of possible TRM shader subtypes: [A, B, C]"""

SHADER_DATA_NAMES = ["Shader Type", "Color 1", "Color 2", "Color 3", "Color 4"]
"""List of TRM shader data names: [Shader Type, Color 1, Color 2, Color 3, Color 4]"""

SHADERNODE_NAME_MAIN = "TRM_MainShader"
SHADERNODE_NAME_INST = "TRM_ShaderInstance"

class TRM_ShaderIndices(NamedTuple):
    """Vertex Indices tuple[offset, length] for Shader data of TRM file"""
    offset: int = 0
    length: int  = 0

class TRM_Shader(NamedTuple):
    """Shader data for TRM file"""
    type: int = 0
    """Type or flags(?) values seen: 0, 2, 3, 6, 12, 14, 18, 19"""
    data1: list = [0.0, 0.0, 0.0, 0.0]
    """These unknowns sometimes look like floats"""
    data2: list = [0.0, 0.0, 0.0, 0.0]
    """Could be color values or multipliers"""
    data3: list = [0.0, 0.0, 0.0, 0.0]
    data4: list = [0.0, 0.0, 0.0, 0.0]
    indices1: TRM_ShaderIndices = TRM_ShaderIndices()
    """Faces to be drawn regularly(?)"""
    indices2: TRM_ShaderIndices = TRM_ShaderIndices()
    """Faces to be drawn with special shading(?)"""
    indices3: TRM_ShaderIndices = TRM_ShaderIndices()
    """Faces to be drawn with special shading(?) adds fixed transparency"""

def str_to_int(value):
    """Try getting int from string. If string is invalid, return None"""
    try:
        return int(value)
    except ValueError:
        return None
    
def rgba_to_int(rgba):
    r = round(rgba[0] * 255)
    g = round(rgba[1] * 255) << 8
    b = round(rgba[2] * 255) << 16
    a = round(rgba[3] * 255) << 24
    return (r + g + b + a)
    
def create_nodegroup(nodes, node_tree, name="Group"):
    group_node: bpy.types.ShaderNodeGroup = nodes.new('ShaderNodeGroup')
    group_node.name = name
    group_node.node_tree = node_tree
    return group_node
    
def connect_nodes(node_tree:bpy.types.NodeTree, in_node, in_socket:str|int, out_node, out_socket:str|int):
    node_tree.links.new(in_node.inputs[in_socket], out_node.outputs[out_socket])

def space_out_nodes(nodes, offset=50):
    for i, n in enumerate(nodes):
        n: bpy.types.ShaderNode
        if i>0:
            n.location.x = prev_n_locX+prev_n_width+offset
        prev_n_locX = n.location.x
        prev_n_width = n.width

def create_TRM_shader_inst_nodegroup(nodes, node_tree):
    shader_inst_node = create_nodegroup(nodes, node_tree, name=SHADERNODE_NAME_INST)
    shader_inst_node.label = "TRM Shader Instance"
    shader_inst_node.width *= 2.2

    return shader_inst_node

def create_TRM_shader_inst(shader:bpy.types.NodeTree, inst_name:str, shader_info=TRM_Shader(), sh_id=0):
    """Create top-level NodeGroup Instance with inputs for BaseColor, Alpha and IsGlossy bool\n
    Returns a NodeTree with name: '{inst_name}' when sh_id >= -1 or '{inst_name} [index]' when sh_id == -1"""

    if sh_id == -1:
        n_count = 0
        for n in bpy.data.node_groups:
            if inst_name in n.name:
                n_count += 1
        sh_id = n_count
        inst_name = f"{inst_name} {sh_id}"

    shader_inst = bpy.data.node_groups.new(name=inst_name, type='ShaderNodeTree')
    if bpy.app.version >= (4,0):
        node_color = shader_inst.interface.new_socket(name="Base Color", socket_type="NodeSocketColor")
        node_alpha = shader_inst.interface.new_socket(name="Alpha", socket_type="NodeSocketFloat")
        node_alpha.subtype = 'FACTOR'
        node_shader = shader_inst.interface.new_socket(name="Shader", in_out="OUTPUT", socket_type="NodeSocketShader")
    else:
        node_color = shader_inst.inputs.new(name="Base Color", type="NodeSocketColor")
        node_alpha = shader_inst.inputs.new(name="Alpha", type="NodeSocketFloatFactor")
        node_shader = shader_inst.outputs.new(name="Shader", type="NodeSocketShader")
    node_color.default_value = [1.0, 0.0, 1.0, 1.0] # Default color obviously has to be the most infuriating one to every game developer out there: Magenta
    node_alpha.default_value = 1.0
    node_alpha.min_value = 0.0
    node_alpha.max_value = 1.0

    # Create nodes
    group_in = shader_inst.nodes.new('NodeGroupInput')
    group_out = shader_inst.nodes.new('NodeGroupOutput')
    shader_node = create_nodegroup(shader_inst.nodes, shader, SHADERNODE_NAME_MAIN)
    shader_node.width *= 1.5
    shader_node_frame = shader_inst.nodes.new('NodeFrame')
    shader_node_frame.label = f"TRM Shader: {sh_id}"
    shader_node.parent = shader_node_frame
    space_out_nodes([group_in, shader_node, group_out])

    # Import shader values
    shader_node.inputs[SHADER_DATA_NAMES[0]].default_value = shader_info.type
    shader_node.inputs[SHADER_DATA_NAMES[1]].default_value = shader_info.data1
    shader_node.inputs[SHADER_DATA_NAMES[2]].default_value = shader_info.data2
    shader_node.inputs[SHADER_DATA_NAMES[3]].default_value = shader_info.data3
    shader_node.inputs[SHADER_DATA_NAMES[4]].default_value = shader_info.data4

    # Connect Group Inputs to the Master Shader NodeGroup and its output to Group Output
    connect_nodes(shader_inst, shader_node, node_color.name, group_in, node_color.name)
    connect_nodes(shader_inst, shader_node, node_alpha.name, group_in, node_alpha.name)
    connect_nodes(shader_inst, group_out, node_shader.name, shader_node, node_shader.name)

    return shader_inst

def find_TRM_shader_inst(mat:bpy.types.Material) -> bpy.types.ShaderNodeGroup:
    inst_node = None
    if mat and mat.use_nodes:
        shader_inst_gr = mat.node_tree.nodes.get(SHADERNODE_NAME_INST.split('.',1)[0])
        if shader_inst_gr:
            inst_node = shader_inst_gr.node_tree.nodes.get(SHADERNODE_NAME_MAIN.split('.',1)[0])

    return inst_node

def find_TRM_shader() -> bpy.types.ShaderNodeTree:
    shader_node = None
    for ntree in bpy.data.node_groups:
        if 'TRM Master Shader' in ntree.name:
            shader_node = ntree
            break
    
    return shader_node

def get_TRM_shader_inst(shader:bpy.types.NodeTree, parent_name:str, shader_info=TRM_Shader(), sh_id=0):
    """Get or create top-level NodeGroup Instance with inputs for BaseColor, Alpha and IsGlossy bool"""
    inst_name = f"{parent_name}: Shader Instance {sh_id}"
    if inst_name in bpy.data.node_groups:
        shader_inst = bpy.data.node_groups.get(inst_name)
    else:
        shader_inst = create_TRM_shader_inst(shader, inst_name, shader_info, sh_id)

    return shader_inst
    
def get_TRM_shader():
    """Get or create a Master Shader NodeGroup with inputs for all TRM shader variables and inputs to pass on data from instances"""
    sh_name = f"TRM Master Shader"
    if sh_name in bpy.data.node_groups:
        shader = bpy.data.node_groups.get(sh_name)
    else:
        shader = bpy.data.node_groups.new(name=sh_name, type='ShaderNodeTree')
        if bpy.app.version >= (4,0):
            if bpy.app.version < (4,1):
                node_shadertype = shader.interface.new_socket(name=SHADER_DATA_NAMES[0], socket_type="NodeSocketFloat")
            else:
                node_shadertype = shader.interface.new_socket(name=SHADER_DATA_NAMES[0], socket_type="NodeSocketInt")

            node_color1 = shader.interface.new_socket(name=SHADER_DATA_NAMES[1], socket_type="NodeSocketColor")
            node_color2 = shader.interface.new_socket(name=SHADER_DATA_NAMES[2], socket_type="NodeSocketColor")
            node_color3 = shader.interface.new_socket(name=SHADER_DATA_NAMES[3], socket_type="NodeSocketColor")
            node_color4 = shader.interface.new_socket(name=SHADER_DATA_NAMES[4], socket_type="NodeSocketColor")
            node_basecolor = shader.interface.new_socket(name="Base Color", socket_type="NodeSocketColor")
            node_alpha = shader.interface.new_socket(name="Alpha", socket_type="NodeSocketFloat")
            node_alpha.subtype = 'FACTOR'
            node_shader = shader.interface.new_socket(name="Shader", in_out="OUTPUT", socket_type="NodeSocketShader")
        else:
            node_shadertype = shader.inputs.new(name=SHADER_DATA_NAMES[0], type="NodeSocketInt")
            node_color1 = shader.inputs.new(name=SHADER_DATA_NAMES[1], type="NodeSocketColor")
            node_color2 = shader.inputs.new(name=SHADER_DATA_NAMES[2], type="NodeSocketColor")
            node_color3 = shader.inputs.new(name=SHADER_DATA_NAMES[3], type="NodeSocketColor")
            node_color4 = shader.inputs.new(name=SHADER_DATA_NAMES[4], type="NodeSocketColor")
            node_basecolor = shader.inputs.new(name="Base Color", type="NodeSocketColor")
            node_alpha = shader.inputs.new(name="Alpha", type="NodeSocketFloatFactor")
            node_shader = shader.outputs.new(name="Shader", type="NodeSocketShader")

        node_shadertype.default_value = 0
        node_shadertype.min_value = 0

        node_color1.default_value, node_color2.default_value, node_color3.default_value, node_color4.default_value = [[0.0, 0.0, 0.0, 1.0]]*4

        node_alpha.default_value = 1.0
        node_alpha.min_value = 0.0
        node_alpha.max_value = 1.0

        # Create nodes
        group_in = shader.nodes.new('NodeGroupInput')
        group_out = shader.nodes.new('NodeGroupOutput')
        shader_bsdf: bpy.types.ShaderNodeBsdfPrincipled = shader.nodes.new('ShaderNodeBsdfPrincipled')

        space_out_nodes([group_in, shader_bsdf, group_out])

        # Connect Group Inputs to the Master Shader NodeGroup and its output to Group Output
        connect_nodes(shader, shader_bsdf, 'Base Color', group_in, node_basecolor.name)
        connect_nodes(shader, shader_bsdf, 'Alpha', group_in, node_alpha.name)
        connect_nodes(shader, group_out, node_shader.name, shader_bsdf, 'BSDF')

    return shader