
echo "START common script"

rem =========================================================== Common features

rem Activate the profile mappings if you want them.
rem regedit /s \\%servname%\netlogon\templates\registry\mapping_start_menu.reg >nul
rem regedit /s \\%servname%\netlogon\templates\registry\mapping_programs.reg >nul
rem regedit /s \\%servname%\netlogon\templates\registry\mapping_desktop.reg >nul

net use H: \\%servname%\homes /yes >nul

rem ====================================================== OS specific features

rem if %__header_osver% is unknown, we skip right to the end. This avoids messing
rem with a different OS script. All customized scripts should do the same, even
rem if they don't define any OS-specific feature.
goto %__header_osver%
goto __header_end


:__header_Win95
regedit /s \\%servname%\netlogon\templates\registry\common-Win95.reg >nul
regedit /s \\%servname%\netlogon\templates\registry\networked_mydocuments.reg >nul
goto __header_end

:__header_WinNT
regedit /s \\%servname%\netlogon\templates\registry\networked_mydocuments.reg >nul
goto __header_end

:__header_Win2k
reg add hkcu\software\microsoft\windows\currentversion\netcache /v enabled /t reg_dword /d 0 /f
reg add hkcu\software\microsoft\windows\currentversion\netcache /v SyncAtLogon /t reg_dword /d 0 /f
reg add hkcu\software\microsoft\windows\currentversion\netcache /v SyncAtLogoff /t reg_dword /d 0 /f
reg add hkcu\software\microsoft\windows\currentversion\netcache /v NoReminders /t reg_dword /d 0 /f

regedit /s \\%servname%\netlogon\templates\registry\networked_mydocuments.reg >nul
goto __header_end

:__header_WinXP
reg add hkcu\software\microsoft\windows\currentversion\netcache /v enabled /t reg_dword /d 0 /f
reg add hkcu\software\microsoft\windows\currentversion\netcache /v SyncAtLogon /t reg_dword /d 0 /f
reg add hkcu\software\microsoft\windows\currentversion\netcache /v SyncAtLogoff /t reg_dword /d 0 /f
reg add hkcu\software\microsoft\windows\currentversion\netcache /v NoReminders /t reg_dword /d 0 /f

regedit /s \\%servname%\netlogon\templates\registry\networked_mydocuments.reg >nul
goto __header_end

:__header_Vista
rd /S /Q "%userprofile%\Documents"
mklink /d "%userprofile%\Documents" \\%servname%\%username%\Documents

rem removing "Pictures" doesn't produce the expected result: Windows
rem re-creates the directory afterwards.
rem rd /S /Q "%userprofile%\Pictures"
rem rd /S /Q "%userprofile%\Mes Images"
rem mklink /d "%userprofile%\Mes Images" \\%servname%\%username%\Images

rem rd /S /Q "%userprofile%\Ma Musique"
rem mklink /d "%userprofile%\Ma Musique" \\%servname%\%username%\Musique

rem rd /S /Q "%userprofile%\Downloads"
rem mklink /d "%userprofile%\Downloads" \\%servname%\%username%\Téléchargements
goto __header_end

:__header_end

rem use the server proxy.
rem regedit /s \\%servname%\netlogon\templates\registry\autoproxy.reg     >nul

echo "END common script"

