from os import remove
from typing import Dict, List, Tuple
from Formats.Source.SourceModel import SourceModel
from Formats.CoD.Gdt import Gdt, GdtEntry
from Helpers.MathHelpers import Vec2Str
from Libs.PyCoD.xmodel import Model
from Helpers.FileHelpers import NewPath

def ConvertModel(model: SourceModel) -> str:
    res = (
        "MODEL\n"
        "VERSION 6\n"

        "NUMBONES 1\n"
        'BONE 0 -1 "tag_origin"\n'

        "BONE 0\n"
        "OFFSET 0.000000 0.000000 0.000000\n"
        "SCALE 1.000000 1.000000 1.000000\n"
        "X 1.000000 0.000000 0.000000\n"
        "Y 0.000000 1.000000 0.000000\n"
        "Z 0.000000 0.000000 1.000000\n\n"
    )

    numVerts = 0
    verts = ""
    numFaces = 0
    faces = ""
    objects = ""

    v = 0
    f = 0

    for g, group in enumerate(model.groups):
        numVerts += len(group.vertices)

        for vert in group.vertices:
            verts += (
                f"VERT {v}\n"
                f"OFFSET {Vec2Str(vert)}\n"
                "BONES 1\n"
                "BONE 0 1.000000\n\n"
            )
            v += 1

        for face in group.faces:
            mat_idx, v1, v2, v3 = face
            faces += f"TRI {g} {mat_idx} 0 0\n"

            for pv in [v1, v3, v2]:
                vert_idx, uv, normal = pv[0], group.uvs[pv[1]], group.normals[pv[2]]
                faces += (
                    f"VERT {vert_idx}\n"
                    f"NORMAL {Vec2Str(normal)}\n"
                    "COLOR 1.000000 1.000000 1.000000 1.000000\n"
                    f"UV 1 {Vec2Str(uv)}\n\n"
                )

            f += 1

        numFaces += f

        objects += f'OBJECT {g} "{group.name}"\n'
    
    res += f"NUMVERTS {numVerts}\n"
    res += verts
    res += "\n"

    res += f"NUMFACES {numFaces}\n"
    res += faces
    res += "\n"

    res += f"NUMOBJECTS {len(model.groups)}\n"
    res += objects
    res += "\n\n"

    res += f"NUMMATERIALS {len(model.materials)}\n"

    for material in model.materials:
        res += (
            f'MATERIAL 0 "{material}" "Phong" ""\n'
            "COLOR 0.000000 0.000000 0.000000 1.000000\n"
            "TRANSPARENCY 0.000000 0.000000 0.000000 1.000000\n"
            "AMBIENTCOLOR 0.588235 0.588235 0.588235 1.000000\n"
            "INCANDESCENCE 0.000000 0.000000 0.000000 1.000000\n"
            "COEFFS 1.000000 0.000000\n"
            "GLOW 0.000000 0\n"
            "REFRACTIVE 6 1.000000\n"
            "SPECULARCOLOR 0.000000 0.000000 0.000000 1.000000\n"
            "REFLECTIVECOLOR 0.000000 0.000000 0.000000 1.000000\n"
            "REFLECTIVE 1 1.000000\n"
            "BLINN 0.300000 1.000000\n"
            "PHONG -1.000000\n\n"
        )

    return res

def ConvertModels(models: Dict[str, SourceModel], exportPath, exportBin=False):
    for name, model in models.items():
        rawModelString = ConvertModel(model)
        modelPath = f"{exportPath}/model_export/Corvid/{NewPath(name[:-4])}"

        with open(modelPath + ".xmodel_export", "w") as file:
            file.write(rawModelString)

        if exportBin:
            Model.FromFile_Raw(f"{modelPath}.xmodel_export").WriteFile_Bin(f"{modelPath}.xmodel_bin")
            remove(f"{modelPath}.xmodel_export")

def CreateModelGdt(models: Dict[str, SourceModel], tints: Dict[str, List[Tuple[int, int, int]]], skins: Dict[str, List[int]], exportBin=False) -> Gdt:
    res = Gdt()
    ext = "xmodel_bin" if exportBin else "xmodel_export"

    for name, model in models.items():
        entryName = NewPath(name[:-4]) # remove the extension

        # create a gdt entry for each model
        res[f"m_{entryName}"] = GdtEntry(f"m_{entryName}", "xmodel", {
            "collisionLOD" if exportBin else "BulletCollisionLOD": "High",
            "filename": f"Corvid\\\\{entryName}.{ext}",
            "type": "rigid"
        })

        if name in skins:
            for skin in skins[name]:
                # sometimes mappers change the skin KVP of models that don't have skins
                if skin > len(model.skinGroups) - 1:
                    continue

                skinOverride = []
                group = model.skinGroups[skin]

                for i, _skin in enumerate(group):
                    skinOverride.append((model.materials[i], _skin))
                
                res[f"m_{entryName}_skin{skin}"] = GdtEntry(f"m_{entryName}_skin{skin}", "xmodel", {
                    "collisionLOD" if exportBin else "BulletCollisionLOD": "High",
                    "filename": f"Corvid\\\\{entryName}.{ext}",
                    "type": "rigid",
                    "skinOverride": "\\r\\n".join([f"{oldSkin} {newSkin}" for oldSkin, newSkin in skinOverride])
                })

        if name in tints:
            skinOverride = []
            for tint in tints[name]:
                for i, mat in enumerate(model.materials):
                    skinOverride.append((mat, f"{mat}_{tint}"))
                
                res[f"m_{entryName}_{tint}"] = GdtEntry(f"m_{entryName}_{tint}", "xmodel", {
                    "collisionLOD" if exportBin else "BulletCollisionLOD": "High",
                    "filename": f"Corvid\\\\{entryName}.{ext}",
                    "type": "rigid",
                    "skinOverride": "\\r\\n".join([f"{oldSkin} {newSkin}" for oldSkin, newSkin in skinOverride])
                })

    return res
