# TR123R Blender Addon
**[Blender 3.6 - 4.1](https://www.blender.org)** Import/Export addon for **[Tomb Raider I-III Remastered](https://store.steampowered.com/app/2478970)** game **.TRM** files.

Addon originally started by [MuruCoder](https://github.com/MuruCoder) with my additions, other improvements and structure changes.
  
You can reach the original creator at **[TombRaiderForums](https://www.tombraiderforums.com/showthread.php?t=228896)** thread. There you can also find previous addon versions and possibly catch me discussing.

## Table of Contents
- [Features](#features)
- [How-to](#how-to)
    - [Texture Import](#texture-import)
    - [Armature Import](#armature-import)
        - [Adding support for other TRMs](#adding-support-for-other-trms)
    - [Shader Setup](#shader-setup)
        - [Material Name Structure](#material-name-structure)
        - [Shader Instances](#shader-instances)
        - [TRM Shader Settings](#trm-shader-settings)
    - [UV Tool](#uv-tool)
        - [Options](#options)
    - [Face Animation Data](#face-animation-data)
    - [Photo Mode Poses](#photo-mode-poses)
        - [Load](#load)
        - [Save](#save)
        - [Switch State](#switch-state)
    - [Skeleton Generator](#skeleton-generator)

## Features
- Import/Export of .TRM files (File->Import/Export->Tomb Raider I-III Remastered (.TRM))
- Import/Export of Lara's Photo Mode Poses
- Importing Armatures
- Importing multiple TRM files
- Exporting mulitple objects to a single TRM file
- Converting textures from DDS to PNG on import
- PNG tetxure import without conversion
- Importing, editing and exporting Shader settings for materials
- Tool for quantizing UVs to 8-bits precision
- Option to auto apply modifiers on export
- Option to auto merge meshes by on UV seams on import
- Extracting and injecting face animation data for "HEAD" TRMs

## How-to
### Texture Import
The game stores textures in a compressed DDS format that needs to be converted first in order to be imported and displayed in Blender. This requires an external tool called **texconv.exe** which the addon operates on.

The file can be downloaded from Microsoft's GitHub page, which can be quickly accessed from Addon's Preferences window. Once you download it, you need to provide a path to the texconv.exe in the **DDS Converter** field.

![texconv](https://github.com/PositionWizard/TR123R-Blender-Addon/assets/89351809/339652d6-0354-4705-9124-fa2f127fbe9e)

Optionally, you can provide a path to a custom folder in **Converted Directory** field, where the converter will save the PNGs to. Leaving it blank will save PNGs inside a new folder in TEX directory for a game that the texture is from (e.g. "1/TEX/PNGs/"). If PNGs are present in the Converted Directory, they will take priority for the import. Each game texture is saved in its respective folder and will be used based on which game you are importing from. This can be overriden by moving a texture to the main Converted Directory folder, which will always take priority instead.

**Game Directory** is the main directory of the game (same folder "tomb123.exe" is in) and can be used to look for the textures when a .TRM is imported outside the game files. Leaving it blank requires .TRM files and textures to be in their original locations for them to be found during import.

To import textures along with a .TRM file, just enable **Use Textures** option in the Import TRM file selection window.

If the **Game Directory** is provided and .TRM file is being imported outside of the game files, there will be an additional option to choose what game to search the textures from.

- **I-III**: game number the model is from (and textures are most likely in)
- **Relative**: will look for textures in relation to an imported .TRM file location
    - this requires the same folder structure relation as in the game files for it to work
    - this option will be forced if **Game Directory** path in Addon's Preferences is empty

![import tex](https://github.com/PositionWizard/TR123R-Blender-Addon/assets/89351809/b7694e34-ca7a-4874-84ed-ea4b7d2a6c5f)

### Armature Import
You can choose to import Armatures along with TRM files by setting a flag in the TRM Import window, called "Import Armature".

Some other options become available once the flag is enabled:
- **Force Connect Bones**: will try to connect bones to one of their children (can be inaccurate and unintuitive at times, so keep that in mind)
- **Auto Bone Orientation**: tries to automatically point bones in the same direction their parent is pointing at, which can look weird on things like claws, jaws, ears, etc, as it was more designed to help in displaying head, hand and foot bones
    - available only once **Force Connect Bones** is enabled
- **Game**: works exactly the same as option for [Texture Import](#texture-import) - allows to choose a game number or relative path to the TRM file in order to specify what game should the armature be imported from.
    - different games can use different skeletons for visibly the same or similar model or TRM name
    - Armatures cannot be imported without either importing directly from original game files or specifying **Game Directory** in the addon's preferences

Not all Armatures can be imported yet, as this would require mapping all TRM names to the correct Entities for each game. The framework already supports looking for specific TRM names for a specific game but the table that it's using to look them up isn't entirely prepared yet. Some models like Lara's OUTFITs, HANDS and OUTFIT_HAIR are already set up but the rest of the names need to be manually updated.

#### Adding support for other TRMs
If anybody wants to contribute and add support for importing more Armatures, the addon has an XML file with entity names that can be modified, which should automatically enable import for updated names. The file can be found in the addon's directory at "%appdata%\Blender Foundation\Blender\4.1\scripts\addons\io_scene_TRR1-3\lib\TRM_Names.xml". There you can find Entity names for each game taken from [TRosettaStone3](https://opentomb.github.io/TRosettaStone3/trosettastone.html#_entity_types) website on reverse-engineering and documentation of classic Tomb Raider games. Those names need to be updated with their respecitve .TRM filenames, similarly to the model name "OUTFIT_HAIR" of ID="2" for game ID="2" or game ID="3".

Be sure to run **Generate Skeleton Data** operator in addon's preferences after modifiactions to update the internal skeleton data and take effect on importing TRMs (more on this in [Skeleton Generator](#skeleton-generator) section).

Remember you can find me in the **[TombRaiderForums](https://www.tombraiderforums.com/showthread.php?t=228896)** thread! You can share your edits there and let me know, so I can update the file in the main repository here.

### Shader Setup
Imported .TRM models will already have a proper Shader setup for their Materials but this can also be configured for new Materials as well. To get desired results, there are a few technicalities and rules to follow.

#### Material Name Structure
Material name has a specific structure that needs to be setup correctly in order for the model to be properly displayed in game.
The structure goes as follows - each part is separated with a "_" character and they consist of:
1. Texture ID - a number that represents a texture name from game's TEX folder (e.g. 5021 is a Pistols texture)
2. Shader Instance ID - number of a Shader Instance that this Material is using
    - multiple Materials can be using the same Shader Instance
3. Shader Subtype - either 'A', 'B' or 'C' character which defines a type of surface for polygons
    - 'A' is a default type and can be ommitted from the name
    - multiple Materials can be using the same Shader Subtype
    - much is still unknown but 'B' and 'C' are sometimes used for transparency effects
4. Game ID - optional suffix if textures are imported (e.g. "_Game-I", "_Game-III")

Here are some examples of possible naming combinations:
- "8004_0"
- "234_1_B"
- "9016_4_C_Game-II"
- "2137_2_Game-I"

#### Shader Instances
Each Material can have its own Shader Instance inherited from the Main TRM Shader. Instances hold settings like Shader Type, Cubemap pointer, Roughness and other unknown data. Multiple Materials can use the same Shader Instance, thus sharing the exact same settings.

TRM Shader and Instances can be created for Materials that weren't imported from the game. This can be done in "Propeties Window -> Materials Tab -> Surface -> TRM Shader Settings"

![Shader Create](https://github.com/PositionWizard/TR123R-Blender-Addon/assets/89351809/f309169c-366f-4352-801c-0cd03953ad39)

Create TRM Shader button will create a main TRM Shader Node Group in the Blender's file and a Shader Instance for currently active Material. At the same time, Material's name will be updated with a Shader Instance ID, which starts at 0.

There can also be a situation when main TRM Shader Node Group already exists and instead you'll be prompted to either Add Existing Shader Instance or Create New Shader Instance.

- **Add Existing Shader Instance**: choose and add an existing Shader Instance node that's present in this Blender file. You will be able to see a node called "TRM Shader" but DO NOT use it! It's for internal use only!
- **Create New Shader Instance**: create a new Shader Instance with a next available ID

![Shader Exists](https://github.com/PositionWizard/TR123R-Blender-Addon/assets/89351809/aae73645-c141-4991-8244-0c6e2bb30a84)

After it's created, Surface panel should change, showing "Surface", "Base Color" and "Alpha" inputs, and shader settings should appear under TRM Shader Settings panel.

- **Surface**: a Shader Instance node with an ID, that should reflect an ID in the Materials' name
- **Base Color**: a default color for display only, meant for a texture image to be plugged in
- **Alpha**: a display-only Alpha slider for previewing transparent images with Alpha channel, plugged into **Base Color** input

![Shader Surface](https://github.com/PositionWizard/TR123R-Blender-Addon/assets/89351809/1c804782-0872-4366-8b53-8450b66702ed)

#### TRM Shader Settings
Shader settings are bound to a specific TRM Shader Instance node. If the same node is used on another Material, it will share those settings. Creating and assigning another Shader Instance will allow to set up various materials differently but will create new Shader definitions internally for the game.

- **Swap Shader Instance**: change Shader Instance for another one that exists in this Blender file. You will be able to see a node called "TRM Shader" but DO NOT use it! It's for internal use only!
- **Create New Shader Instance**: create a new Shader Instance with a next available ID

Note: If you wish to choose another Shader Instance, do NOT change Surface input's reference or name manually as it can break things for export!!! Use one of the provided buttons instead!

Shader Instance data:
- **Shader Type**: a type of Shader for this Instance
    - their names are guessed and there are multiple to choose from for convenience
    - none of these are set in stone, names and their properties are just guessed based on behaviour in game, if you know more, feel free to share your research on TR Forums
    - choosing "Other" will allow to experiment with the Index number, as anything beyond what's in the list, isn't used in the game
- **Color 1/2/3/4**: unknown data values represented as Color type, sometimes swapped for another input if Shader Type's behaviour is known
- **Cubemap ("Glossy" Only)**: a material slot for this mesh to be used as a cubemap texture
    - option only available with Shader Type 3 ("Glossy")
    - cubemap is an environment texture that's used to display fake reflections for the surface
    - will only use a texture defined in Material's name and that material doesn't need a Shader Instance
    - using self material (leaving it be) will use a different environment texture based on current level/area in the game
- **Roughness ("Glossy" Only)**: value in range 0.0-1.0 defining amount of visible reflections
    - option only available with Shader Type 3 ("Glossy")

![Shader Settings](https://github.com/PositionWizard/TR123R-Blender-Addon/assets/89351809/12b5e3b3-67a1-4d67-bcfc-6778f53fdd22)

Things to keep in mind:
- Shader Settings don't affect what's visible in Blender
- to see the results you need to export to the game and test it there
- most of the settings are still unknown, "Glossy" type is guessed based on testing
- "Cubemap" and "Roughness" settings can be used in other Shader Types in a form of "Color" data type
- values are updated across all Shader Types, so changing these and switching between them can tell you how the same data is represented with other data types
- if you learn something new about those settings, let us know at [TR Forums Thread](https://www.tombraiderforums.com/showthread.php?t=228896)

### UV Tool
There's a new tool in the UV Editor window under "(N) Panel -> Tool -> TR123R Tools" tab. It's going to be visible only during Edit Mode for mesh object.
It allows to conform the UVs to the game's limitations - some things may appear skewed and way different from Blender's display if this isn't done.

![UV tool](https://github.com/PositionWizard/TR123R-Blender-Addon/assets/89351809/201eaae7-05a7-4452-bf7a-0751d9531397)

TRM files use UVs with only 8 bits of precision (256 possible vertex positions vertically and horizontally) and this tool snaps vertices to the correct spots.
#### Options:
- **Selection**: affects only selected vertices in the UV window
- **All**: affects all UV vertices

Try to keep your UVs inside a single UV square. The game doesn't respect UVs that are out of bounds and while there is an automatic adjustment of such UVs on export, it's prone to stretch vertices across the entire tile.

### Face Animation Data
Face animations from file like HEAD_IDLE.TRM cannot be edited yet but for now, the animation data can be extracted to another file and then used from that file when exporting the .TRM back into the game.

Modifying i.e. HEAD_IDLE.TRM:
1. Import the HEAD_IDLE.TRM to Blender
    - This will generate a file called HEAD_IDLE.TRMA in the same folder you imported the .TRM from
2. Edit the mesh in any software or use your own
    - Remember to keep the same Vertex Group order, face ones can be deleted if you don't want them but there will be no face movement in the game
    - If you want to keep face animations, your mesh should be roughly in the same place as original and should have very similar weighting in the same areas
3. Export the mesh to the same folder that the generated HEAD_IDLE.TRMA file is in and **make sure your filename is exactly the same**
    - Export directory can be different from game's directory, just both files should be in the same place when exporting from Blender
    - TRMA file doesn't need to be in game directory for it to work in game

### Photo Mode Poses
You can Load and Save Lara's poses from Photo Mode. Tools for that can be accessed under "(N) Panel -> Tool -> TR123R Tools". They should show up once an Armature is selected.

![Poses](https://github.com/PositionWizard/TR123R-Blender-Addon/assets/89351809/ef316a21-d167-43b1-8db2-d0f0317777a1)

You must import any Lara's .TRM model first, so you can load and save poses to and from the armature. Armatures should be automatically created upon importing .TRM models but currently only a few meshes are supported, including Lara's OUTFITs and HAIR. More information can be read in "[Armature Import](#armature-import)" section.

To import poses, you must first specify the path of either "Game Directory" or "Photo Mode Poses" in Addon's Preferences. Both can be set and either are optional but at least one must be set to work. For each of the buttons in the tool, "Use Explicit Path" can be enabled to load, save and edit POSE.txt under "Photo Mode Poses" path.

#### Load:
- **Load Pose and Load Poses**:
    - **Use Explicit Path**
    - **Skip Disabled Poses**: ignores commented out lines in POSE.txt
    - **Only Selected Bones**: option available only in Pose Mode, loads a pose only on selected bones
- **Load Pose**: loads a single pose to current frame
    - **Pose Number**: if **Skip Disabled Poses** is set, it will load a pose on the same number that's shown in game. Otherwise **Pose Number** will load a specific text line from the file
    - **Auto-Key**: enabling it will also insert keyframe on a current frame and currently active or new Action
- **Load Poses** loads all poses from the file into a currently active or new Action

#### Save:
- **Save Current Pose and Save Multiple Poses**:
    - **Add Pose to Existing**: adds poses at the end of the file, making them new available numbers in the game's Photo Mode
- **Save Current Pose**: saves a pose visible on a current frame
    - **Replace Pose**: a pose number that pose will be replaced on in the game; available once **Add Pose to Existing** is disabled
- **Save Multiple Poses**: saves many poses over a specified frame range on the timeline - each pose will be saved as it's displayed on a given frame
    - **From Frame Range**: the frame range in Blender to save poses from - start and end are inclusive, and each frame will be treated as a new pose, regardless whether a keyframe is present or not
    - **Replace at Pose**: if **Add Pose to Existing** is disabled, poses from a time range will replace poses in the game starting at that number and add new if they exceed original number of poses

#### Switch State:
- **Enable Poses and Disable Poses**
    - **Enable/Disable All Poses**: enable/disable all poses for the game
    - **Pose Line**: a specific pose line in the file that will be enabled/disabled for the game
- **Enable Poses**: enable specific pose or all poses that are disabled in the file with '//' sign
- **Disable Poses**: disable specific pose or all poses that can be seen in the game

### Skeleton Generator
Armature data is automatically generated on first supported imported .TRM file. This data is needed to properly construct armatures for TRM file names but if anything goes wrong, this can be manually generated from the Addon's Preferences.

Make sure you have corretly specified the "Game Directory" path and hit the **Generate Skeleton Data** button. It will take a few seconds and let you know with a message when it's done. Use this to refresh the list of available Armatures to import, after editing TRM_Names.xml.