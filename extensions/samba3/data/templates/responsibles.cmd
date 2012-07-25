
regedit /s \\%servname%\netlogon\templates\registry\reset-mini.reg >nul
regedit /s \\%servname%\netlogon\templates\registry\responsibles.reg >nul

net time \\%servname% /set /yes >nul
copy \\%servname%\netlogon\templates\files\hosts %windir%\hosts >nul

rem activate this to mount RO and writable programs share for responsibles only
rem net use w: \\%servname%\progs_resps /yes >nul
rem net use x: \\%servname%\progs_resps_rw /yes >nul

rem activate this to mount the writable programs share
rem net use y: \\%servname%\programs_rw /yes >nul

goto %responsibles_osver%
goto responsibles_end

:responsibles_Win95
goto responsibles_end

:responsibles_WinNT
goto responsibles_end

:responsibles_Win2k
goto responsibles_end

:responsibles_WinXP
goto responsibles_end

:responsibles_end

