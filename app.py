from modules.MapExporter import exportMap

file = open("maps/de_mirage_d.vmf")
res = exportMap(file, True)
open("mirage.map", "w").write(res)
