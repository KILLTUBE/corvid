from modules.vdfutils import parse_vdf
from os.path import basename, splitext, dirname
from shutil import copy, copyfile
from glob import glob
from .Static import fixVmt, uniqueName
from .Gdt import Gdt
from tempfile import gettempdir
from .AssetConverter import getTexSize
from SourceIO.source1.mdl.mdl_file import Mdl
from pathlib import Path
from .SourceDir import SourceDir

tempDir = f"{gettempdir()}/corvid"

def copyMaterials(mats, dir: SourceDir):
    res = []
    for mat in mats:
        name = basename(mat)
        dir.copy(f"materials/{mat}.vmt", f"{tempDir}/mat/{name}.vmt")
        res.append(name)
    return res

def copyTextures(mats, dir: SourceDir, mdl=False):
    res = {
        "sizes": {}, # save the dimensions of $basetexture
        "colorMaps": [],
        "colorMapsAlpha": [],
        "envMaps": [],
        "envMapsAlpha": [],
        "normalMaps": [],
        "revealMaps": [],
        "vmts": {} # save vmt data to create GDT's later
    }
    if not mdl:
        vmtDir, vtfDir = "mat", "matTex"
    else:
        vmtDir, vtfDir = "mdlMats", "mdlTex"
    for file in mats:
        name = basename(file)
        print(name)
        vmt = parse_vdf(fixVmt(open(f"{tempDir}/{vmtDir}/{name}.vmt").read()))
        res["vmts"][name] = vmt
        shader = list(vmt)[0]
        mat = vmt[shader]
        baseTexture = mat["$basetexture"].strip()
        name = basename(baseTexture)
        dir.copy(f"materials/{baseTexture}.vtf", f"{tempDir}/{vtfDir}/{name}.vtf")
        if not mdl: # we don't need to get the dimensions of model textures
            res["sizes"][file.strip()] = getTexSize(f"{tempDir}/{vtfDir}/{name}.vtf")
        if "$translucent" in mat or "$alpha" in mat or "$alphatest" in mat:
            res["colorMapsAlpha"].append(name)
        else:
            res["colorMaps"].append(name)
        if "$bumpmap" in mat:
            bumpMap = mat["$bumpmap"].strip()
            name: str = basename(bumpMap)
            dir.copy(f"materials/{bumpMap}.vtf", f"{tempDir}/{vtfDir}/{name}.vtf")
            res["normalMaps"].append(name)
        if "$envmapmask" in mat:
            envMap: str = mat["$envmapmask"].strip()
            name = basename(envMap)
            dir.copy(f"materials/{envMap}.vtf", f"{tempDir}/{vtfDir}/{name}.vtf")
            res["envMaps"].append(name)
        if "$blendmodulatetexture" in mat:
            revealMap: str = mat["$blendmodulatetexture"].strip()
            name = basename(revealMap)
            dir.copy(f"materials/{revealMap}.vtf", f"{tempDir}/{vtfDir}/{name}.vtf")
            res["revealMaps"].append(name)
        if "$basetexture2" in mat:
            basetexture2 = mat["$basetexture2"].strip()
            name: str = basename(basetexture2)
            dir.copy(f"materials/{basetexture2}.vtf", f"{tempDir}/{vtfDir}/{name}.vtf")
            res["colorMaps"].append(name)
            res["sizes"][file.strip() + "_"] = getTexSize(f"{tempDir}/{vtfDir}/{name}.vtf")
        if "$bumpmap2" in mat:
            bumpMap2 = mat["$bumpmap2"].strip()
            name: str = basename(bumpMap2)
            dir.copy(f"materials/{bumpMap2}.vtf", f"{tempDir}/{vtfDir}/{name}.vtf")
            res["normalMaps"].append(name)
        if "$envmapmask2" in mat:
            envMap2: str = mat["$envmapmask2"].strip()
            name = basename(envMap2)
            dir.copy(f"materials/{envMap2}.vtf", f"{tempDir}/{vtfDir}/{name}.vtf")
            res["envMaps"].append(name)
        if "$basealphaenvmapmask" in mat:
            res["envMapsAlpha"].append(basename(mat["$basetexture"].strip()))
        if "$basealphaenvmapmask2" in mat:
            res["envMapsAlpha"].append(basename(mat["$basetexture2"].strip()))
        if "$normalmapalphaenvmapmask" in mat and "$bummap" in mat:
            res["envMapsAlpha"].append(basename(mat["$bumpmap"].strip()))
        if "$normalmapalphaenvmapmask2" in mat and "$bummap2" in mat:
            res["envMapsAlpha"].append(basename(mat["$bumpmap2"].strip()))
    return res

def copyModels(models, dir: SourceDir):
    for model in models:
        name = splitext(basename(model))[0]
        path = dirname(model)
        dir.copy(f"{model}", f"{tempDir}/mdl/{name}.mdl")
        for ext in ["dx90.vtx", "vtx", "vvd"]:
            dir.copy(f"{path}/{name}.{ext}", f"{tempDir}/mdl/{name}.{ext}", True)

def copyModelMaterials(models, dir: SourceDir):
    materials = []
    for model in models:
        name = basename(model)
        mdl = Mdl(f"{tempDir}/mdl/{name}")
        mdl.read()
        for material in mdl.materials:
            for path in mdl.materials_paths:
                path = Path(path).as_posix()
                name = basename(material.name)
                name = f"{path}/{name}".lower()
                if name not in materials:
                    materials.append((name, mdl.header.surface_prop))

                name = Path(material.name).as_posix().lower()
                if name not in materials:
                    materials.append((name, mdl.header.surface_prop))
                    
    for mat, surface_prop in materials:
        name = basename(mat)
        if dir.copy(f"materials/{mat}.vmt", f"{tempDir}/mdlMats/{name}.vmt"):
            # unlike CoD, the surface type of a model isn't defined in the material so we have to copy that value
            # from the model and paste it in the materials it uses
            try:
                file = open(f"{tempDir}/mdlMats/{name}.vmt")
                new = file.read().replace("{\n", f'{{\n"$surfaceprop" "{surface_prop}" // corvid\n', 1)
                open(f"{tempDir}/mdlMats/{name}.vmt", "w").write(new)
            except:
                pass
    
    return [i[0] for i in materials]

def surfaceType(surface):
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
        "zombieflesh": ["flesh", "flesh"],
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
    if surface in surfaces:
        return {
            "surface": surfaces[surface][0],
            "gloss": surfaces[surface][1],
        }
    else:
        return {
            "surface": "<none>",
            "gloss": "<full>"
        }
    
def createMaterialGdt(vmts: dict, BO3=False):
    if BO3:
        return createMaterialGdtBo3(vmts)
    gdt = Gdt()
    textureDir = "texture_assets\\\\corvid\\\\"
    ext, _ext = ".tga", "_.tga"
    if BO3:
        textureDir = "i_"
        ext, _ext = "", ""
    for name, vmt in vmts.items():
        shader = list(vmt)[0]
        mat = vmt[shader]
        data = {}
        if shader == "lightmappedgeneric" or shader == "worldvertextransition":
            data["materialType"] = "world phong"
        elif shader == "unlitgeneric":
            data["materialType"] = "world unlit"
        elif shader == "vertexlitgeneric":
            data["materialType"] = "model phong"
        else:
            data["materialType"] = "world phong"
        
        data["colorMap"] = textureDir + uniqueName(mat["$basetexture"].strip()) + ext

        if "$bumpmap" in mat and "$ssbump" not in mat:
            data["normalMap"] = textureDir + uniqueName(mat["$bumpmap"].strip()) + ext
        if "$envmapmask" in mat:
            data["cosinePowerMap"] = textureDir + uniqueName(mat["$envmapmask"].strip()) + ext
        if "$basealphaenvmapmask" in mat and "$envmapmask" not in mat:
            data["cosinePowerMap"] = textureDir + uniqueName(mat["$basetexture"].strip()) + _ext
        if "$normalmapalphaenvmapmask" in mat and "$envmapmask" not in mat and "$bumpmap" in mat:
            data["cosinePowerMap"] = textureDir + uniqueName(mat["$bumpmap"].strip()) + _ext

        if "$nocull" in mat:
            data["cullFace"] = "None"

        if "$surfaceprop" in mat:
            data["surfaceType"] = surfaceType(mat["$surfaceprop"].strip())["surface"]
        else:
            data["surfaceType"] = "<none>"

        if "$alphatest" in mat or "$alpha" in mat:
            data["alphaTest"] = "GE128"
        if "$translucent" in mat:
            data["blendFunc"] = "Blend"
        
        if "$basetexture2" in mat:
            data2 = {}
            data2["materialType"] = "world phong"
            data2["colorMap"] = textureDir + uniqueName(mat["$basetexture2"].strip()) + ext
            data["blendFunc"] = "Blend"

            if "$bumpmap2" in mat and "$ssbump" not in mat:
                data2["normalMap"] = textureDir + uniqueName(mat["$bumpmap2"].strip()) + ext
            if "$envmapmask2" in mat:
                data["cosinePowerMap2"] = textureDir + uniqueName(mat["$envmapmask2"].strip()) + ext
            if "$basealphaenvmapmask2" in mat and "$envmapmask2" not in mat:
                data2["cosinePowerMap2"] = textureDir + uniqueName(mat["$basetexture2"].strip()) + _ext
            if "$normalmapalphaenvmapmask2" in mat and "$envmapmask2" not in mat and "$bumpmap2" in mat:
                data2["cosinePowerMap2"] = textureDir + uniqueName(mat["$bumpmap2"].strip()) + _ext

            if "$surfaceprop2" in mat:
                data2["surfaceType"] = surfaceType(mat["$surfaceprop2"].strip())["surface"]
            else:
                data2["surfaceType"] = "<none>"

            if "$alphatest" in mat or "$alpha" in mat:
                data2["alphaTest"] = "GE128"
            data, data2 = data2, data

            gdt.add(name.strip() + "_", "material", data2)

        gdt.add(name.strip(), "material", data)
    return {
        "gdt": gdt.toStr(),
        "bat": gdt.toBat()
    }

def createMaterialGdtBo3(vmt: dict):
    gdt = Gdt()

def createModelGdt(models, BO3=False):
    gdt = Gdt()
    for model in models:
        name = splitext(basename(model))[0].lower()
        gdt.add(name, "xmodel", {
            "collisionLOD" if not BO3 else "BulletCollisionLOD": "High",
            "filename": f"corvid\\\\{name}." + "xmodel_export" if not BO3 else "xmodel_bin",
            "type": "rigid",
            "physicsPreset": "default"
        })
    return {
        "gdt": gdt.toStr(),
        "bat": gdt.toBat()
    }

def createImageGdt(images):
    gdt = Gdt()
    for file in images["colorMaps"]:
        gdt.add(f"i_{file}", "image", {
            "imageType": "Texture",
            "type": "image",
            "baseImage": f"texture_assets\\\\corvid\\\\{file}.tif",
            "semantic": "diffuseMap",
            "compressionMethod": "compressed high color",
            "coreSemantic": "sRGB3chAlpha",
            "streamable": "1"
        })
    for file in images["colorMapsAlpha"]:
        gdt.add(f"i_{file}", "image", {
            "imageType": "Texture",
            "type": "image",
            "baseImage": f"texture_assets\\\\corvid\\\\{file}.tif",
            "semantic": "diffuseMap",
            "compressionMethod": "compressed high color",
            "coreSemantic": "sRGB3chAlpha",
            "streamable": "1"
        })
    for file in images["normalMaps"]:
        gdt.add(f"i_{file}", "image", {
            "imageType": "Texture",
            "type": "image",
            "baseImage": f"texture_assets\\\\corvid\\\\{file}.tif",
            "semantic": "normalMap",
            "compressionMethod": "compressed",
            "coreSemantic": "Normal",
            "streamable": "1"
        })
    for file in images["envMaps"]:
        gdt.add(f"i_{file}", "image", {
            "imageType": "Texture",
            "type": "image",
            "baseImage": f"texture_assets\\\\corvid\\\\{file}.tif",
            "semantic": "glossMap",
            "compressionMethod": "compressed",
            "coreSemantic": "Linear1ch",
            "streamable": "1"
        })
    for file in images["envMapsAlpha"]:
        gdt.add(f"i_{file}_", "image", {
            "imageType": "Texture",
            "type": "image",
            "baseImage": f"texture_assets\\\\corvid\\\\{file}_.tif",
            "semantic": "glossMap",
            "compressionMethod": "compressed",
            "coreSemantic": "Linear1ch",
            "streamable": "1"
        })
    for file in images["revealMaps"]:
        gdt.add(f"i_{file}", "image", {
            "imageType": "Texture",
            "type": "image",
            "baseImage": f"texture_assets\\\\corvid\\\\{file}.tif",
            "semantic": "revealMap",
            "compressionMethod": "compressed",
            "coreSemantic": "Linear1ch",
            "streamable": "1"
        })
    return gdt.toStr()