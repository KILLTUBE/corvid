import os
import struct
import numpy as np

os.environ["NO_BPY"] = "1"

from posixpath import basename
from typing import Dict, List
from glm import vec2, vec3
from SourceIO.library.models.mdl.v49.mdl_file import MdlV49
from SourceIO.library.models.vtx import open_vtx
from SourceIO.library.models.vvd import Vvd
from SourceIO.library.utils import MemoryBuffer
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

def readSkinFamilies(mdl, mdlBytes):
    """Read the full skin family table (texture indices per skin) from the raw MDL bytes.
    SourceIO truncates skin_groups to the first differing slot, which can leave them empty."""
    header = mdl.header
    families = []
    for family in range(header.skin_family_count):
        offset = header.skin_family_offset + family * header.skin_reference_count * 2
        indices = struct.unpack_from(f"<{header.skin_reference_count}H", mdlBytes, offset)
        families.append([i if i < len(mdl.materials) else 0 for i in indices])
    return families

def convertModel(modelData,writePath, materialNames, tint="", skin=0, scale=1.0, game="WaW"):
    modelName = modelData["name"]
    mdl = MdlV49.from_buffer(MemoryBuffer(modelData["mdl"]))

    vtx_data = modelData.get("dx90.vtx") or modelData.get("vtx")
    if vtx_data is None:
        print(f"Can't find vtx data for the model {modelName}.mdl. Skipping...")
        return

    vtx = open_vtx(MemoryBuffer(vtx_data))
    vvd = Vvd.from_buffer(MemoryBuffer(modelData["vvd"]))

    # material names per mdl material index (copied as strings so the mdl's own objects aren't renamed)
    matNames = [mat.name for mat in mdl.materials]

    # replace the material names when they have different skins
    if skin != 0:
        families = readSkinFamilies(mdl, modelData["mdl"])
        if skin < len(families):
            for i, texIndex in enumerate(families[skin]):
                if i < len(matNames):
                    matNames[i] = mdl.materials[texIndex].name

    materials = []
    # exactly one entry per material index: use the first name that has a material file,
    # otherwise the full-path name (loadModelMaterials creates a 404 material for it)
    for matName in matNames:
        candidates = [newPath(matName)] # if the model contains the full path
        for path in mdl.materials_paths:
            # if path/materialname exists
            candidates.append(newPath(f"{path}/{matName}"))
            # sometimes a material might contain both. we don't really need this but it won't hurt to have extra measures.
            candidates.append(newPath(f"{path}/{basename(matName.replace(chr(92), '/'))}"))
        materials.append(next((name for name in candidates if name in materialNames), candidates[0]))

    if tint != "" and game == "BO3":
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
                idx0 = indices_array[i]
                idx1 = indices_array[i + 1]
                idx2 = indices_array[i + 2]

                # skip degenerate triangles (two or more identical vertices)
                if idx0 == idx1 or idx1 == idx2 or idx0 == idx2:
                    continue

                # also skip zero-area triangles (vertices at the same position)
                v0 = verts[numVerts + idx0]
                v1 = verts[numVerts + idx1]
                v2 = verts[numVerts + idx2]
                if v0 == v1 or v1 == v2 or v0 == v2:
                    continue

                if len(faces) % 1000 == 0 and len(faces) != 0:
                    groups.append(f"corvid_{len(groups)}")

                faces.append({
                    "points":[
                        {
                            "vert": numVerts + idx1,
                            "normal": normals[numNormals + idx1],
                            "uv": uvs[numUVs + idx1]
                        },
                        {
                            "vert": numVerts + idx2,
                            "normal": normals[numNormals + idx2],
                            "uv": uvs[numUVs + idx2]
                        },
                        {
                            "vert": numVerts + idx0,
                            "normal": normals[numNormals + idx0],
                            "uv": uvs[numUVs + idx0]
                        }
                    ],
                    "group": (len(groups) - 1),
                    "material": material_indices_array[int(i / 3)]
                })

    if skin != 0 and tint != "" and game == "BO3":
        fileName = modelName + f"_skin{skin}_{tint}"
    elif tint != "" and game == "BO3":
        fileName = modelName + f"_{tint}"
    elif skin != 0:
        fileName = modelName + f"_skin{skin}"
    else:
        fileName = modelName

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

    # check if the model is far from origin and add a small triangle
    # at origin to prevent "rotation invariant bounds" errors
    if len(verts) > 0:
        vmin = vec3(verts[0])
        vmax = vec3(verts[0])
        for v in verts:
            vmin = vec3(min(vmin.x, v.x), min(vmin.y, v.y), min(vmin.z, v.z))
            vmax = vec3(max(vmax.x, v.x), max(vmax.y, v.y), max(vmax.z, v.z))

        origin_inside = (vmin.x <= 0 <= vmax.x and vmin.y <= 0 <= vmax.y and vmin.z <= 0 <= vmax.z)
        if not origin_inside:
            origin_mesh = Mesh("corvid_origin")
            eps = 0.01
            origin_mesh.verts.append(Vertex(offset=(0.0, 0.0, 0.0), weights=[(0, 1.0)]))
            origin_mesh.verts.append(Vertex(offset=(eps, 0.0, 0.0), weights=[(0, 1.0)]))
            origin_mesh.verts.append(Vertex(offset=(0.0, eps, 0.0), weights=[(0, 1.0)]))
            face = Face(mesh_id=len(model.meshes), material_id=0)
            face.indices[0] = FaceVertex(vertex=0, normal=(0.0, 0.0, 1.0), color=(1.0, 1.0, 1.0, 0.0), uv=(0.0, 0.0))
            face.indices[1] = FaceVertex(vertex=1, normal=(0.0, 0.0, 1.0), color=(1.0, 1.0, 1.0, 0.0), uv=(0.0, 0.0))
            face.indices[2] = FaceVertex(vertex=2, normal=(0.0, 0.0, 1.0), color=(1.0, 1.0, 1.0, 0.0), uv=(0.0, 0.0))
            origin_mesh.faces.append(face)
            model.meshes.append(origin_mesh)

    if game == "BO3":
        model.WriteFile_Bin(f"{writePath}/{fileName}.xmodel_bin", version=7)
    else:
        model.WriteFile_Raw(f"{writePath}/{fileName}.xmodel_export", version=6)
