
echo "START Admins script"

echo "RESET REGISTRY."
rem This currently doesn't work as expected, because the users.cmd script
rem will lock down the computer again. Waiting for #912 to be resolved.
rem regedit /s \\%servname%\netlogon\templates\registry\reset-mini.reg >nul

echo "SET TIME."
net time \\%servname% /set /yes >nul

echo "COPY HOSTS."
copy \\%servname%\netlogon\templates\hosts %windir%\hosts >nul

rem net use P: \\%servname%\programs /yes >nul

echo "ATTACH NETLOGON."
rem net use L: \\%servname%\netlogon /yes >nul


goto %samba_admins_osver%
goto samba_admins_end

:samba_admins_Win95
goto samba_admins_end

:samba_admins_WinNT
goto samba_admins_end

:samba_admins_Win2k
reg add hklm\software\microsoft\windows\currentversion\netcache /v enabled /t reg_dword /d 0 /f
reg add hklm\software\microsoft\windows\currentversion\netcache /v SyncAtLogon /t reg_dword /d 0 /f
reg add hklm\software\microsoft\windows\currentversion\netcache /v SyncAtLogoff /t reg_dword /d 0 /f
reg add hklm\software\microsoft\windows\currentversion\netcache /v NoReminders /t reg_dword /d 0 /f
goto samba_admins_end

:samba_admins_WinXP
reg add hklm\software\microsoft\windows\currentversion\netcache /v enabled /t reg_dword /d 0 /f
reg add hklm\software\microsoft\windows\currentversion\netcache /v SyncAtLogon /t reg_dword /d 0 /f
reg add hklm\software\microsoft\windows\currentversion\netcache /v SyncAtLogoff /t reg_dword /d 0 /f
reg add hklm\software\microsoft\windows\currentversion\netcache /v NoReminders /t reg_dword /d 0 /f
goto samba_admins_end

:samba_admins_Vista
rem Are offline files still enabled by default for roaming profiles on Vista/7 ?
rem reg add hklm\software\microsoft\windows\currentversion\netcache /v enabled /t reg_dword /d 0 /f
rem reg add hklm\software\microsoft\windows\currentversion\netcache /v SyncAtLogon /t reg_dword /d 0 /f
rem reg add hklm\software\microsoft\windows\currentversion\netcache /v SyncAtLogoff /t reg_dword /d 0 /f
rem reg add hklm\software\microsoft\windows\currentversion\netcache /v NoReminders /t reg_dword /d 0 /f
goto samba_admins_end

:samba_admins_end

echo "END Admins script."
