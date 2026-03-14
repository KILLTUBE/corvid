class Gdt:
    def __init__(self, entries=None):
        self.entries = entries if entries is not None else {}
        self.CoD2 = False
        self.name = ""
    
    def add(self, name: str, type: str, data: dict, base: str=""):
        self.entries[name] = {
            "name": name,
            "type": type,
            "data": data,
            "base": base
        }
    
    def toStr(self):
        res = "{\n"
        for entry in list(self.entries.values()):
            if entry["base"] != "":
                res += f'\t"{entry["name"]}" ( "{entry["type"]}.gdf" ) [ {entry["base"]} ]\n'
            else:
                res += f'\t"{entry["name"]}" ( "{entry["type"]}.gdf" )\n'
            res += "\t{\n"
            for key, value in entry["data"].items():
                res += f'\t\t"{key}" "{value}"\n'
            res += "\t}\n"
        res += "}\n"
        return res
                
    def toBat(self):
        entries = list(self.entries.values())
        count = len(entries)

        res = "@echo off\n"
        res += "setlocal enabledelayedexpansion\n"
        res += f"set total={count}\n"
        res += "set current=0\n"
        res += "set success=0\n"
        res += "set errors=0\n"
        res += 'set "r1=" & set "r2=" & set "r3=" & set "r4=" & set "r5="\n'
        res += f'if exist "%~n0.log" del "%~n0.log"\n'
        res += "\n"

        for entry in entries:
            name, type = entry["name"], entry["type"]
            if self.CoD2:
                res += f'call :convert "{name}" "source_data\\_{self.name}.gdt" {name}\n'
            else:
                res += f'call :convert "{name}" "{type}" {name}\n'

        res += "\n"
        res += "cls\n"
        res += "echo.\n"
        res += "echo Converting assets !current!/!total!... Success: !success! Error: !errors!\n"
        res += "echo.\n"
        res += "if defined r1 echo !r1!\n"
        res += "if defined r2 echo !r2!\n"
        res += "if defined r3 echo !r3!\n"
        res += "if defined r4 echo !r4!\n"
        res += "if defined r5 echo !r5!\n"
        res += "echo.\n"
        res += "if !errors! GTR 0 (\n"
        res += '    echo Check %~n0.log for error details.\n'
        res += ")\n"
        res += 'if exist "%~n0_tmp.log" del "%~n0_tmp.log"\n'
        res += "rundll32 user32.dll,MessageBeep\n"
        res += "pause\n"
        res += "goto :eof\n"
        res += "\n"

        # Subroutine
        res += ":convert\n"
        res += 'set "asset=%~1"\n'
        res += "set /a current+=1\n"
        if self.CoD2:
            res += 'converter -nopause -single "%~2" %~3 > %~n0_tmp.log 2>&1\n'
        else:
            res += 'converter -nopause -single "%~2" %~3 > %~n0_tmp.log 2>&1\n'
        res += 'type %~n0_tmp.log >> %~n0.log\n'
        res += 'findstr /c:"************ ERROR ************" %~n0_tmp.log >nul 2>&1\n'
        res += "if !ERRORLEVEL! EQU 0 (\n"
        res += "    set /a errors+=1\n"
        res += '    set "mark=X"\n'
        res += ") else (\n"
        res += "    set /a success+=1\n"
        res += '    set "mark=+"\n'
        res += ")\n"
        res += 'set "r5=!r4!" & set "r4=!r3!" & set "r3=!r2!" & set "r2=!r1!" & set "r1=  [!mark!] !asset!"\n'
        res += "cls\n"
        res += "echo.\n"
        res += "echo Converting assets !current!/!total!... Success: !success! Error: !errors!\n"
        res += "echo.\n"
        res += "if defined r1 echo !r1!\n"
        res += "if defined r2 echo !r2!\n"
        res += "if defined r3 echo !r3!\n"
        res += "if defined r4 echo !r4!\n"
        res += "if defined r5 echo !r5!\n"
        res += "goto :eof\n"
        return res
    
    def __add__(self, other: 'Gdt'):
        res = Gdt({**self.entries, **other.entries})
        res.CoD2 = self.CoD2
        res.name = self.name
        return res