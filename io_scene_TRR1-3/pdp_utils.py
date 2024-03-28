import bpy, os
import xml.etree.ElementTree as ET
from struct import unpack
from pathlib import Path
from . import bin_parse

TR_ENTITY_NAMES_FILEPATH = "lib/EntityNames.xml"
SKELETON_DATA_FILEPATH = "lib_user/SkeletonData.xml"

def process_pdp(filepath):
    with open(filepath, 'rb') as f:
       
        num_animations =  bin_parse.read_uint32(f)
        f.seek(num_animations * 32, 1)

        num_statechanges =  bin_parse.read_uint32(f)
        f.seek(num_statechanges * 6, 1)

        num_animdispatches =  bin_parse.read_uint32(f)
        f.seek(num_animdispatches * 8, 1)

        num_animcommands =  bin_parse.read_uint32(f)
        f.seek(num_animcommands * 2, 1)

        num_meshtrees =  bin_parse.read_uint32(f)
        # KEEP MESH TREES
        meshtrees = []
        for n in range(num_meshtrees):
            meshtrees.append(bin_parse.read_int32(f))

        num_frames =  bin_parse.read_uint32(f)
        f.seek(num_frames * 2, 1)

        num_models =  bin_parse.read_uint32(f)
        # KEEP MODELS
        models: list[dict] = []
        for n in range(num_models):
            d = unpack('<IHHIIH', f.read(18))
            model = {'ID': d[0], 'num_meshes': d[1], 'starting_mesh': d[2], 'mesh_tree': d[3], 'frame_offset': d[4], 'animation': d[5]}
            # Get only skeletal meshes
            if model['num_meshes'] > 1:
                meshtree_size = model['mesh_tree']+(4*model['num_meshes'])
                model['trees'] = meshtrees[model['mesh_tree']:meshtree_size+1]
                models.append(model)

    return models

def get_game_models(game_dir, game_id=1, game_subdirs=['DATA']):
    game_models: list[dict] = []
    gm_ids = set()
    # filepath = os.path.abspath(os.path.join(game_dir, f'{game_id}/DATA/EMPRTOMB.PDP'))
    for subdir in game_subdirs:
        file_dir = os.path.abspath(os.path.join(game_dir, f'{game_id}/{subdir}'))
        files = Path(file_dir).glob('*.PDP')
        for filepath in files:
            models = process_pdp(filepath)
            # filter out duplicate models by ID
            for model in models:
                if model['ID'] not in gm_ids:
                    game_models.append(model)
                    gm_ids.add(model['ID'])

    game_models.sort(key=lambda gm: gm['ID'])
    return game_models

def get_bone_data(model) -> list:
    bones = [[-1, (0, 0, 0)]]
    stack = [0, 0]
    meshtrees = model['trees']
    tree = 0

    for n in range(1, model['num_meshes']):
        flags = meshtrees[tree]
        x = meshtrees[tree+1]
        y = meshtrees[tree+2]
        z = meshtrees[tree+3]

        previous = stack.pop()
        if flags & 0x01:
            previous = stack.pop()

        bones.append([previous, (x, y, z)])

        if flags & 0x02:
            stack.append(previous)
        stack.append(n)

        tree += 4

    # loop through bones and show thier parent ID, head and tail (assumed) coords
    model['bones'] = []
    for p in range(len(bones)):
        children = 0
        child = -1
        # loop through all the next bones in the list and count them as children when their parent ID matches current ID
        for c in range(p + 1, len(bones)):
            if bones[c][0] == p:
                children += 1
                child = c
                
        bone_data = bones[p]
        # guess and save bone's tail data according to last child bone under it (children == 1 would get first one)
        if children > 0:
            c = bones[child][1]
            bone_data.append((c[0], c[1], c[2]))

        model['bones'].append(bone_data)

    return model['bones']

def xml_write_skeleton(game_dir):
    # Example of the XML structure:
    #
    # <Models>
    #   <Game ID="1">
    #     <Armature m_ID="0" name="Model">
    #         <Bone>
    #         <Data p_ID="-1"/>
    #         <Data type="HEAD" X="0.0" Y="0.0" Z="0.0"/>
    #         <Data type="TAIL" X="0.0" Y="0.0" Z="0.0"/>
    #         </Bone>
    #     </Armature>
    #   </Game>
    # </Models>

    addon_dir = os.path.dirname(__file__)

    game_subdirs = {
        1: ['DATA', 'DATA/UB'],
        2: ['DATA', 'DATA/GM'],
        3: ['DATA', 'DATA/LA', 'CUTS']
    }

    tr_entities_filepath = os.path.join(addon_dir, TR_ENTITY_NAMES_FILEPATH)
    tr_entities_tree = ET.parse(tr_entities_filepath)
    tr_entities_root = tr_entities_tree.getroot()
    
    data_root = ET.Element('Models')
    for g_id in range(1,4):
        data_game = ET.SubElement(data_root, 'Game')
        data_game.set('ID', f'{g_id}')

        models = get_game_models(game_dir, g_id, game_subdirs[g_id])

        for model in models:
            skel = get_bone_data(model)
            tr_entity = tr_entities_root.find("./game/[@ID='%s']/model/[ID='%s']/name" % (g_id, model['ID']))
            model_name = tr_entity.text

            data_arm = ET.SubElement(data_game, 'Armature')
            data_arm.set('m_ID', f'{model["ID"]}')
            data_arm.set('name', model_name)

            for bone in skel:
                elem_bone = ET.SubElement(data_arm, 'Bone')
                elem_bone.set('p_ID', f'{bone[0]}')

                elem_1 = ET.SubElement(elem_bone, 'Data')
                elem_1.set('type', "HEAD")
                elem_1.set('Vector', f"{bone[1]}")

                if len(bone)>2:
                    elem_2 = ET.SubElement(elem_bone, 'Data')
                    elem_2.set('type', "TAIL")
                    elem_2.set('Vector', f"{bone[2]}")

    tree = ET.ElementTree(data_root)
    ET.indent(tree)

    userlib_dir = os.path.join(addon_dir, "lib_user")

    if not os.path.exists(userlib_dir):
        os.makedirs(userlib_dir)

    xml_filepath = os.path.join(addon_dir, SKELETON_DATA_FILEPATH)
    tree.write(xml_filepath, encoding='utf-8', xml_declaration=True)