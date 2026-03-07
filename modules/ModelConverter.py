import os
import numpy as np

os.environ["NO_BPY"] = "1"

from os.path import exists
from posixpath import basename
from tempfile import gettempdir
from typing import Dict, List
from glm import vec2, vec3
from SourceIO.library.models.mdl.v49.mdl_file import MdlV49
from SourceIO.library.models.vtx import open_vtx
from SourceIO.library.models.vvd import Vvd
from SourceIO.library.utils import FileBuffer
from PyCoD import Model as CoDModel
from PyCoD.xmodel import Bone, Vertex, FaceVertex, Face, Mesh, Material
from .Static import newPath, Vec2Str

def merge_strip_groups(vtx_mesh):
    indices_accumulator = []
    vertex_accumulator = []
    vertex_offset = 0
    for strip_group in vtx_mesh.strip_groups:
        indices_accumulator.append(np.add(strip_group.indices, vertex_offset))
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

def convertModel(filePath, writePath, tint="", skin=0, scale=1.0, game="WaW"):
    tempDir = f"{gettempdir()}/corvid/mdlMats"
    # read mdl, vtx and vvd files
    if not os.path.exists(f"{filePath}.mdl"):
        print(f"Can't find {basename(filePath)}.mdl. Skipping...")
        return
    mdl = MdlV49.from_buffer(FileBuffer(f"{filePath}.mdl"))

    if os.path.exists(f"{filePath}.dx90.vtx"):
        vtx = open_vtx(FileBuffer(f"{filePath}.dx90.vtx"))
    elif os.path.exists(f"{filePath}.vtx"):
        vtx = open_vtx(FileBuffer(f"{filePath}.vtx"))
    else:
        print(f"Can't find vtx file for the model {basename(filePath)}.mdl. Skipping...")
        return

    vvd = Vvd.from_buffer(FileBuffer(f"{filePath}.vvd"))

    # replace the material names when they have different skins
    if skin != 0 and skin < len(mdl.skin_groups):
        for i in range(len(mdl.skin_groups[skin])):
            mdl.materials[i].name = mdl.skin_groups[skin][i].name

    materials = []
    # check for the following and add if a material file exists with that name
    for mat in mdl.materials:
        # if the model contains the full path
        name = newPath(mat.name)
        if exists(f"{tempDir}/{name}.vmt"):
            materials.append(name)
            continue
        
        for path in mdl.materials_paths:
            # if path/materialname exists
            name = newPath(f"{path}/{mat.name}")
            if exists(f"{tempDir}/{name}.vmt"):
                materials.append(name)
                continue

            # sometimes a material might contain both. we don't really need this but it won't hurt to have extra measures.
            name = newPath(f"{path}/{basename(mat.name.replace(chr(92), '/'))}")
            if exists(f"{tempDir}/{name}.vmt"):
                materials.append(name)
                continue

    if tint != "":
        materials = [mat + f"_{tint}" for mat in materials]

    verts: List[vec3] = []
    vertDict: Dict[str, int] = {}
    normals: List[vec3] = []
    uvs: List[vec2] = []
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
            [verts.append(vec3([round(i, 6) for i in (vec3(v) * scale)])) for v in vertices["vertex"]]
            [normals.append(vec3([round(i, 6) for i in vec3(n)])) for n in vertices["normal"]]
            [uvs.append(vec2([round(i, 6) for i in vec2(t)])) for t in vertices["uv"]]

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

    if skin != 0 and tint != "":
        fileName = basename(filePath) + f"_skin{skin}_{tint}"
    elif tint != "":
        fileName = basename(filePath) + f"_{tint}"
    elif skin != 0:
        fileName = basename(filePath) + f"_skin{skin}"
    else:
        fileName = basename(filePath)

    # Build PyCoD Model
    model = CoDModel()

    bone = Bone("tag_origin", parent=-1)
    bone.offset = (0.0, 0.0, 0.0)
    bone.matrix = [(1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)]
    model.bones.append(bone)

    # Build per-mesh vertex lists and faces
    for group_idx, group_name in enumerate(groups):
        mesh = Mesh(group_name)

        group_faces = [f for f in faces if f["group"] == group_idx]

        # Collect unique vertex indices used by this group
        used_global = set()
        for f in group_faces:
            for pt in f["points"]:
                used_global.add(pt["vert"])
        sorted_global = sorted(used_global)
        global_to_local = {g: l for l, g in enumerate(sorted_global)}

        for g in sorted_global:
            v = verts[g]
            mesh.verts.append(Vertex(
                offset=(float(v.x), float(v.y), float(v.z)),
                weights=[(0, 1.0)]
            ))

        for f in group_faces:
            face = Face(mesh_id=group_idx, material_id=int(f["material"]))
            for i, pt in enumerate(f["points"]):
                normal = pt["normal"]
                if normal.x == 0.0 and normal.y == 0.0 and normal.z == 0.0:
                    normal = vec3(0.0, 1.0, 0.0)
                face.indices[i] = FaceVertex(
                    vertex=global_to_local[pt["vert"]],
                    normal=(float(normal.x), float(normal.y), float(normal.z)),
                    color=(1.0, 1.0, 1.0, 1.0),
                    uv=(float(pt["uv"].x), float(pt["uv"].y))
                )
            mesh.faces.append(face)

        model.meshes.append(mesh)

    for mat_name in materials:
        model.materials.append(Material(mat_name, "Phong", {"color": "404.tga"}))

    if game == "BO3":
        model.WriteFile_Bin(f"{writePath}/{fileName}.xmodel_bin", version=7)
    else:
        model.WriteFile_Raw(f"{writePath}/{fileName}.xmodel_export", version=6)