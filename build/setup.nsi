Unicode true
SetCompressor /SOLID lzma
!include "MUI2.nsh"

!define APP "Qiyos Jadval"
!define DIRNAME "QiyosJadval"
!define VER "2.1"

Name "${APP}"
OutFile "QiyosJadval-ornatuvchi.exe"
InstallDir "$LOCALAPPDATA\Programs\${DIRNAME}"
InstallDirRegKey HKCU "Software\${DIRNAME}" "InstallDir"
RequestExecutionLevel user
BrandingText "${APP} ${VER}"

!define MUI_ICON "dist\QiyosJadval\app\icon.ico"
!define MUI_UNICON "dist\QiyosJadval\app\icon.ico"
!define MUI_FINISHPAGE_RUN
!define MUI_FINISHPAGE_RUN_FUNCTION "RunApp"
!define MUI_FINISHPAGE_RUN_TEXT "${APP} dasturini ishga tushirish"

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "Uzbek"

VIProductVersion "2.1.0.0"
VIAddVersionKey /LANG=0 "ProductName" "${APP}"
VIAddVersionKey /LANG=0 "FileDescription" "${APP} o'rnatuvchisi"
VIAddVersionKey /LANG=0 "FileVersion" "${VER}"
VIAddVersionKey /LANG=0 "LegalCopyright" "Bahtiyor Studio"

Function RunApp
  SetOutPath "$INSTDIR"
  Exec '"$INSTDIR\runtime\pythonw.exe" "$INSTDIR\app\main.py"'
FunctionEnd

Section "Dastur"
  SetOutPath "$INSTDIR"
  RMDir /r "$INSTDIR\app"
  File /r "dist\QiyosJadval\*.*"
  WriteUninstaller "$INSTDIR\Ochirish.exe"
  CreateDirectory "$SMPROGRAMS\${APP}"
  CreateShortcut "$SMPROGRAMS\${APP}\${APP}.lnk" "$INSTDIR\runtime\pythonw.exe" '"$INSTDIR\app\main.py"' "$INSTDIR\app\icon.ico" 0
  CreateShortcut "$SMPROGRAMS\${APP}\Dasturni o‘chirish.lnk" "$INSTDIR\Ochirish.exe"
  CreateShortcut "$DESKTOP\${APP}.lnk" "$INSTDIR\runtime\pythonw.exe" '"$INSTDIR\app\main.py"' "$INSTDIR\app\icon.ico" 0
  CreateShortcut "$INSTDIR\${APP}.lnk" "$INSTDIR\runtime\pythonw.exe" '"$INSTDIR\app\main.py"' "$INSTDIR\app\icon.ico" 0
  WriteRegStr HKCU "Software\${DIRNAME}" "InstallDir" "$INSTDIR"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${DIRNAME}" "DisplayName" "${APP}"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${DIRNAME}" "DisplayVersion" "${VER}"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${DIRNAME}" "DisplayIcon" "$INSTDIR\app\icon.ico"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${DIRNAME}" "Publisher" "Bahtiyor Studio"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${DIRNAME}" "UninstallString" '"$INSTDIR\Ochirish.exe"'
  WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${DIRNAME}" "NoModify" 1
  WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${DIRNAME}" "NoRepair" 1
SectionEnd

Section "Uninstall"
  Delete "$DESKTOP\${APP}.lnk"
  RMDir /r "$SMPROGRAMS\${APP}"
  RMDir /r "$INSTDIR\app"
  RMDir /r "$INSTDIR\runtime"
  Delete "$INSTDIR\${APP}.lnk"
  Delete "$INSTDIR\Ochirish.exe"
  RMDir "$INSTDIR"
  DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${DIRNAME}"
  DeleteRegKey HKCU "Software\${DIRNAME}"
SectionEnd
