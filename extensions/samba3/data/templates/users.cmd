
echo "START Users script"

regedit /s \\%servname%\netlogon\templates\registry\users.reg >nul

rem activate this to mount the writable programs share
rem net use Y: \\%servname%\programs_rw /yes >nul

goto %users_osver%
goto users_end

:users_Win95
goto users_end

:users_WinNT
goto users_end

:users_Win2k
goto users_end

:users_WinXP
goto users_end

:users_Vista
goto users_end

:users_end

echo "END Users script"
