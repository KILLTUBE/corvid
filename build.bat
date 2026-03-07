@echo off
if exist dist rd /S /Q dist
pyinstaller app.py -F -i res/icon.ico -n "Corvid" --windowed --hidden-import=glm --add-binary "SourceIO/library/utils/pylib/windows/pylib.pyd;SourceIO/library/utils/pylib/windows"
mkdir "dist\res"
xcopy /s /e "res" "dist\res\"
