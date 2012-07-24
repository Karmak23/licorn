
regedit /s \\%servname%\netlogon\templates\registry\users.reg >nul

rem activate this to mount the writable programs share
rem net use y: \\%servname%\programs_rw /yes >nul

goto %users_osver%
goto users_send

:users_Win95
goto users_send

:users_WinNT
goto users_send

:users_Win2k
goto users_send

:users_WinXP
goto users_send

:users_end

