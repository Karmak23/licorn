rem
rem Administrators parameters
rem

regedit /s \\%servname%\netlogon\templates\registry\reset-small.reg >nul

net time \\%servname% /set /yes >nul
copy \\%servname%\netlogon\templates\hosts %windir%\hosts >nul

rem net use p: \\%servname%\programs /yes >nul
rem net use n: \\%servname%\netlogon /yes >nul

goto %samba-admins_osver%
goto samba-admins_end

:samba-admins_Win95
goto samba-admins_end

:samba-admins_WinNT
goto samba-admins_end

:samba-admins_Win2k
goto samba-admins_end

:samba-admins_WinXP
goto samba-admins_end

:samba-admins_end

