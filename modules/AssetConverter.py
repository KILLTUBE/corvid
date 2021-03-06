import os
from os.path import basename, splitext, exists, dirname
os.environ["NO_BPY"] = "1"
from PIL import Image
from SourceIO.source1.vtf.VTFWrapper import VTFLib
from .Vector2 import Vector2
from tempfile import gettempdir
from .Static import uniqueName
from subprocess import call
from PyCoD import Model

tempDir = gettempdir() + "/corvid"

def convertImage(src, dest, format="rgba", dds=False):
    if not exists(src):
        print(f"{src} could not be found")
        return False
    format = format.upper()
    image = VTFLib.VTFLib()
    image.image_load(src)
    width = image.width()
    height = image.height()
    rgba = Image.frombuffer("RGBA", (width, height), image.convert_to_rgba8888().contents)
    if format == "RGBA":
        rgba.save(dest)
    elif format == "RGB":
        rgba.convert("RGB").save(dest)
        # convert color maps with no alpha channel to DDS if the texture is being converted for older Cod titles
        if dds:
            name = splitext(basename(dest))[0]
            imageDir = f"{tempDir}/converted/texture_assets/corvid"
            fmt = image.image_format().name
            formats = {
                "ImageFormatDXT1": "-dxt1c",
                "ImageFormatDXT1OneBitAlpha": "-dxt1a",
                "ImageFormatDXT3": "-dxt3",
                "ImageFormatDXT5": "-dxt5"
            }
            fmt = formats[fmt] if fmt in formats else "-dxt5"
            call(["bin/nvdxt.exe", "-file", f"{imageDir}/{name}.tga", "-output", f"{imageDir}/{name}.dds", fmt])
            os.remove(dest) # remove the tga file
    elif len(format) == 1:
        rgba.getchannel(format).save(dest)

def convertImages(images, src, dest, ext="tga"):
    images["colorMaps"] = list(dict.fromkeys(images["colorMaps"]))
    images["colorMapsAlpha"] = list(dict.fromkeys(images["colorMapsAlpha"]))
    images["normalMaps"] = list(dict.fromkeys(images["normalMaps"]))
    images["envMaps"] = list(dict.fromkeys(images["envMaps"]))
    images["envMapsAlpha"] = list(dict.fromkeys(images["envMapsAlpha"]))
    images["revealMaps"] = list(dict.fromkeys(images["revealMaps"]))
    dds = True if ext == "tga" else False
    for file in images["colorMapsAlpha"]:
        print(f"Converting {file}.vtf...")
        convertImage(f"{tempDir}/{src}/{file}.vtf", f"{tempDir}/converted/{dest}/{uniqueName(file)}.{ext}", "rgba", dds)
    for file in images["normalMaps"]:
        print(f"Converting {file}.vtf...")
        convertImage(f"{tempDir}/{src}/{file}.vtf", f"{tempDir}/converted/{dest}/{uniqueName(file)}.{ext}", "rgb")
    for file in images["envMaps"]:
        print(f"Converting {file}.vtf...")
        convertImage(f"{tempDir}/{src}/{file}.vtf", f"{tempDir}/converted/{dest}/{uniqueName(file)}.{ext}", "rgb")
    for file in images["envMapsAlpha"]:
        print(f"Converting {file}.vtf...")
        convertImage(f"{tempDir}/{src}/{file}.vtf", f"{tempDir}/converted/{dest}/{uniqueName(file)}_.{ext}", "a")
    for file in images["revealMaps"]:
        print(f"Converting {file}.vtf...")
        convertImage(f"{tempDir}/{src}/{file}.vtf", f"{tempDir}/converted/{dest}/{uniqueName(file)}.{ext}", "g")
    for file in images["colorMaps"]:
        print(f"Converting {file}.vtf...")
        convertImage(f"{tempDir}/{src}/{file}.vtf", f"{tempDir}/converted/{dest}/{uniqueName(file)}.{ext}", "rgb")

def getTexSize(src):
    image = VTFLib.VTFLib()
    image.image_load(src)
    return Vector2(image.width(), image.height())

def convertModels(models, BO3=False):
    codModel = Model()
    mdlDir = f"{tempDir}/mdl"
    convertDir = f"{tempDir}/converted/model_export/corvid"
    for model in models:
        model = splitext(basename(model))[0]
        print(f"Converting {model}.mdl...")
        call(["bin/mdl2xmodel.exe", f"{mdlDir}/{model}", convertDir])
        if BO3:
            codModel.LoadFile_Raw(f"{convertDir}/{model}.xmodel_export")
            codModel.WriteFile_Bin(f"{convertDir}/{model}.xmodel_bin")
            os.remove(f"{convertDir}/{model}.xmodel_export")
