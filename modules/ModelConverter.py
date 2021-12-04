import os
import numpy as np
import time

os.environ["NO_BPY"] = "1"

from os.path import exists
from posixpath import basename
from tempfile import gettempdir
from typing import Dict, List
from SourceIO.source1.mdl.mdl_file import Mdl
from SourceIO.source1.vtx.vtx import Vtx
from SourceIO.source1.vvd.vvd import Vvd
from .Static import newPath
from .Vector3 import Vector3
from .Vector2 import Vector2

def merge_strip_groups(vtx_mesh):
    indices_accumulator = []
    vertex_accumulator = []
    vertex_offset = 0
    for strip_group in vtx_mesh.strip_groups:
        indices_accumulator.append(np.add(strip_group.indexes, vertex_offset))
        vertex_accumulator.append(strip_group.vertexes['original_mesh_vertex_index'].reshape(-1))
        vertex_offset += sum(strip.vertex_count for strip in strip_group.strips)
    return np.hstack(indices_accumulator), np.hstack(vertex_accumulator), vertex_offset

def get_slice(data, start, count=None):
    if count is None:
        count = len(data) - start
    return data[start:start + count]

def merge_meshes(model, vtx_model):
    vtx_vertices = []
    acc = 0
    mat_arrays = []
    indices_array = []
    for n, (vtx_mesh, mesh) in enumerate(zip(vtx_model.meshes, model.meshes)):

        if not vtx_mesh.strip_groups:
            continue

        vertex_start = mesh.vertex_index_start
        indices, vertices, offset = merge_strip_groups(vtx_mesh)
        indices = np.add(indices, acc)
        mat_array = np.full(indices.shape[0] // 3, mesh.material_index)
        mat_arrays.append(mat_array)
        vtx_vertices.extend(np.add(vertices, vertex_start))
        indices_array.append(indices)
        acc += offset

    return vtx_vertices, np.hstack(indices_array), np.hstack(mat_arrays)

def convertModel(filePath, writePath, tint="", skin=0):
    tempDir = f"{gettempdir()}/corvid/mdlMats"
    # read mdl, vtx and vvd files
    mdl = Mdl(f"{filePath}.mdl")
    mdl.read()

    vtx: Vtx
    if os.path.exists(f"{filePath}.dx90.vtx"):
        vtx = Vtx(f"{filePath}.dx90.vtx")
        vtx.read()
    elif os.path.exists(f"{filePath}.vtx"):
        vtx = Vtx(f"{filePath}.dx90.vtx")
        vtx.read()
    else:
        print("Can't find vtx file for the model. Skipping...")
        return

    vvd = Vvd(f"{filePath}.vvd")
    vvd.read()

    # replace the material names when they have different skins
    if skin != 0 and skin < len(mdl.skin_groups):
        for i in range(len(mdl.skin_groups[skin])):
            mdl.materials[i].name = mdl.skin_groups[skin][i]

    materials = []
    # check for the following and add if a material file exists with that name
    for mat in mdl.materials:
        # if the model contains the full path
        name = newPath(mat.name)
        if tint != "":
            name += tint
        if exists(f"{tempDir}/{name}.vmt"):
            materials.append(name)
            continue
        
        for path in mdl.materials_paths:
            # if path/materialname exists
            name = newPath(f"{path}/{mat.name}")
            if tint != "":
                name += tint
            if exists(f"{tempDir}/{name}.vmt"):
                materials.append(name)
                continue

            # sometimes a material might contain both. we don't really need this but it won't hurt to have extra measures.
            name = newPath(f"{path}/{basename(mat.name)}")
            if tint != "":
                name += tint
            if exists(f"{tempDir}/{name}.vmt"):
                materials.append(name)
                continue

    verts: List[Vector3] = []
    vertDict: Dict[str, int] = {}
    normals: List[Vector3] = []
    uvs: List[Vector2] = []
    groups = []
    faces = []
    
    desired_lod = 0
    all_vertices = vvd.lod_data[desired_lod]

    groups.append("corvid_0")

    for mdl_parts, vtx_parts in zip(mdl.body_parts, vtx.body_parts):
        for vtx_model, model in zip(vtx_parts.models, mdl_parts.models):
            if model.vertex_count == 0:
                continue

            model_vertices = get_slice(all_vertices, model.vertex_offset, model.vertex_count)
            vtx_vertices, indices_array, material_indices_array = merge_meshes(model, vtx_model.model_lods[desired_lod])

            indices_array = np.array(indices_array, dtype=np.uint32)
            vertices = model_vertices[vtx_vertices]

            numVerts = len(verts)
            numNormals = len(normals)
            numUVs = len(uvs)
            [verts.append(Vector3.FromArray(v).round(6)) for v in vertices["vertex"]]
            [normals.append(Vector3.FromArray(n).round(6)) for n in vertices["normal"]]
            [uvs.append(Vector2.FromArray(t).round(6)) for t in vertices["uv"]]

            for i in range(0, len(indices_array), 3):
                if i % 1000 == 0 and i != 0:
                    groups.append(f"corvid_{len(groups)}")
                    
                faces.append({
                    "points":[
                        {
                            "vert": numVerts + indices_array[i + 1],
                            "normal": normals[numNormals + indices_array[i + 1]],
                            "uv": uvs[numUVs + indices_array[i + 1]]
                        },
                        {
                            "vert": numVerts + indices_array[i + 2],
                            "normal": normals[numNormals + indices_array[i + 2]],
                            "uv": uvs[numUVs + indices_array[i + 2]]
                        },
                        {
                            "vert": numVerts + indices_array[i],
                            "normal": normals[numNormals + indices_array[i]],
                            "uv": uvs[numUVs + indices_array[i]]
                        }
                    ],
                    "group": (len(groups) - 1),
                    "material": material_indices_array[int(i / 3)]
                })

    if tint != "":
        fileName = basename(filePath) + f"_{tint}"
    elif skin != 0:
        fileName = basename(filePath) + f"_skin{skin}"
    else:
        fileName = basename(filePath)

    with open(f"{writePath}/{fileName}.xmodel_export", "w") as file:
        file.write(
            "// File generated by Corvid | https://github.com/KILLTUBE/corvid\n"
            + "// Written by johndoe | https://github.com/myuce/\n"
            + f"// Original filename: {fileName}.mdl\n"
            + f"// Export time: " + time.strftime("%d/%m/%Y %H:%M:%S") + "\n\n"

            + "MODEL\n"
            + "VERSION 6\n\n"
            
            + "NUMBONES 1\n"
            + 'BONE 0 -1 "tag_origin"\n\n'
            
            + "BONE 0\n"
            + "OFFSET 0.000000 0.000000 0.000000\n"
            + "SCALE 1.000000 1.000000 1.000000\n"
            + "X 1.000000 0.000000 0.000000\n"
            + "Y 0.000000 1.000000 0.000000\n"
            + "Z 0.000000 0.000000 1.000000\n\n"
        )
        
        file.write(f"NUMVERTS {len(verts)}\n\n")
        for i in range(len(verts)):
            file.write(
                f"VERT {i}\n"
                + f"OFFSET {verts[i].x} {verts[i].y} {verts[i].z}\n"
                + "BONES 1\n"
                + "BONE 0 1.000000\n\n"
            )
        
        file.write(f"NUMFACES {len(faces)}\n\n")
        for i in range(len(faces)):
            file.write(f'TRI {faces[i]["group"]} {faces[i]["material"]} 0 0\n')
            for point in faces[i]["points"]:
                if point["normal"].x + point["normal"].y + point["normal"].z == 0.0:
                    point["normal"].y = 1.000000
                file.write(
                    f'VERT {point["vert"]}\n'
                    + f'NORMAL {point["normal"].x} {point["normal"].y} {point["normal"].z}\n'
                    + "COLOR 1.000000 1.000000 1.000000 1.000000\n"
                    + f'UV 1 {point["uv"].x} {point["uv"].y}\n\n'
                )
        
        file.write(f"NUMOBJECTS {len(groups)}\n")
        for i in range(len(groups)):
            file.write(f'OBJECT {i} "{groups[i]}"\n')
        file.write("\n")

        file.write(f"NUMMATERIALS {len(materials)}\n")
        for i in range(len(materials)):
            file.write(
                f'MATERIAL {i} "{materials[i]}" "Phong" "404.tga"\n'
                + "COLOR 0.000000 0.000000 0.000000 1.000000\n"
                + "TRANSPARENCY 0.000000 0.000000 0.000000 1.000000\n"
                + "AMBIENTCOLOR 0.000000 0.000000 0.000000 1.000000\n"
                + "INCANDESCENCE 0.000000 0.000000 0.000000 1.000000\n"
                + "COEFFS 0.800000 0.000000\n"
                + "GLOW 0.000000 0\n"
                + "REFRACTIVE 6 1.000000\n"
                + "SPECULARCOLOR -1.000000 -1.000000 -1.000000 1.000000\n"
                + "REFLECTIVECOLOR -1.000000 -1.000000 -1.000000 1.000000\n"
                + "REFLECTIVE -1 1.000000\n"
                + "BLINN -1.000000 -1.000000\n"
                + "PHONG -1.000000\n\n"
            )