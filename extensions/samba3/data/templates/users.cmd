
regedit /s \\%servname%\netlogon\templates\registry\users.reg >nul

rem activate this to mount the writable programs share
rem net use y: \\%servname%\programs_rw /yes >nul

goto %_users_osver%
goto _user_send

:_users_Win95
goto _user_send

:_users_WinNT
goto _user_send

:_users_Win2k
goto _user_send

:_users_WinXP
goto _user_send

:_users_end

