
echo "START common script"

rem =========================================================== Common features

rem Unlock the computer from previous lockdown. This is done in the common
rem features until #912 is resolved properly.
regedit /s \\%servname%\netlogon\templates\registry\reset-mini.reg >nul


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
mkdir %appdata%\microsoft\windows\libraries
xcopy \\%servname%\netlogon\local\libraries\*.* %appdata%\microsoft\windows\libraries /I /Y

rem "Domain Users" need the createlink permission for this to work.

rem rd /S /Q "%userprofile%\Documents"
rem mklink /d "%userprofile%\Documents" H:\Documents
rem mklink /d "%userprofile%\Documents" \\%servname%\%username%\Documents

rem removing "Pictures" doesn't produce the expected result: Windows
rem re-creates the directory afterwards.
rem rd /S /Q "%userprofile%\Mes Images"
rem rd /S /Q "%userprofile%\Pictures"
rem mklink /d "%userprofile%\Pictures" H:\Images
rem mklink /d "%userprofile%\Pictures" \\%servname%\%username%\Images

rem rd /S /Q "%userprofile%\Music"
rem mklink /d "%userprofile%\Music" H:\Musique
rem mklink /d "%userprofile%\Music" \\%servname%\%username%\Musique

rem rd /S /Q "%userprofile%\Downloads"
rem mklink /d "%userprofile%\Downloads" H:\Téléchargements
rem mklink /d "%userprofile%\Downloads" \\%servname%\%username%\Téléchargements
goto __header_end

:__header_end

rem use the server proxy.
rem regedit /s \\%servname%\netlogon\templates\registry\autoproxy.reg     >nul

echo "END common script"

