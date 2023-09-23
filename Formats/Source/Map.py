from collections import OrderedDict
from os.path import basename, dirname, splitext, exists
from pathlib import Path
from typing import Dict, List, Tuple
from mathutils import Vector
from Formats.BaseMap.Map import Map as BaseMap
from Formats.Source.Material import Material
from Formats.Source.SourceModel import SourceModel
from Helpers.ListHelpers import AddUnique, Flatten
from Helpers.FileHelpers import GetTempDir, NewPath
from Helpers.MathHelpers import VecFromStr, Vec2Str
from Libs.SourceIO.source1.vtf.VTFWrapper.VTFLib import VTFLib
from .Entity import Entity
from .Solid import Solid
from .Side import Side
from .SourceDir import SourceDir
from .vdfutils import parse_vdf, format_vdf

FixPath = lambda path: Path(path).as_posix().strip().lower().replace(".vtf", "").replace(".vmt", "").replace(".tga", "")

class Map(BaseMap):
    __slots__ = (
        "versionInfo", "visGroups", "viewSettings", "world", "modelSkins","modelTints", "skyName", "skyboxOrigin",
        "skyboxScale", "assetDir", "materialData", "textureData", "modelTextureData"
    )

    world: List[Solid]
    entities: List[Entity]
    versionInfo: dict
    visGroups: list
    viewSettings: dict
    modelSkins: Dict[str, List[int]]
    modelTints: Dict[str, List[Tuple[int, int, int]]]
    skyName: str
    skyboxOrigin: Vector
    skyboxScale: float
    assetDir: SourceDir
    materialData: Dict[str, Material]
    textureData: Tuple[List[str], List[str], List[str], List[str], List[str], List[str]]
    modelData: Dict[str, SourceModel]
    modelMaterialData: Dict[str, Material]
    modelTextureData: Tuple[List[str], List[str], List[str], List[str], List[str]]

    def __init__(self, options: dict=None) -> None:
        super().__init__()

        self.versionInfo = {}
        self.visGroups = []
        self.viewSettings = {}
        self.world = []
        self.modelSkins = {}
        self.modelTints = {}
        self.skyboxOrigin = None
        self.skyboxScale = None
        self.skyName = ""
        self.assetDir = SourceDir()
        self.materialData = {}
        # color maps, transparent color maps, normal maps, env maps, env maps in alpha channel, blend maps
        self.textureData = ([], [], [], [], [], [])
        # color maps, transparent color maps, normal maps, env maps, env maps in alpha channel
        self.modelMaterialData = {}
        self.modelTextureData = ([], [], [], [], [])
        if options is not None:
            for i in options["Resources"]:
                self.assetDir.Add(i)

    def AddModelTint(self, model: str, tint: str) -> None:
        if model not in self.modelTints:
            self.modelTints[model] = []
        
        tint = tuple([int(i) for i in tint.split()])

        if tint not in self.modelTints[model]:
            self.modelTints[model].append(tint)
    
    def AddModelSkin(self, model: str, skin: str) -> None:
        if model not in self.modelSkins:
            self.modelSkins[model] = []
        
        skin = int(skin)

        if skin not in self.modelSkins[model]:
            self.modelSkins[model].append(skin)

    def LoadMaterials(self):
        for material in self.materials:
            if material.startswith("tools/"):
                continue

            vmtString = self.assetDir.Open(f"materials/{material}.vmt")
            if vmtString is not None:
                self.materialData[NewPath(material)] = Material.FromStr(vmtString)
            else:
                print(f"Cannot find material: {material}")

    def ExportTextures(self):
        textureMaps = [ # keys of the matetrial parameters for the texure maps we need
            "$basetexture", "$bumpmap", "$envmapmask", "$blendmodulatetexture","$basetexture2", "$bumpmap2", "$envmapmask2"
        ]
        tempDir = GetTempDir()

        # color maps, transparent color maps, normal maps, env maps, env maps in alpha channel, blend maps
        colorMaps, colorMapsAlpha, normalMaps, envMaps, envMapsInAlpha, blendMaps = self.textureData

        # export the materials from the game
        for material in self.materialData.values():
            for param in material.data.keys():
                if param in textureMaps:
                    path = FixPath(material[param])
                    self.assetDir.Copy(f"materials/{path}.vtf", f"{tempDir}/textures/{NewPath(path)}.vtf")

            # save their categories to convert them later
            if "$basetexture" in material:
                if "$translucent" in material or "$alpha" in material or "$alphatest" in material:
                    AddUnique(colorMapsAlpha, NewPath(FixPath(material["$basetexture"])))        
                elif "$blendtintbybasealpha" in material or "$blendtintcoloroverbase" in material:
                    AddUnique(colorMapsAlpha, NewPath(FixPath(material["$basetexture"])))      
                else:
                    AddUnique(colorMaps, NewPath(FixPath(material["$basetexture"])))
            
            if "$bumpmap" in material:
                AddUnique(normalMaps, NewPath(FixPath(material["$bumpmap"])))
            
            if "$envmapmask" in material:
                AddUnique(envMaps, NewPath(FixPath(material["$envmapmask"])))
            
            if "$blendmodulatetexture" in material:
                blendMaps.append(NewPath(FixPath(material["$blendmodulatetexture"])))
            
            if "$basetexture2" in material:
                AddUnique(colorMaps, NewPath(FixPath(material["$basetexture2"])))
            
            if "$bumpmap2" in material:
                AddUnique(normalMaps, NewPath(FixPath(material["$bumpmap2"])))
            
            if "$envmapmask2" in material:
                AddUnique(envMaps, NewPath(FixPath(material["$envmapmask2"])))
            
            if "basealphaenvmapmask" in material:
                AddUnique(envMapsInAlpha, NewPath(FixPath(material["$basetexture"])))
            
            if "normalmapalphaenvmapmask" in material:
                AddUnique(envMapsInAlpha, NewPath(FixPath(material["$bumpmap"])))

    def GetMaterialSizes(self):
        tempDir = GetTempDir()
        vtf = VTFLib()

        for name, material in self.materialData.items():
            if "$basetexture" in material:
                path = f"{tempDir}/textures/{NewPath(FixPath(material['$basetexture']))}.vtf"
                if exists(path):
                    vtf.image_load(path)
                    self.matSizes[name] = Vector((vtf.width(), vtf.height()))
                    vtf.image_destroy()

    def ExportModels(self):
        tempDir = GetTempDir()
        extensions = ["dx90.vtx", "vtx", "vvd"]

        for model in self.models:
            fileName = splitext(basename(model))[0]
            dirName = dirname(model)
            path = NewPath(f"{dirName}/{fileName}")
            self.assetDir.Copy(model, f"{tempDir}/models/{path}.mdl")

            for ext in extensions:
                self.assetDir.Copy(f"{dirName}/{fileName}.{ext}", f"{tempDir}/models/{path}.{ext}")

    def LoadModels(self):
        tempDir = GetTempDir()

        for model in self.models:
            fileName = splitext(basename(model))[0]
            dirName = dirname(model)
            path = NewPath(f"{dirName}/{fileName}")
            modelPath = f"{tempDir}/models/{path}"
            if not exists(f"{modelPath}.mdl"):
                continue

            modelData = SourceModel.Load(modelPath)

            for material in modelData.materials:
                if material not in self.modelMaterials:
                    self.modelMaterials.append(material)
            
            self.modelData[model] = modelData

    def LoadModelMaterials(self):
        # the paths to where vmt files are located are stored in two fields (materials, materials_paths)
        # we need to check each folder to see if there's a file with the same name as each material
        # and change each material object's material fiels accordingly before loading them
        for model in self.modelData.values():
            for i, material in enumerate(model.materials):
                material = FixPath(material)

                # the material field has the full path to the material we're looking for
                vmt = self.assetDir.Open(f"materials/{material}.vmt")
                if vmt is not None:
                    newName = NewPath(material)
                    model.materials[i] = newName
                    self.modelMaterialData[newName] = Material.FromStr(vmt)

                    # most models' materials don't have $surfaceprop property, so we need to make sure
                    # the materials have that property
                    self.modelMaterialData[newName]["$surfaceprop"] = model.surfaceProp

                    continue

                # the material exist in the path
                for path in model.materialPaths:
                    vmt = self.assetDir.Open(f"materials/{path}/{material}.vmt")
                    if vmt is not None:
                        newName = NewPath(material)
                        model.materials[i] = newName
                        self.modelMaterialData[newName] = Material.FromStr(vmt)
                        self.modelMaterialData[newName]["$surfaceprop"] = model.surfaceProp
                        continue

                    # the material's name has some additional path information, but we need its base name
                    # this does not really happen with any models, but it's an extra measure
                    vmt = self.assetDir.Open(f"materials/{path}/{basename(material)}.vmt")
                    if vmt is not None:
                        newName = NewPath(f"{path}/{basename(material)}")
                        model.materials[i] = newName
                        self.modelMaterialData[newName] = Material.FromStr(vmt)
                        self.modelMaterialData[newName]["$surfaceprop"] = model.surfaceProp
                        continue

            # do the same with skin groups
            for g, skinGroup in enumerate(model.skinGroups):
                for i, skin in enumerate(skinGroup):
                    skin = FixPath(skin)

                    vmt = self.assetDir.Open(f"materials/{skin}.vmt")

                    if vmt is not None:
                        newName = NewPath(skin)
                        model.skinGroups[g][i] = newName
                        self.modelMaterialData[newName] = Material.FromStr(vmt)
                        self.modelMaterialData[newName]["$surfaceprop"] = model.surfaceProp
                        continue

                    for path in model.materialPaths:
                        vmt = self.assetDir.Open(f"materials/{path}/{skin}.vmt")
                        if vmt is not None:
                            newName = NewPath(skin)
                            model.skinGroups[g][i] = newName
                            self.modelMaterialData[newName] = Material.FromStr(vmt)
                            self.modelMaterialData[newName]["$surfaceprop"] = model.surfaceProp
                            continue

                        vmt = self.assetDir.Open(f"materials/{path}/{basename(skin)}.vmt")
                        if vmt is not None:
                            newName = NewPath(f"{path}/{basename(skin)}")
                            model.skinGroups[g][i] = newName
                            self.modelMaterialData[newName] = Material.FromStr(vmt)
                            self.modelMaterialData[newName]["$surfaceprop"] = model.surfaceProp
                            continue

    def ExportModelTextures(self):
        textureMaps = [ # keys of the matetrial parameters for the texure maps we need
            "$basetexture", "$bumpmap", "$envmapmask"
        ]
        tempDir = GetTempDir()

        # color maps, transparent color maps, normal maps, env maps, env maps in alpha channel, blend maps
        colorMaps, colorMapsAlpha, normalMaps, envMaps, envMapsInAlpha = self.modelTextureData

        # export the materials from the game
        for material in self.modelMaterialData.values():
            for param in material.data.keys():
                if param in textureMaps:
                    path = FixPath(material[param])
                    self.assetDir.Copy(f"materials/{path}.vtf", f"{tempDir}/textures/{NewPath(path)}.vtf")

            # save their categories to convert them later
            if "$basetexture" in material:
                if "$translucent" in material or "$alpha" in material or "$alphatest" in material:
                    AddUnique(colorMapsAlpha, NewPath(FixPath(material["$basetexture"])))
                elif "$blendtintbybasealpha" in material or "$blendtintcoloroverbase" in material:
                    AddUnique(colorMapsAlpha, NewPath(FixPath(material["$basetexture"])))
                else:
                    AddUnique(colorMaps, NewPath(FixPath(material["$basetexture"])))

            if "$bumpmap" in material:
                AddUnique(normalMaps, NewPath(FixPath(material["$bumpmap"])))

            if "$envmapmask" in material:
                AddUnique(envMaps, NewPath(FixPath(material["$envmapmask"])))

            if "basealphaenvmapmask" in material:
                AddUnique(envMapsInAlpha, NewPath(FixPath(material["$basetexture"])))

            if "normalmapalphaenvmapmask" in material:
                AddUnique(envMapsInAlpha, NewPath(FixPath(material["$basetexture"])))

    @staticmethod
    def Load(path: str, options: dict=None) -> 'Map':
        res = Map(options)
        mapName = basename(path)
        print(f"Reading {mapName}...")


        with open(path, "r") as file:
            vmf: dict = parse_vdf(file.read(), True)

            if "versionInfo" in vmf:
                res.versionInfo = vmf["versionInfo"]

            if "visGroups" in vmf:
                res.visGroups = vmf["visGroups"]

            if "viewSettings" in vmf:
                res.viewSettings = vmf["viewSettings"]
            
            if "skyname" in vmf["world"]:
                res.skyName = vmf["world"]["skyname"]

            worldSolids = []
            worldSolids = vmf["world"]["solid"] if isinstance(vmf["world"]["solid"], list) else [vmf["world"]["solid"]]

            for solid in worldSolids:
                res.world.append(Solid(solid))
                for side in solid["side"]:
                    res.AddMaterial(side["material"])

            entities: Dict[str, str] = vmf["entity"] if isinstance(vmf["entity"], list) else [vmf["entity"]]
            for i, entity in enumerate(entities):
                res.entities.append(Entity(entity))
                
                for geo in res.entities[i].geo:
                    for face in geo.faces:
                        res.AddMaterial(face.material)

                if entity["classname"].startswith("prop_") and "model" in entity and entity["model"].endswith(".mdl"):
                    res.AddModel(entity["model"])

                    if "rendercolor" in entity and entity["rendercolor"] != "255 255 255":
                        res.AddModelTint(entity["model"], entity["rendercolor"])

                    if "skin" in entity and entity["skin"] != "0":
                        res.AddModelSkin(entity["model"], entity["skin"])

                elif entity["classname"] == "infodecal":
                    res.AddMaterial(entity["texture"])

                elif entity["classname"] == "info_overlay":
                    res.AddMaterial(entity["material"])

                elif entity["classname"] == "sky_camera":
                    res.skyboxOrigin = VecFromStr(entity["origin"])
                    res.skyboxScale = float(entity["scale"])

        if options is not None and not options["SkipAssets"]:
            # load material data and export the textures
            res.LoadMaterials()
            res.ExportTextures()
            res.GetMaterialSizes()

            # put all the brush faces in a 1d array to iterate through them more easily
            sides: List[Side] = Flatten([[f for f in b.faces] for b in res.world] + [[[f for f in b.faces] for b in e.geo] for e in res.entities])

            # the size of the color map is necessary while calculating a brush face's UV coordinates
            for side in sides:
                mat = NewPath(side.material)

                if mat in res.matSizes:
                    side.texSize = res.matSizes[mat]

            res.ExportModels()
            res.LoadModels()
            res.LoadModelMaterials()
            res.ExportModelTextures()

        return res

    def ToVMF(self) -> str:
        data = OrderedDict({
            "versioninfo": self.versionInfo,
            "viewsettings": self.viewSettings,
            "visgroups": self.visGroups,
            "world": {
                "mapversion": "1",
                "classname": "worldspawn",
                "detailmaterial": "detail/detailsprites",
                "detailvbsp": "detail.vbsp",
                "maxpropscreenwidth": "-1",
                "skyname": self.skyName,
                "solid": []
            },
            "entity": []
        })

        for solid in self.world:
            data["world"]["solid"].append(solid.ToDict())

        for entity in self.entities:
            data["entity"].append(entity.ToDict())

        return format_vdf(data)
