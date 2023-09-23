
del dist /S /F /Q
pyinstaller main.py -F -i res/icon.ico -n "Corvid" --windowed --add-data "SourceIO/source1/vtf/VTFWrapper/VTFLib.x64.dll;."
@mkdir "./dist/res"
xcopy /s "./res" "./dist/res"
copy .\SourceIO\source1\vtf\VTFWrapper\VTFLib.x64.dll .\dist\res\
