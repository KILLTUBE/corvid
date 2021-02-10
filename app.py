from modules.MapExporter import exportMap

file = open("maps/de_inferno_d.vmf")
res = exportMap(file)
open("inferno.map", "w").write(res)
