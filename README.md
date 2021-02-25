# Corvid (ˈkɔrvəd)
Corvid is a tool made to make it easy to convert map made in Source Engine to Call of Duty. It is currently a work-in-progress, but it is at a stage where it is able to do what it is supposed to do with a few bugs and flaws here and there.

## Corvid can currently convert the following
- Brushes
- Displacements with vertex paints
- Ropes
- Lights (with limited support for spot lights in older Cod titles)
- Prop entities (static and physics props)

## Installing & running
To install Corvid, simply clone this repository, and install the dependencies using the following command.

```
python -m pip install -r requirements.txt
```
To run Corvid, all you need to do is launch app.py. In order to convert a map, all you need to do is provide a VMF while (you can use [BSP Source](https://github.com/ata4/bspsrc/releases) to decompile a map) and the directories where Corvid should look for the models and the materails used by the map. Once the conversion finishes, the map will be ready to be used with its assets properly converted for Call of Duty's mod tools.

## Issues and known bugs
- Some brushes and displacements (especially the ones that have corners that are very close to each other) might not convert. This happens very rarely, but it should be fixed after the cause of this bug is found.
- Some models can't be converted and some models come out in a bad shape. This is because of the library being used to read models. Updating it or using SourceIO's model loader will probably fix that issue.

## Sources and references used
- Stefan Hajnoczi's [paper](https://github.com/stefanha/map-files/blob/master/MAPFiles.pdf) on map files.
- [VMF2OBJ](https://github.com/Dylancyclone/VMF2OBJ) by Dylancyclone
- [Qodot](https://github.com/Shfty/qodot-plugin) by Shfty

## Special thanks to
- [masterex1000](https://github.com/masterex1000) for helping me understand the intricacies of map files
- [Dylancyclone](https://github.com/Dylancyclone) for helping me understand how plane intersection works with his [VMF2OBJ](https://github.com/Dylancyclone/VMF2OBJ) tool

Icon file created by [Freepik](https://www.flaticon.com/authors/freepik)