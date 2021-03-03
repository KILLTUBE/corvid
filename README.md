# Corvid (ˈkɔrvəd)
Corvid is a tool made to make it easy to convert map made in Source Engine to Call of Duty. It is currently a work-in-progress, but it is at a stage where it is able to do what it is supposed to do with a few bugs and flaws here and there.

## Corvid can currently convert the following
- Materials (with their surface data and normal maps/env maps)
- Brushes and their texture coordinates
- Displacements and their vertex colors
- Ropes
- Lights (with limited support for spot lights in older Cod titles)
- Prop entities (static and physics props)

## Installing & running
To install Corvid, simply clone this repository, and install the dependencies using the following command.

```
python -m pip install -r requirements.txt
```
To run Corvid, all you need to do is launch `app.py`. In order to convert a map, you need to provide Corvid with a VMF while (you can use [BSP Source](https://github.com/ata4/bspsrc/releases) to decompile a map) and the directories and VPK files in which Corvid should look for the models and the materails used by the map. Once the conversion finishes, the map will be ready to be used with its assets properly converted for Call of Duty's mod tools.

## Issues and known bugs
- Some models can't be converted and some models come out in a bad shape. This is because of the model converter I wrote. Updating it or using SourceIO's model loader will probably fix that issue.

## Sources and references used
- Stefan Hajnoczi's [paper](https://github.com/stefanha/map-files/blob/master/MAPFiles.pdf) on map files.
- [VMF2OBJ](https://github.com/Dylancyclone/VMF2OBJ) by Dylancyclone
- [Qodot](https://github.com/Shfty/qodot-plugin) by Shfty
- [Zeroy](https://zeroy.com)'s article on [Call of Duty map format](https://wiki.zeroy.com/index.php?title=Call_of_Duty_4:_.MAP_file_structure)
- [Valve Map Format](https://developer.valvesoftware.com/wiki/Valve_Map_Format) on [Valve Developer Wiki](https://developer.valvesoftware.com/)

## Special thanks to
- [Dylancyclone](https://github.com/Dylancyclone) for [VMF2OBJ](https://github.com/Dylancyclone/VMF2OBJ) tool which helped me understand a lot of things about Source Engine maps and inspired me to work on this tool
- [masterex1000](https://github.com/masterex1000) for helping me understand the intricacies of map files, mesh generation and helping with calculating UV maps
- OldmanCats and Thomas cat for testing the maps converted by Corvid and help me figure out the issues we had on Black Ops 3. Without their help, Corvid couldn't have Black Ops 3 support at all.

Icon file created by [Freepik](https://www.flaticon.com/authors/freepik)