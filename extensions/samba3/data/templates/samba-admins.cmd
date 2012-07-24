rem
rem Administrators parameters
rem

regedit /s \\%servname%\netlogon\templates\registry\reset-small.reg >nul

net time \\%servname% /set /yes >nul
copy \\%servname%\netlogon\templates\hosts %windir%\hosts >nul

rem net use p: \\%servname%\programs /yes >nul
rem net use n: \\%servname%\netlogon /yes >nul

goto %_admins_osver%
goto _admins_end

:_admins_Win95
goto _admins_end

:_admins_WinNT
goto _admins_end

:_admins_Win2k
goto _admins_end

:_admins_WinXP
goto _admins_end

:_admins_end

