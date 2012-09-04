
echo "START Admins script"

echo "RESET REGISTRY."
rem Activate one or another given what you want to allow on the local machine.
rem regedit /s \\%servname%\netlogon\templates\registry\reset-small.reg >nul
regedit /s \\%servname%\netlogon\templates\registry\reset.reg >nul

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
reg add hklm\software\microsoft\windows\currentversion\netcache /v enabled /t reg_dword /d 0 /f
reg add hklm\software\microsoft\windows\currentversion\netcache /v SyncAtLogon /t reg_dword /d 0 /f
reg add hklm\software\microsoft\windows\currentversion\netcache /v SyncAtLogoff /t reg_dword /d 0 /f
reg add hklm\software\microsoft\windows\currentversion\netcache /v NoReminders /t reg_dword /d 0 /f
goto samba_admins_end

:samba_admins_end

echo "END Admins script."
