# build.spec
# Tells PyInstaller exactly how to bundle the app for Windows

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=['customtkinter'],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    name='CutListOptimizer',
    debug=False,
    console=False,        # False = no black terminal window behind the app
    icon=None,            # add 'icon.ico' here later if you want a custom icon
)