import os, shutil, zipfile, glob, sys, tempfile, pefile
SRC='py/tools'; OUT='dist/QiyosJadval'
assert not os.path.exists(OUT)
skip_dirs={'include','libs','test','idlelib','tkinter','turtledemo','ensurepip','lib2to3','venv','pydoc_data','site-packages','__pycache__','sqlite3','tcl'}
skip_files=('tcl','tk','_tkinter','_test','sqlite3','_sqlite3','_msi','winsound')
def ign(d,names):
    out=[]
    for n in names:
        p=os.path.join(d,n)
        if os.path.isdir(p) and n in skip_dirs: out.append(n)
        elif os.path.isfile(p) and os.path.basename(d)=='DLLs' and n.lower().startswith(skip_files): out.append(n)
    return out
shutil.copytree(SRC, OUT+'/runtime', ignore=ign)
sp=OUT+'/runtime/Lib/site-packages'; os.makedirs(sp)
tmp=tempfile.mkdtemp(dir='.')
for w in ('PyMuPDF','pillow','PySide6_Essentials','shiboken6'):
    zipfile.ZipFile(glob.glob('whl/%s-*.whl'%w)[0]).extractall(tmp)
# to'liq ko'chiriladiganlar
for d in ('pymupdf','fitz','PIL','shiboken6'):
    shutil.copytree(os.path.join(tmp,d), os.path.join(sp,d), ignore=shutil.ignore_patterns('__pycache__','*.pyi','*.lib','include','mupdf-devel'))
# PySide6: faqat kerakli qismlar (DLL bog'liqliklari yopilmasi bilan)
P=os.path.join(tmp,'PySide6'); Q=os.path.join(sp,'PySide6'); os.makedirs(Q)
roots=['QtCore.pyd','QtGui.pyd','QtWidgets.pyd','pyside6.abi3.dll','plugins/platforms/qwindows.dll',
       'plugins/imageformats/qico.dll','plugins/styles/qmodernwindowsstyle.dll']
have={f.lower():f for f in os.listdir(P)}
need=set(); todo=list(roots); deps_ext=set()
while todo:
    r=todo.pop()
    if r in need: continue
    path=os.path.join(P,r)
    if not os.path.exists(path): print('YO\'Q:',r); continue
    need.add(r)
    pe=pefile.PE(path, fast_load=True); pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY['IMAGE_DIRECTORY_ENTRY_IMPORT']])
    for imp in getattr(pe,'DIRECTORY_ENTRY_IMPORT',[]):
        n=imp.dll.decode().lower()
        if n in have: todo.append(have[n])
        else: deps_ext.add(n)
for f in os.listdir(P):
    fl=f.lower()
    if fl.startswith(('msvcp','vcruntime','concrt')) and fl.endswith('.dll'): need.add(f)
    if f in ('__init__.py','_config.py','_git_pyside_version.py'): need.add(f)
for r in sorted(need):
    os.makedirs(os.path.dirname(os.path.join(Q,r)), exist_ok=True); shutil.copy2(os.path.join(P,r), os.path.join(Q,r))
if os.path.isdir(os.path.join(P,'support')): shutil.copytree(os.path.join(P,'support'), os.path.join(Q,'support'), ignore=shutil.ignore_patterns('__pycache__'))
print('PySide6 saqlandi:',sorted(need)); print('tashqi DLLlar:',sorted(deps_ext))
# pymupdf / shiboken / PIL bog'liqliklari tekshiruvi
for base in ('pymupdf','shiboken6','PIL'):
    d=os.path.join(sp,base); local={f.lower() for f in os.listdir(d)} | {f.lower() for f in os.listdir(Q)} | {f.lower() for f in os.listdir(OUT+'/runtime')}
    for f in os.listdir(d):
        if f.lower().endswith(('.pyd','.dll')):
            pe=pefile.PE(os.path.join(d,f), fast_load=True); pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY['IMAGE_DIRECTORY_ENTRY_IMPORT']])
            ext=[i.dll.decode() for i in getattr(pe,'DIRECTORY_ENTRY_IMPORT',[]) if i.dll.decode().lower() not in local and not i.dll.decode().lower().startswith(('api-ms','kernel32','user32','gdi32','advapi32','ws2_32','shell32','ole32','msvcrt','ucrtbase','crypt32','bcrypt','oleaut32','comdlg32','winmm','version','shlwapi','ntdll','imm32','secur32','wsock32','psapi','userenv','netapi32','iphlpapi','dwmapi','uxtheme','setupapi','dnsapi','authz','mpr','winhttp','comctl32','d3d','dxgi','dwrite','wtsapi32','shcore','opengl32'))]
            if ext: print(base,f,'->',ext)
shutil.rmtree(tmp)
