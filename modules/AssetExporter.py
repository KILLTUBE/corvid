import os
os.environ["NO_BPY"] = "1"
from PIL import Image
from glm import vec2, vec3
import numpy as np
from modules.cube2equi import find_corresponding_pixel
from modules.vdfutils import parse_vdf
from os.path import basename, splitext, dirname
from math import log2
from .Static import fixVmt, newPath, VecFromStr, Vec2Str, Vec2Hex
from .Gdt import Gdt
from .AssetConverter import getTexSize
from SourceIO.library.models.mdl.v49.mdl_file import MdlV49
from SourceIO.library.utils import MemoryBuffer
from pathlib import Path
from .SourceDir import SourceDir
from .Progress import Progress


def loadMaterials(mats, dir: SourceDir, progress: Progress=None):
    if progress is None:
        progress = Progress()
    res = []
    vmtCache = {}
    total = len(mats)
    for i, mat in enumerate(mats):
        progress.current(i + 1, total)
        name = newPath(mat)
        data = dir.read_text(f"materials/{mat}.vmt", silent=True)
        if data is None:
            data = dir.read_wvt_fallback(mat)
        if data is not None:
            vmtCache[name] = data
        res.append(name)
    return res, vmtCache

def loadTextures(mats, vmtCache, dir: SourceDir, mdl=False, progress: Progress=None):
    if progress is None:
        progress = Progress()
    res = {
        "sizes": {}, # save the dimensions of $basetexture
        "colorMaps": [],
        "colorMapsAlpha": [],
        "envMaps": [],
        "envMapsAlpha": [],
        "normalMaps": [],
        "revealMaps": [],
        "infected": {}, # basetexture name -> {gradient, clothRow, skinRow}
        "vmts": {}, # save vmt data to create GDT's later
        "vtfData": {} # VTF bytes keyed by normalized name
    }
    vtfData = res["vtfData"]

    def loadVtf(texturePath):
        # strip any leading materials/ prefix some VMTs include
        texturePath = texturePath.removeprefix("materials/")
        name = newPath(splitext(texturePath)[0], True)
        if name not in vtfData:
            data = dir.read_bytes(f"materials/{texturePath}.vtf", silent=True)
            if data is not None:
                vtfData[name] = data
        return name

    total = len(mats)
    for i, file in enumerate(mats):
        progress.current(i + 1, total)
        fileName = basename(file)
        vmtText = vmtCache.get(fileName) or vmtCache.get(file)
        if vmtText is None:
            progress.log(f"Could not find material {fileName}. Creating an empty material for it...")
            res["vmts"][fileName] = parse_vdf('lightmappedgeneric\n{\n"$basetexture" "404"\n}')
            res["sizes"][file.strip()] = vec2(512, 512)
            continue

        try:
            vmt = parse_vdf(fixVmt(vmtText))
            res["vmts"][fileName] = vmt
            shader = list(vmt)[0]
            mat = vmt[shader]
        except:
            progress.log(f"Could not parse material {fileName}. Skipping...")
            continue

        # some materials in Source can reference & inherit other materials' properties
        if "include" in mat:
            includeFile = mat["include"]
            if not includeFile.startswith("materials"):
                includeFile = "materials/" + includeFile
            if not includeFile.endswith(".vmt"):
                includeFile += ".vmt"
            includeFile = Path(includeFile.replace("\\", "/")).as_posix().lower().strip()
            includeText = dir.read_text(includeFile, silent=True)
            if includeText is not None:
                try:
                    includeVmt = parse_vdf(fixVmt(includeText))
                    patch = list(includeVmt)[0]
                    includeMat = includeVmt[patch]
                    mat = {**includeMat, **mat}
                except:
                    pass
                else:
                    # resolve the included shader name for the infected shader
                    if shader == "patch" and patch == "infected":
                        vmt[patch] = mat
                        del vmt[shader]
                        shader = patch
                        res["vmts"][fileName] = vmt
                    else:
                        res["vmts"][fileName][shader] = mat

        if "insert" in mat:
            mat = {**mat, **mat["insert"]}
            res["vmts"][fileName][shader] = mat

        # Refract shader uses $refracttinttexture instead of $basetexture
        if "$basetexture" not in mat and "$refracttinttexture" in mat:
            mat["$basetexture"] = mat["$refracttinttexture"]
            res["vmts"][fileName][shader] = mat

        if "$basetexture" in mat:
            baseTexture = mat["$basetexture"].strip()
            name = loadVtf(baseTexture)
        if not mdl: # we don't need to get the dimensions of model textures
            if "$basetexture" in mat and name in vtfData:
                res["sizes"][file.strip()] = getTexSize(vtfData[name])
            else:
                res["sizes"][file.strip()] = vec2(512, 512)
        # Infected shader: basetexture is a mask, not a color map.
        # Load gradient texture and reconstruct the diffuse during conversion.
        if shader == "infected" and "$basetexture" in mat and "$gradienttexture" in mat:
            gradName = loadVtf(mat["$gradienttexture"].strip())
            clothRow = int(mat.get("$colortintgradient", "0"))
            skinRow = int(mat.get("$skintintgradient", "8"))
            res["infected"][name] = {
                "gradient": gradName,
                "clothRow": clothRow,
                "skinRow": skinRow,
            }
            res["colorMaps"].append(name)
        elif "$basetexture" in mat:
            if "$translucent" in mat or "$alpha" in mat or "$alphatest" in mat:
                res["colorMapsAlpha"].append(name)
            elif "$blendtintbybasealpha" in mat or "$blendtintcoloroverbase" in mat:
                res["colorMapsAlpha"].append(name)
            else:
                res["colorMaps"].append(name)
        if "$bumpmap" in mat:
            name = loadVtf(mat["$bumpmap"].strip())
            res["normalMaps"].append(name)
        if "$envmapmask" in mat:
            name = loadVtf(mat["$envmapmask"].strip())
            res["envMaps"].append(name)
        if "$blendmodulatetexture" in mat:
            name = loadVtf(mat["$blendmodulatetexture"].strip())
            res["revealMaps"].append(name)
        if "$basetexture2" in mat:
            basetexture2 = mat["$basetexture2"].strip()
            name = loadVtf(basetexture2)
            res["colorMaps"].append(name)
            if name in vtfData:
                res["sizes"][file.strip() + "_blend"] = getTexSize(vtfData[name])
        if "$bumpmap2" in mat:
            name = loadVtf(mat["$bumpmap2"].strip())
            res["normalMaps"].append(name)
        if "$envmapmask2" in mat:
            name = loadVtf(mat["$envmapmask2"].strip())
            res["envMaps"].append(name)
        if "$basealphaenvmapmask" in mat:
            res["envMapsAlpha"].append(newPath(splitext(mat["$basetexture"])[0], True))
        if "$basealphaenvmapmask2" in mat:
            res["envMapsAlpha"].append(newPath(splitext(mat["$basetexture2"])[0], True))
        if "$normalmapalphaenvmapmask" in mat and "$bumpmap" in mat:
            res["envMapsAlpha"].append(newPath(splitext(mat["$bumpmap"])[0], True))
        if "$normalmapalphaenvmapmask2" in mat and "$bumpmap2" in mat:
            res["envMapsAlpha"].append(newPath(splitext(mat["$bumpmap2"])[0], True))
    return res

def loadModels(models, dir: SourceDir, progress: Progress=None):
    if progress is None:
        progress = Progress()
    modelData = {}
    total = len(models)
    for i, model in enumerate(models):
        progress.current(i + 1, total)
        modelName = splitext(basename(model))[0]
        newName = splitext(newPath(model))[0]
        path = dirname(model)
        mdl_data = dir.read_bytes(f"{model}", silent=True)
        if mdl_data is None:
            continue
        data = {"name": basename(newName), "mdl": mdl_data}
        for ext in ["dx90.vtx", "vtx", "vvd"]:
            ext_data = dir.read_bytes(f"{path}/{modelName}.{ext}", silent=True)
            if ext_data is not None:
                data[ext] = ext_data
        if "vvd" in data and ("dx90.vtx" in data or "vtx" in data):
            modelData[newName] = data
    return modelData

def loadModelMaterials(models, modelData, dir: SourceDir, modelTints, modelSkins, skinTints, game="WaW", progress: Progress=None):
    if progress is None:
        progress = Progress()
    materials = []
    res = []
    vmtCache = {}
    total = len(models)

    for i, model in enumerate(models):
        progress.current(i + 1, total)
        mdlName = splitext(newPath(model))[0]
        tints = modelTints[mdlName] if mdlName in modelTints else []

        if mdlName in skinTints:
            for _, _tints in skinTints[mdlName].items():
                tints += _tints

        if mdlName not in modelData:
            continue
        mdl = MdlV49.from_buffer(MemoryBuffer(modelData[mdlName]["mdl"]))

        # collect all materials: base skin + alternate skins
        all_materials = list(mdl.materials)
        if mdlName in modelSkins:
            for skin in modelSkins[mdlName]:
                if skin < len(mdl.skin_groups):
                    for mat in mdl.skin_groups[skin]:
                        if mat not in all_materials:
                            all_materials.append(mat)

        for material in all_materials:
            for path in mdl.materials_paths:
                path = Path(path.replace("\\", "/")).as_posix()
                name = basename(material.name.replace("\\", "/"))
                name = f"{path}/{name}".lower()
                if name not in materials:
                    materials.append((name, mdl.header.surface_prop, tints))

                name = Path(material.name.replace("\\", "/")).as_posix().lower()
                if name not in materials:
                    materials.append((name, mdl.header.surface_prop, tints))

    total = len(materials)
    for i, (mat, surface_prop, tints) in enumerate(materials):
        progress.current(i + 1, total)
        name = newPath(mat)
        vmtText = dir.read_text(f"materials/{mat}.vmt", silent=True)
        if vmtText is None:
            continue

        # unlike CoD, the surface type of a model isn't defined in the material so we have to copy that value
        # from the model and paste it in the materials it uses
        vmtText = vmtText.replace("{\n", f'{{\n"$surfaceprop" "{surface_prop}"\n', 1)
        vmtCache[name] = vmtText
        res.append(name)

        # create new a material for each tint value used for the model
        if game == "BO3" and len(tints) > 0:
            for tint in tints:
                _tint = VecFromStr(tint, 3)
                hex = Vec2Hex(_tint)
                tint = vec3(round(_tint.x, 3), round(_tint.y, 3), round(_tint.z, 3))
                tintedVmt = vmtText.replace("{\n", f'{{\n"$colortint" "{tint} 1"\n', 1)
                vmtCache[f"{name}_{hex}"] = tintedVmt
                res.append(f"{name}_{hex}")

    return sorted(set(res)), vmtCache

def modelUsage(name: str, surfaceprop: str = ""):
    name = name.lower()
    surfaceprop = surfaceprop.lower()

    nameKeywords = {
        "foliage": "foliage", "tree": "foliage", "leaf": "foliage", "leaves": "foliage",
        "bush": "foliage", "plant": "foliage", "grass": "foliage", "vine": "foliage",
        "ivy": "foliage", "shrub": "foliage", "hedge": "foliage", "fern": "foliage",
        "flower": "foliage", "weed": "foliage",
        "rock": "rock", "stone": "rock", "boulder": "rock", "cliff": "rock",
        "barrel": "barrel",
        "crate": "crate", "box": "crate",
        "fence": "fence", "chainlink": "fence",
        "sign": "sign",
        "poster": "poster",
        "door": "door", "gate": "door",
        "window": "window",
    }

    for keyword, usage in nameKeywords.items():
        if keyword in name:
            return usage

    surfacepropMap = {
        "foliage": "foliage", "grass": "foliage",
        "rock": "rock", "boulder": "rock", "baserock": "rock",
        "wood_box": "crate", "wood_crate": "crate",
        "floating_metal_barrel": "barrel", "metal_barrel": "barrel",
        "chainlink": "fence",
        "water": "liquid", "wade": "liquid", "puddle": "liquid",
        "slipperyslime": "liquid", "slime": "liquid",
        "dirt": "ground", "mud": "ground", "sand": "ground",
        "quicksand": "ground", "antlionsand": "ground",
    }

    if surfaceprop in surfacepropMap:
        return surfacepropMap[surfaceprop]

    return "core"

def surfaceType(surface: str, game=""):
    surface = surface.lower()
    surfaces =     {
        "default": ["plaster", "plaster"],
        "default_silent": ["plaster", "plaster"],
        "floatingstandable": ["plaster", "plaster"],
        "item": ["plastic", "plastic"],
        "ladder": ["metal", "metal"],
        "no_decal": ["plastic", "plastic"],
        "baserock": ["rock", "rock"],
        "boulder": ["rock", "rock"],
        "brick": ["brick", "brick"],
        "concrete": ["concrete", "concrete"],
        "concrete_block": ["concrete", "concrete"],
        "gravel": ["gravel", "gravel"],
        "rock": ["rock", "rock"],
        "canister": ["metal", "metal"],
        "chain": ["metal", "metal"],
        "chainlink": ["metal", "metal"],
        "combine_metal": ["metal", "metal"],
        "crowbar": ["metal", "metal"],
        "floating_metal_barrel": ["metal", "metal"],
        "grenade": ["metal", "metal"],
        "gunship": ["metal", "metal"],
        "metal": ["metal", "metal"],
        "metal_barrel": ["metal", "metal"],
        "metal_bouncy": ["metal", "metal"],
        "metal_box": ["metal", "metal"],
        "metal_seafloorcar": ["metal", "metal"],
        "metalgrate": ["metal", "metal"],
        "metalpanel": ["metal", "metal"],
        "metalvent": ["metal", "metal"],
        "metalvehicle": ["metal", "metal"],
        "paintcan": ["metal", "metal"],
        "popcan": ["metal", "metal"],
        "roller": ["metal", "metal"],
        "slipperymetal": ["metal", "metal"],
        "solidmetal": ["metal", "metal"],
        "strider": ["metal", "metal"],
        "weapon": ["metal", "metal"],
        "wood": ["wood", "wood"],
        "wood_box": ["wood", "wood"],
        "wood_crate": ["wood", "wood"],
        "wood_furniture": ["wood", "wood"],
        "wood_lowdensity": ["wood", "wood"],
        "wood_plank": ["wood", "wood"],
        "wood_panel": ["wood", "wood"],
        "wood_solid": ["wood", "wood"],
        "dirt": ["dirt", "dirt"],
        "grass": ["grass", "foliage"],
        "mud": ["mud", "mud"],
        "quicksand": ["sand", "sand"],
        "sand": ["sand", "sand"],
        "slipperyslime": ["mud", "mud"],
        "antlionsand": ["sand", "sand"],
        "slime": ["mud", "mud"],
        "water": ["water", "water"],
        "wade": ["water", "water"],
        "puddle": ["water", "water"],
        "ice": ["ice", "ice"],
        "snow": ["snow", "snow"],
        "alienflesh": ["flesh", "skin"],
        "antlion": ["flesh", "skin"],
        "armorflesh": ["flesh", "skin"],
        "bloodyflesh": ["flesh", "skin"],
        "flesh": ["flesh", "skin"],
        "foliage": ["foliage", "foliage"],
        "watermelon": ["fruit", "foliage"],
        "zombieflesh": ["flesh", "skin"],
        "asphalt": ["asphalt", "asphalt"],
        "glass": ["glass", "glass"],
        "glassbottle": ["glass", "glass"],
        "combine_glass": ["glass", "glass"],
        "tile": ["ceramic", "ceramic"],
        "paper": ["paper", "paper"],
        "papercup": ["paper", "paper"],
        "cardboard": ["paper", "paper"],
        "plaster": ["plaster", "plaster"],
        "plastic_barrel": ["plastic", "plastic"],
        "plastic_barrel_buoyant": ["plastic", "plastic"],
        "plastic_box": ["plastic", "plastic"],
        "plastic": ["plastic", "plastic"],
        "rubber": ["plastic", "plastic"],
        "rubbertire": ["plastic", "plastic"],
        "slidingrubbertire": ["plastic", "plastic"],
        "slidingrubbertire_front": ["plastic", "plastic"],
        "slidingrubbertire_rear": ["plastic", "plastic"],
        "jeeptire": ["plastic", "plastic"],
        "brakingrubbertire": ["plastic", "plastic"],
        "carpet": ["carpet", "carpet"],
        "ceiling_tile": ["ceramic", "ceramic"],
        "computer": ["plastic", "plastic"],
        "pottery": ["brick", "brick"]
    }

    glossranges = {
        "<full>": (0.0, 8.5), "asphalt": (0.0, 2.0), "brick": (0.0, 2.0), "carpet": (0.0, 1.0), "ceramic": (0.0, 8.5), "cloth": (0.0, 2.0), "concrete": (0.0, 2.0),
        "dirt": (0.0, 2.0), "skin": (1.0, 5.0), "foliage": (0.0, 3.0), "glass": (3.0, 8.5), "gravel": (0.0, 2.0), "ice": (2.0, 8.5), "metal": (0.0, 8.5),
        "mud": (2.0, 6.5), "paint": (1.0, 3.5), "paper": (0.0, 1.0), "plaster": (0.0, 1.0), "plastic": (2.0, 6.5), "rock": (0.0, 2.0), "rubber": (0.0, 2.0),
        "sand": (1.0, 4.0), "snow": (2.0, 6.0), "water": (3.0, 8.5), "wood": (1.0, 2.5), "bark": (0.0, 2.0)
    }

    if surface in surfaces:
        if game == "CoD2": # some surface types don't exist in CoD 2
            cod2surfs = [
                'asphalt', 'bark', 'brick', 'carpet', 'cloth',
                'concrete', 'dirt', 'flesh', 'foliage',
                'glass', 'grass', 'gravel', 'ice', 'metal', 'mud', 'paper',
                'plaster', 'rock', 'sand', 'snow', 'water', 'wood'
            ]

            if surfaces[surface][0] not in cod2surfs:
                surfaces[surface][0] = "<none>"

        return {
            "surface": surfaces[surface][0],
            "gloss": surfaces[surface][1],
            "glossrange": glossranges[surfaces[surface][1]]
        }

    else:
        return {
            "surface": "<none>",
            "gloss": "<custom>",
            "glossrange": (0, 4)
        }
    
def createMaterialGdt(vmts: dict, game="WaW", loadedTextures=set(), overlayMats=None, colorMaps=set(), progress: Progress=None):
    if progress is None:
        progress = Progress()
    if game == "BO3":
        return createMaterialGdtBo3(vmts, loadedTextures, colorMaps, overlayMats, progress)
    gdt = Gdt()
    textureDir = "texture_assets\\\\corvid\\\\"
    ext, _ext = ".tga", "_.tga"

    total = len(vmts.items())

    for i, (name, vmt) in enumerate(vmts.items()):
        progress.current(i + 1, total)
        shader = list(vmt)[0]
        
        try:
            mat = vmt[shader]
            data = {}
        except:
            progress.log(f"Error parsing {name}. Skipping...")
            progress.log(str(vmt))
            continue

        assetName = name

        if shader == "lightmappedgeneric" or shader == "worldvertextransition":
            data["materialType"] = "world phong"
        elif shader == "unlitgeneric":
            data["materialType"] = "world unlit"
        elif shader == "vertexlitgeneric" or shader == "infected":
            data["materialType"] = "model phong"
        else:
            data["materialType"] = "world phong"
        
        if shader not in ("vertexlitgeneric", "infected"):
            data["usage"] = "tools"
        else:
            surfprop = mat.get("$surfaceprop", "").strip()
            data["usage"] = modelUsage(name, surfprop)

        if "$basetexture" in mat:
            fileName = newPath(mat["$basetexture"], shorten=True)
            if fileName  in loadedTextures:
                data["colorMap"] = textureDir + fileName + ext
            else:
                data["colorMap"] = textureDir + "404" + ext
        else:
            data["colorMap"] = textureDir + "404" + ext
        
        if "$bumpmap" in mat and "$ssbump" not in mat:
            fileName = newPath(mat["$bumpmap"], shorten=True)
            if fileName  in loadedTextures:
                data["normalMap"] = textureDir + fileName + ext
        if "$envmapmask" in mat:
            fileName = newPath(mat["$envmapmask"], shorten=True)
            if fileName  in loadedTextures:
                data["cosinePowerMap"] = textureDir + fileName + ext
        if "$basealphaenvmapmask" in mat and "$envmapmask" not in mat:
            fileName = newPath(mat["$basetexture"], shorten=True)
            if fileName in loadedTextures:
                data["cosinePowerMap"] = textureDir + fileName + _ext
        if "$normalmapalphaenvmapmask" in mat and "$envmapmask" not in mat and "$bumpmap" in mat:
            fileName = newPath(mat["$bumpmap"], shorten=True)
            if fileName in loadedTextures:
                data["cosinePowerMap"] = textureDir + fileName + _ext

        if "$nocull" in mat:
            data["cullFace"] = "None"

        if "$surfaceprop" in mat:
            data["surfaceType"] = surfaceType(mat["$surfaceprop"].strip(), game)["surface"]
        else:
            data["surfaceType"] = "<none>"

        if "$alphatest" in mat or "$alpha" in mat:
            data["alphaTest"] = "GE128"
        if "$translucent" in mat:
            data["blendFunc"] = "Blend"

        if overlayMats and assetName.strip() in overlayMats:
            data["sort"] = "decal - top 3"
            data["locale_decal"] = "1"
            data["polygonOffset"] = "Static Decal"
            if "$alphatest" in mat or "$alpha" in mat:
                data["blendFunc"] = "Multiply"
            elif "blendFunc" not in data:
                data["blendFunc"] = "Blend"

        if "$basetexture2" in mat:
            data2 = {}
            data2["materialType"] = "world phong"
            fileName = newPath(mat["$basetexture2"], shorten=True)
            if fileName  in loadedTextures:
                data2["colorMap"] = textureDir + fileName + ext
            else:
                data2["colorMap"] = textureDir + "404" + ext

            data2["blendFunc"] = "Blend"
            data2["usage"] = "tools"

            if "$bumpmap2" in mat and "$ssbump" not in mat:
                fileName = newPath(mat["$bumpmap2"], shorten=True)
                if fileName  in loadedTextures:
                    data2["normalMap"] = textureDir + fileName + ext
            if "$envmapmask2" in mat:
                fileName = newPath(mat["$envmapmask2"], shorten=True)
                if fileName  in loadedTextures:
                    data["cosinePowerMap"] = textureDir + fileName + ext
            if "$basealphaenvmapmask2" in mat and "$envmapmask2" not in mat:
                fileName = newPath(mat["$basetexture2"], shorten=True)
                if fileName in loadedTextures:
                    data2["cosinePowerMap"] = textureDir + fileName + _ext
            if "$normalmapalphaenvmapmask2" in mat and "$envmapmask2" not in mat and "$bumpmap2" in mat:
                fileName = newPath(mat["$bumpmap2"], shorten=True)
                if fileName in loadedTextures:
                    data2["cosinePowerMap"] = textureDir + fileName + _ext

            if "$surfaceprop2" in mat:
                data2["surfaceType"] = surfaceType(mat["$surfaceprop2"].strip())["surface"]
            else:
                data2["surfaceType"] = "<none>"

            if "$alphatest" in mat or "$alpha" in mat:
                data2["alphaTest"] = "GE128"

            data2["sort"] = "decal - bottom 1"
            data2["locale"] = "decal"

            gdt.add(assetName.strip() + "_blend", "material", data2)

        gdt.add(assetName.strip(), "material", data)
    return gdt

def createMaterialGdtBo3(vmts: dict, loadedTextures=set(), colorMaps=set(), overlayMats=None, progress: Progress=None):
    if progress is None:
        progress = Progress()
    gdt = Gdt()
    total = len(vmts.items())

    for i, (name, vmt) in enumerate(vmts.items()):
        progress.current(i + 1, total)
        shader = list(vmt)[0]
        mat = vmt[shader]
        assetName = name

        data = {}
        data["template"] = "material.template"

        # these are default values and should stay the same unless the material requires more than a color map and a normal map
        data["materialCategory"] = "Geometry"
        data["materialType"] = "lit"

        if "$basetexture" in mat:
            fileName = newPath(mat["$basetexture"], shorten=True)
            if fileName  in loadedTextures:
                data["colorMap"] = "i_" + newPath(mat["$basetexture"], shorten=True)
            else:
                data["colorMap"] = "i_404"
        else:
            data["colorMap"] = "i_404"
        
        if shader not in ("vertexlitgeneric", "vertexunlitgeneric", "infected"):
            data["usage"] = "tools"
        else:
            surfprop = mat.get("$surfaceprop", "").strip()
            data["usage"] = modelUsage(name, surfprop)

        if "$bumpmap" in mat and "$ssbump" not in mat:
            fileName = newPath(mat["$bumpmap"], shorten=True)
            if fileName  in loadedTextures:
                data["normalMap"] = "i_" + fileName
        if "$envmapmask" in mat:
            fileName = newPath(mat["$envmapmask"], shorten=True)
            if fileName  in loadedTextures:
                assetSuffix = "_" if fileName in colorMaps else ""
                data["cosinePowerMap"] = "i_" + fileName + assetSuffix
                data["materialCategory"] = "Geometry Plus"
                data["materialType"] = "lit_plus"
        if "$basealphaenvmapmask" in mat and "$envmapmask" not in mat:
            fileName = newPath(mat["$basetexture"], shorten=True)
            if fileName in loadedTextures:
                data["cosinePowerMap"] = "i_" + fileName + "_"
                data["materialCategory"] = "Geometry Plus"
                data["materialType"] = "lit_plus"
        if "$normalmapalphaenvmapmask" in mat and "$envmapmask" not in mat and "$bumpmap" in mat:
            fileName = newPath(mat["$bumpmap"], shorten=True)
            if fileName in loadedTextures:
                data["cosinePowerMap"] = "i_" + fileName + "_"
                data["materialCategory"] = "Geometry Plus"
                data["materialType"] = "lit_plus"

        if "$surfaceprop" in mat:
            surfaceprop = surfaceType(mat["$surfaceprop"].strip())
            data["surfaceType"] = surfaceprop["surface"]
            data["glossSurfaceType"] = surfaceprop["gloss"]
            data["glossRangeMin"] = surfaceprop["glossrange"][0]
            data["glossRangeMax"] = surfaceprop["glossrange"][1]
        else:
            data["surfaceType"] = "<none>"
            data["glossSurfaceType"] = "<custom>"
            data["glossRangeMin"] = "0.0"
            data["glossRangeMax"] = "0.0"

        if "cosinePowerMap" not in data:
            data["glossRangeMin"] = 0.0
            data["glossRangeMax"] = 0.0
        
        # gotta change the material type for things like alphatest, translucency and back face culling
        # that's one of the major differences between the old and new asset pipeline from what I can tell

        if "$translucent" in mat:
            if data["materialType"] == "lit_plus":
                data["materialType"] = "lit_transparent_plus"
            else:
                data["materialType"] = "lit_transparent"

        if "$alpha" in mat or "$alphatest" in mat:
            if data["materialType"] == "lit_plus":
                data["materialType"] = "lit_alphatest_plus"
            else:
                data["materialType"] = "lit_alphatest"
        
        if "$nocull" in mat:
            if data["materialType"] == "lit_transparent_plus":
                data["materialType"] = "lit_transparent_nocull_plus"
            elif data["materialType"] == "lit_transparent":
                data["materialType"] = "lit_transparent_nocull"
            elif data["materialType"] == "lit_alphatest":
                data["materialType"] = "lit_alphatest_nocull"
            elif data["materialType"] == "lit_alphatest_plus":
                data["materialType"] = "lit_alphatest_nocull_plus"
            elif data["materialType"] == "lit_plus":
                data["materialType"] = "lit_nocull_plus"
            else:
                data["materialType"] = "lit_nocull"
                
        if overlayMats and assetName.strip() in overlayMats:
            data["materialCategory"] = "Decal"
            data["materialType"] = "lit_decal"

        # if "$selfillum" in mat:
        #     if mat["$selfillum"] == "1":
        #         data["materialType"] = "lit_emissive"

        if "$color" in mat:
            tint = VecFromStr(mat["$color"], 3)

            if tint.x >= 1.0 or tint.y >= 1.0 or tint.z >= 1.0:
                tint = vec3([round(i, 3) for i in tint / 255])

            data["colorTint"] = tint

        if "$colortint" in mat:
            data["colorTint"] = mat["$colortint"]

        if "$layertint1" in mat:
            tint = VecFromStr(mat["$layertint1"], 3)

            if tint.x >= 1.0 or tint.y >= 1.0 or tint.z >= 1.0:
                tint = vec3([round(i, 3) for i in tint / 255])

            data["colorTint"] = tint

        if "$basetexture2" in mat:
            data2 = {}
            data2["materialCategory"] = "Decal"
            data2["materialType"] = "lit_decal_reveal"
            data2["layerSortDecal"] = "Asphalt (bottom)"

            fileName = newPath(mat["$basetexture2"], shorten=True)
            if fileName  in loadedTextures:
                data2["colorMap"] = "i_" + fileName
            else:
                data2["colorMap"] = "404"
            data2["usage"] = "tools" # probably not a good idea

            if "$bumpmap2" in mat and "$ssbump2" not in mat:
                fileName = newPath(mat["$bumpmap2"], shorten=True)
                if fileName  in loadedTextures:
                    data2["normalMap"] = "i_" + newPath(mat["$bumpmap2"], shorten=True)
            if "$blendmodulatetexture" in mat:
                fileName = newPath(mat["$blendmodulatetexture"], shorten=True)
                if fileName  in loadedTextures:
                    data2["alphaRevealMap"] = "i_" + newPath(mat["$blendmodulatetexture"], shorten=True)
            if "$envmapmask2" in mat:
                fileName = newPath(mat["$envmapmask2"], shorten=True)
                if fileName  in loadedTextures:
                    assetSuffix = "_" if fileName in colorMaps else ""
                    data2["cosinePowerMap"] = "i_" + fileName + assetSuffix
                    data2["materialType"] = "lit_decal_reveal_plus"
            if "$basealphaenvmapmask2" in mat and "$envmapmask2" not in mat:
                fileName = newPath(mat["$basetexture2"], shorten=True)
                if fileName in loadedTextures:
                    data2["cosinePowerMap"] = "i_" + newPath(mat["$basetexture2"], shorten=True) + "_"
                    data2["materialType"] = "lit_decal_reveal_plus"
            if "$normalmapalphaenvmapmask2" in mat and "$envmapmask2" not in mat and "$bumpmap2" in mat:
                fileName = newPath(mat["$bumpmap2"], shorten=True)
                if fileName in loadedTextures:
                    data2["cosinePowerMap"] = "i_" + newPath(mat["$bumpmap2"], shorten=True) + "_"
                    data2["materialType"] = "lit_decal_reveal_plus"

            if "$surfaceprop2" in mat:
                surfaceprop = surfaceType(mat["$surfaceprop2"].strip())
                data2["surfaceType"] = surfaceprop["surface"]
                data2["glossSurfaceType"] = surfaceprop["gloss"]
                data2["glossRangeMin"] = surfaceprop["glossrange"][0]
                data2["glossRangeMax"] = surfaceprop["glossrange"][1]
            else:
                data2["surfaceType"] = "<none>"
                data2["glossSurfaceType"] = "<custom>"
                data2["glossRangeMin"] = "0.0"
                data2["glossRangeMax"] = "0.0"

            if "cosinePowerMap" not in data2:
                data2["glossRangeMin"] = 0.0
                data2["glossRangeMax"] = 0.0

            if "$layertint2" in mat:
                tint = VecFromStr(mat["$layertint2"], 3)

                if tint.x >= 1.0 or tint.y >= 1.0 or tint.z >= 1.0:
                    tint = vec3([round(i, 3) for i in tint / 255])

                data2["colorTint"] = tint           

            gdt.add(assetName + "_blend", "material", data2)
        
        gdt.add(assetName, "material", data)
    
    return gdt

def createModelGdt(models, game="WaW", modelTints={}, modelSkins={}, skinTints={}, progress: Progress=None):
    if progress is None:
        progress = Progress()
    gdt = Gdt()
    total = len(models)

    for i, model in enumerate(models):
        progress.current(i + 1, total)
        name = splitext(newPath(model))[0]

        gdt.add("m_" + name, "xmodel", {
            "collisionLOD" if game != "BO3" else "BulletCollisionLOD": "High",
            "filename": f"corvid\\\\{name}." + ("xmodel_export" if game != "BO3" else "xmodel_bin"),
            "type": "rigid"
        })

        if game == "BO3" and name in modelTints:
            for tint in modelTints[name]:
                hex = Vec2Hex(VecFromStr(tint, 3))
                gdt.add(f"m_{name}_{hex}", "xmodel", {
                    "collisionLOD" if game != "BO3" else "BulletCollisionLOD": "High",
                    "filename": f"corvid\\\\{name}_{hex}." + ("xmodel_export" if game != "BO3" else "xmodel_bin"),
                    "type": "rigid"
                })

        if name in modelSkins:
            for skin in modelSkins[name]:
                gdt.add(f"m_{name}_skin{skin}", "xmodel", {
                    "collisionLOD" if game != "BO3" else "BulletCollisionLOD": "High",
                    "filename": f"corvid\\\\{name}_skin{skin}." + ("xmodel_export" if game != "BO3" else "xmodel_bin"),
                    "type": "rigid"
                })

        if game == "BO3" and name in skinTints:
            for skin, tints in skinTints[name].items():
                for tint in tints:
                    hex = Vec2Hex(VecFromStr(tint, 3))
                    gdt.add(f"m_{name}_skin{skin}_{hex}", "xmodel", {
                        "collisionLOD" if game != "BO3" else "BulletCollisionLOD": "High",
                        "filename": f"corvid\\\\{name}_skin{skin}_{hex}." + ("xmodel_export" if game != "BO3" else "xmodel_bin"),
                        "type": "rigid"
                    })

    return gdt

def createImageGdt(images, progress: Progress=None):
    if progress is None:
        progress = Progress()
    gdt = Gdt()
    images["colorMaps"] = list(dict.fromkeys(images["colorMaps"]))
    images["colorMapsAlpha"] = list(dict.fromkeys(images["colorMapsAlpha"]))
    images["normalMaps"] = list(dict.fromkeys(images["normalMaps"]))
    images["envMaps"] = list(dict.fromkeys(images["envMaps"]))
    images["envMapsAlpha"] = list(dict.fromkeys(images["envMapsAlpha"]))
    images["revealMaps"] = list(dict.fromkeys(images["revealMaps"]))

    lencolorMaps = len(images["colorMaps"])
    lencolorMapsAlpha = len(images["colorMapsAlpha"])
    lennormalMaps = len(images["normalMaps"])
    lenenvMaps = len(images["envMaps"])
    lenenvMapsAlpha = len(images["envMapsAlpha"])
    lenrevealMaps = len(images["revealMaps"])
    total = lencolorMaps + lencolorMapsAlpha + lennormalMaps + lenenvMaps + lenenvMapsAlpha + lenrevealMaps

    for i, file in enumerate(images["colorMaps"]):
        progress.current(i + 1, total)
        gdt.add(f"i_{file}", "image", {
            "imageType": "Texture",
            "type": "image",
            "baseImage": f"texture_assets\\\\corvid\\\\{file}.tif",
            "semantic": "diffuseMap",
            "compressionMethod": "compressed high color",
            "coreSemantic": "sRGB3chAlpha",
            "streamable": "1"
        })

    for i, file in enumerate(images["colorMapsAlpha"], lencolorMaps):
        progress.current(i + 1, total)
        gdt.add(f"i_{file}", "image", {
            "imageType": "Texture",
            "type": "image",
            "baseImage": f"texture_assets\\\\corvid\\\\{file}.tif",
            "semantic": "diffuseMap",
            "compressionMethod": "compressed high color",
            "coreSemantic": "sRGB3chAlpha",
            "streamable": "1"
        })

    for i, file in enumerate(images["normalMaps"], lencolorMaps + lencolorMapsAlpha):
        progress.current(i + 1, total)
        gdt.add(f"i_{file}", "image", {
            "imageType": "Texture",
            "type": "image",
            "baseImage": f"texture_assets\\\\corvid\\\\{file}.tif",
            "semantic": "normalMap",
            "compressionMethod": "compressed",
            "coreSemantic": "Normal",
            "streamable": "1"
        })

    for i, file in enumerate(images["envMaps"], lencolorMaps + lencolorMapsAlpha + lennormalMaps):
        progress.current(i + 1, total)
        
        # some materials use the same image for both their color maps and env maps. we need to create seperate image asset for them
        assetName = file + "_" if file in images["colorMaps"] or file in images["colorMapsAlpha"] else file
        gdt.add(f"i_{assetName}", "image", {
            "imageType": "Texture",
            "type": "image",
            "baseImage": f"texture_assets\\\\corvid\\\\{file}.tif",
            "semantic": "glossMap",
            "compressionMethod": "compressed",
            "coreSemantic": "Linear1ch",
            "streamable": "1"
        })

    for i, file in enumerate(images["envMapsAlpha"], lencolorMaps + lencolorMapsAlpha + lennormalMaps + lenenvMaps):
        progress.current(i + 1, total)
        gdt.add(f"i_{file}_", "image", {
            "imageType": "Texture",
            "type": "image",
            "baseImage": f"texture_assets\\\\corvid\\\\{file}_.tif",
            "semantic": "glossMap",
            "compressionMethod": "compressed",
            "coreSemantic": "Linear1ch",
            "streamable": "1"
        })

    for i, file in enumerate(images["revealMaps"], lencolorMaps + lencolorMapsAlpha + lennormalMaps + lenenvMaps + lenenvMapsAlpha):
        progress.current(i + 1, total)
        gdt.add(f"i_{file}", "image", {
            "imageType": "Texture",
            "type": "image",
            "baseImage": f"texture_assets\\\\corvid\\\\{file}.tif",
            "semantic": "revealMap",
            "compressionMethod": "compressed",
            "coreSemantic": "Linear1ch",
            "streamable": "1"
        })
    
    gdt.add("i_404", "image", {
        "imageType": "Texture",
        "type": "image",
        "baseImage": "texture_assets\\\\corvid\\\\404.tif",
        "semantic": "diffuseMap",
        "compressionMethod": "compressed high color",
        "coreSemantic": "sRGB3chAlpha",
        "streamable": "1"
    })
    
    return gdt

def exportSkybox(skyName: str, mapName: str, worldSpawnSettings, dir: SourceDir, game="WaW", outDir=""):
    skyName = skyName.lower()
    faces = ["up", "dn", "lf", "rt", "ft", "bk"]
    gdt = Gdt()
    convertDir = f"{outDir}/texture_assets/corvid/"

    from SourceIO.library.utils.pylib.vtf import load_vtf_texture

    # read VMT data for all faces and detect HDR
    vmtData = {}
    isHDR = False
    skyColor = np.array([1.0, 1.0, 1.0], dtype=np.float32)
    for face in faces:
        vmtText = dir.read_text(f"materials/skybox/{skyName}{face}.vmt", silent=True)
        if vmtText is None:
            return gdt
        vmt = parse_vdf(fixVmt(vmtText))
        shader = list(vmt)[0]
        vmtData[face] = vmt[shader]

    firstMat = vmtData[faces[0]]
    isHDR = "$hdrcompressedtexture" in firstMat or "$hdrbasetexture" in firstMat

    # parse $color multiplier from VMT (e.g. "[.25 .25 .25]")
    colorStr = firstMat.get("$color", "")
    if colorStr:
        colorStr = colorStr.strip("[]{}").strip()
        colorVals = colorStr.split()
        if len(colorVals) == 3:
            skyColor = np.array([float(v) for v in colorVals], dtype=np.float32)

    # load all faces from VTF data
    skyImages = {}
    maxDim = 0
    for face in faces:
        mat = vmtData[face]
        # for BO3, prefer HDR textures; for older games, prefer LDR
        if game == "BO3":
            paramOrder = ["$hdrcompressedtexture", "$hdrbasetexture", "$basetexture"]
        else:
            paramOrder = ["$basetexture", "$hdrcompressedtexture", "$hdrbasetexture"]
        for param in paramOrder:
            if param in mat:
                texParam = param
                break
        texName = splitext(basename(mat[texParam]))[0]
        vtfData = dir.read_bytes(f"materials/skybox/{texName}.vtf", silent=True)
        pixel_data, width, height, is_float = load_vtf_texture(vtfData)
        if is_float:
            arr = np.frombuffer(pixel_data, dtype=np.float32).reshape(height, width, 4)
        else:
            arr = np.frombuffer(pixel_data, dtype=np.uint8).reshape(height, width, 4).astype(np.float32) / 255.0

        # apply $basetexturetransform scale to determine target size
        transform = mat.get("$basetexturetransform", "")
        targetW, targetH = width, height
        if "scale" in transform:
            scale_part = transform.split("scale")[1].split("rotate")[0].strip()
            scale_vals = scale_part.split()
            targetW = int(width * float(scale_vals[0]))
            targetH = int(height * float(scale_vals[1]))

        maxDim = max(max(targetW, targetH), maxDim)
        skyImages[face] = arr

    # resize all faces to square
    for face in faces:
        arr = skyImages[face]
        # apply $color multiplier for BO3 HDR path
        if game == "BO3":
            arr[:, :, :3] *= skyColor
        if arr.shape[0] != maxDim or arr.shape[1] != maxDim:
            pil = Image.fromarray((np.clip(arr, 0, 1) * 255).astype(np.uint8), "RGBA")
            pil = pil.resize((maxDim, maxDim), Image.LANCZOS)
            skyImages[face] = np.array(pil).astype(np.float32) / 255.0
        else:
            skyImages[face] = arr

    if game != "BO3":
        # save individual faces as plain RGB images for older CoD games
        for face in faces:
            arr = skyImages[face][:, :, :3]
            ldr = (np.clip(arr, 0, 1) * 255).astype(np.uint8)
            Image.fromarray(ldr, "RGB").save(f"{convertDir}/{mapName}_sky_{face}.tga")

    if game == "BO3":
        print("Converting skybox...")

        # assemble cubemap cross layout
        s = maxDim
        cubemap = np.zeros((s * 3, s * 4, 3), dtype=np.float32)
        cubemap[s:s*2, 0:s] = skyImages["bk"][:, :, :3]
        cubemap[s:s*2, s:s*2] = skyImages["rt"][:, :, :3]
        cubemap[0:s, s:s*2] = skyImages["up"][:, :, :3]
        cubemap[s:s*2, s*2:s*3] = skyImages["ft"][:, :, :3]
        cubemap[s:s*2, s*3:s*4] = skyImages["lf"][:, :, :3]
        cubemap[s*2:s*3, s:s*2] = skyImages["dn"][:, :, :3]

        # convert cubemap cross to equirectangular
        wo, ho = cubemap.shape[1], cubemap.shape[0]
        h = int(wo / 3)
        w = int(2 * h)
        n = ho / 3

        xcoords, ycoords = np.meshgrid(np.arange(w), np.arange(h))
        corrx, corry = find_corresponding_pixel(xcoords, ycoords, w, h, n)

        equi = cubemap[corry, corrx, :3]
        res = Image.fromarray((np.clip(equi, 0, 1) * 255).astype(np.uint8), mode="RGB")
        res.save(f"{convertDir}/i_{mapName}_sky.tif")

        # create GDTs for the skybox assets
        gdt.add(f"i_{mapName}_sky", "image", {
            "imageType": "Texture",
            "type": "image",
            "baseImage": f"texture_assets\\\\corvid\\\\i_{mapName}_sky.tif",
            "semantic": "HDR",
            "compressionMethod": "compressed",
            "coreSemantic": "HDR",
            "streamable": "1",
            "noMipMaps": "1"
        })
        gdt.add(f"{mapName}_sky_mtl", "material", {
            "materialCategory": "Geometry",
            "materialType": "sky_latlong_hdr",
            "colorMap": f"i_{mapName}_sky",
            "surfaceType": "<none>",
            "glossSurfaceType": "<full>",
            "usage": "<not in editor>",
            "noImpact": "1",
            "noMarks": "1",
            "nonColliding": "1",
            "noCastShadow": "1",
            "skyHalfSpace": "1",
            "skyStops": "3",
            "skySize": "8000"

        })

        gdt.add(f"{mapName}_skybox", "xmodel", {
            "filename": f"t6_props\\\\vista\\\\skybox\\\\t6_skybox.xmodel_bin",
            "type": "rigid",
            "skinOverride": f"mtl_skybox_default {mapName}_sky_mtl\\r\\n",
            "BulletCollisionLOD": "None"
        })

        suncolor = worldSpawnSettings.get("suncolor", vec3(1, 1, 1))
        sunbrightness = worldSpawnSettings.get("sunlight", 1.5)

        # Use raw Source angles for BO3 SSI conversion
        # Source pitch: counter-clockwise (-90 = down)
        # BO3 SSI pitch: positive = downward (90 = down)
        source_pitch = worldSpawnSettings.get("source_sun_pitch", 0)
        source_yaw = worldSpawnSettings.get("source_sun_yaw", 0)
        bo3_pitch = -source_pitch
        bo3_yaw = source_yaw

        # Source brightness to BO3 stops (logarithmic scale)
        sunstops = round(log2(max(sunbrightness, 0.01)) + 14, 2)

        gdt.add(f"{mapName}_ssi", "ssi", {
            "bounceCount": "4",
            "colorSRGB": f"{Vec2Str(suncolor)} 1",
            "dynamicShadow": "1",
            "enablesun": "1",
            "ev": "0",
            "evcmp": "0",
            "evmax": "31",
            "evmin": "-32",
            "penumbra_inches": "1",
            "pitch": bo3_pitch,
            "skyboxmodel": f"{mapName}_skybox",
            "stops": sunstops,
            "type": "ssi",
            "yaw": bo3_yaw
        })
    else:
        gdt.add(f"{mapName}_sky", "material", {
            "materialType": "sky",
            "usage": "sky",
            "locale_tools": "1",
            "sort": "skybox - horizon",
            "surfaceType": "<none>",
            "noLightmap": "1",
            "noCastShadow": "1",
            "noReceiveDynamicShadow": "1",
            "nopicmipColor": "1",
            "sky": "1",
            "colorMap": f"texture_assets\\\\corvid\\\\{mapName}_sky_ft.tga"
        })
    return gdt

def exportMinimap(mapName: str, dir: SourceDir, game="WaW", outDir=""):
    gdt = Gdt()
    
    # if it's a decompiled map, we need to remove that suffix
    if mapName.endswith("_d"):
        mapName = mapName[0:-2].lower()
    elif mapName.endswith("_decompiled"):
        mapName = mapName[0:-11].lower()

    ext = "png" if game == "BO3" else "tga" # file extension

    from .AssetConverter import convertImage
    from io import BytesIO

    overview = dir.read_text(f"resource/overviews/{mapName}.txt", silent=True)

    if overview is None:
        return None, None, None

    overview = fixVmt(overview)

    data = parse_vdf(overview)
    data = data[list(data)[0]]

    if "material" not in data:
        return None, None, None

    image = None
    # csgo uses dds images for radars whereas older games use vtf images
    dds_data = dir.read_bytes(f"resource/overviews/{data['material']}_radar.dds", silent=True)
    if dds_data is not None:
        image = Image.open(BytesIO(dds_data))
        image.save(f"{outDir}/texture_assets/corvid/{mapName}_radar.{ext}")
    else:
        vmtText = dir.read_text(f"materials/{data['material']}_radar.vmt", silent=True)
        if vmtText is not None:
            mat = parse_vdf(fixVmt(vmtText))
            mat = mat[list(mat)[0]]
            if "$basetexture" in mat:
                vtfData = dir.read_bytes("materials/" + mat["$basetexture"] + ".vtf", silent=True)
                if vtfData is None:
                    return None, None, None
            convertImage(vtfData, f"{outDir}/texture_assets/corvid/{mapName}_radar.{ext}", "rgb")
            image = Image.open(f"{outDir}/texture_assets/corvid/{mapName}_radar.{ext}")
        else:
            return None, None, None

    if "rotate" in data and data["rotate"] != "1":
        image = image.rotate(90)
    
    image.save(f"{outDir}/texture_assets/corvid/{mapName}_radar.{ext}")

    if game == "BO3":
        gdt.add(f"i_{mapName}_minimap", "image",{
            "imageType": "Texture",
            "type": "image",
            "baseImage": f"texture_assets\\\\corvid\\\\{mapName}_radar.png",
            "semantic": "2d",
            "compressionMethod": "compressed",
            "coreSemantic": "Linear4ch",
            "streamable": "1",
            "clampU": "1",
            "clampV": "1"
        })

        gdt.add(f"{mapName}_minimap", "material",{
            "colorMap": f"i_{mapName}_minimap",
            "materialType": "2d_add"
        },
        "base:local")


    else:
        gdt.add(f"{mapName}_minimap", "material", {
            "materialType": "2d",
            "surfaceType": "<none>",
            "usage": "<not in editor>",
            "colorMap": f"texture_assets\\\\corvid\\\\{mapName}_radar.tga",
            "tileColor": "no tile",
            "filterColor": "nomip bilinear",
            "nopicmipColor": "1"
        })

    return gdt, float(data["pos_x"]), float(data["pos_y"])
