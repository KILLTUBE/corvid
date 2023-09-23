from typing import Any, Dict, List
from mathutils import Vector
from .Entity import Entity
from .Model import Model

class Map:
    __slots__ = ("settings", "entities", "materials", "matSizes", "models", "modelMaterials", "modelData", "modelMaterialData")
    settings: dict
    entities: List[Entity]
    materials: List[str]
    matSizes: Dict[str, Vector]
    models: List[str]
    modelMaterials: List[str]
    modelData: Dict[str, Model]
    modelMaterialData: Dict[str, Any]

    def __init__(self) -> None:
        self.settings = {}
        self.entities = []
        self.materials = []
        self.matSizes = {}
        self.models = []
        self.modelMaterials = []
        self.modelData = {}
        self.modelMaterialData = {}
    
    def __str__(self) -> str:
        raise NotImplementedError()
    
    def AddMaterial(self, material: str):
        material = material.lower().strip()
        if material not in self.materials:
            self.materials.append(material)

    def AddModel(self, model: str):
        model = model.lower()
        if model not in self.models:
            self.models.append(model)

    def Save(self):
        raise NotImplementedError()

    @staticmethod
    def Load(path: str) -> 'Map':
        raise NotImplementedError()
