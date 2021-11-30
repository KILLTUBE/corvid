import os
from os.path import basename, splitext, exists, dirname
os.environ["NO_BPY"] = "1"
from PIL import Image, ImageOps
from SourceIO.source1.vtf.VTFWrapper import VTFLib
from .Vector2 import Vector2
from .Vector3 import Vector3
from tempfile import gettempdir
from .Static import newPath
from PyCoD import Model
from .ModelConverter import convertModel

tempDir = gettempdir() + "/corvid"

def convertImage(src, dest, format="rgba", invert=False, resize=False):
    if not exists(src):
        print(f"{src} could not be found")
        return False
    format = format.upper()
    image = VTFLib.VTFLib()
    image.image_load(src)
    width = image.width()
    height = image.height()
    rgba = Image.frombuffer("RGBA", (width, height), image.convert_to_rgba8888().contents)
    if resize:
        rgba.resize((512, 512))
    if invert:
        rgba = ImageOps.invert(rgba.convert("RGB"))
    if format == "RGBA":
        rgba.save(dest)
    elif format == "RGB":
        rgba.convert("RGB").save(dest)
    elif len(format) == 1:
        rgba.getchannel(format).save(dest)

def convertImages(images, src, dest, ext="tga"):
    images["colorMaps"] = list(dict.fromkeys(images["colorMaps"]))
    images["colorMapsAlpha"] = list(dict.fromkeys(images["colorMapsAlpha"]))
    images["normalMaps"] = list(dict.fromkeys(images["normalMaps"]))
    images["envMaps"] = list(dict.fromkeys(images["envMaps"]))
    images["envMapsAlpha"] = list(dict.fromkeys(images["envMapsAlpha"]))
    images["revealMaps"] = list(dict.fromkeys(images["revealMaps"]))

    total = len(images["colorMaps"] + images["colorMapsAlpha"] + images["normalMaps"] + images["envMaps"] + images["envMapsAlpha"] + images["revealMaps"])
    i = 0

    for file in images["colorMapsAlpha"]:
        print(f"{i}|{total}|done", end=""); i += 1;
        convertImage(f"{tempDir}/{src}/{file}.vtf", f"{tempDir}/converted/{dest}/{file}.{ext}", "rgba")
    for file in images["normalMaps"]:
        print(f"{i}|{total}|done", end=""); i += 1;
        convertImage(f"{tempDir}/{src}/{file}.vtf", f"{tempDir}/converted/{dest}/{file}.{ext}", "rgb")
    for file in images["envMaps"]:
        print(f"{i}|{total}|done", end=""); i += 1;
        convertImage(f"{tempDir}/{src}/{file}.vtf", f"{tempDir}/converted/{dest}/{file}.{ext}", "rgb")
    for file in images["envMapsAlpha"]:
        print(f"{i}|{total}|done", end=""); i += 1;
        convertImage(f"{tempDir}/{src}/{file}.vtf", f"{tempDir}/converted/{dest}/{file}_.{ext}", "a")
    for file in images["revealMaps"]:
        print(f"{i}|{total}|done", end=""); i += 1;
        convertImage(f"{tempDir}/{src}/{file}.vtf", f"{tempDir}/converted/{dest}/{file}.{ext}", "g", True)
    for file in images["colorMaps"]:
        print(f"{i}|{total}|done", end=""); i += 1;
        convertImage(f"{tempDir}/{src}/{file}.vtf", f"{tempDir}/converted/{dest}/{file}.{ext}", "rgb")

def getTexSize(src):
    image = VTFLib.VTFLib()
    image.image_load(src)
    return Vector2(image.width(), image.height())

def convertModels(models, modelTints, modelSkins, game="WaW"):
    codModel = Model()
    mdlDir = f"{tempDir}/mdl"
    convertDir = f"{tempDir}/converted/model_export/corvid"
    total = len(models)
    i = 0
    for model in models:
        print(f"{i}|{total}|done", end=""); i += 1
        model = splitext(newPath(model))[0]
        # convert models with tints
        if game == "BO3" and model in modelTints:
            for tint in modelTints[model]:
                hex = Vector3.FromStr(tint).toHex()
                convertModel(f"{mdlDir}/{model}", convertDir, tint=hex)
                try:
                    codModel.LoadFile_Raw(f"{convertDir}/{model}_{hex}.xmodel_export")
                    codModel.WriteFile_Bin(f"{convertDir}/{model}_{hex}.xmodel_bin")
                except:
                    print(f"Could not convert {model}_{hex} to xmodel_bin...")
                else:
                    os.remove(f"{convertDir}/{model}_{hex}.xmodel_export")
        convertModel(f"{mdlDir}/{model}", convertDir)

        # convert models with skins
        for skin in modelSkins[model]:
            convertModel(f"{mdlDir}/{model}", convertDir, skin=skin)
            if game == "BO3":
                try:
                    codModel.LoadFile_Raw(f"{convertDir}/{model}_skin{skin}.xmodel_export")
                    codModel.WriteFile_Bin(f"{convertDir}/{model}_skin{skin}.xmodel_bin")
                except:
                    print(f"Could not convert {model} to xmodel_bin...")
                else:
                    os.remove(f"{convertDir}/{model}_skin{skin}.xmodel_export")

        if game == "BO3":
            try:
                codModel.LoadFile_Raw(f"{convertDir}/{model}.xmodel_export")
                codModel.WriteFile_Bin(f"{convertDir}/{model}.xmodel_bin")
            except:
                print(f"Could not convert {model} to xmodel_bin...")
            else:
                os.remove(f"{convertDir}/{model}.xmodel_export")
