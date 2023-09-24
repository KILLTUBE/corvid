from Formats.Source.Map import Map as SourceMap
from .MapExporter import ExportMap

def ConvertSource2CoD(path: str, options: dict=None):
    mapData: SourceMap = SourceMap.Load(path, options)
    ExportMap(mapData, options)
