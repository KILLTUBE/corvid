@echo off
if exist dist rd /S /Q dist
REM Corvid.spec bundles pylib.pyd and MSVCP140.dll (required by pylib.pyd)
pyinstaller --noconfirm Corvid.spec
mkdir "dist\res"
xcopy /s /e "res" "dist\res\"
