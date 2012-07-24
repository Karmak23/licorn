
rem =========================================================== Common features


net use H: \\%servname%\homes /yes >nul
regedit /s \\%servname%\netlogon\templates\registry\networked_mydocuments.reg >nul

rem Activate the profile mappings if you want them.
rem regedit /s \\%servname%\netlogon\templates\registry\mapping_start_menu.reg >nul
rem regedit /s \\%servname%\netlogon\templates\registry\mapping_programs.reg >nul
rem regedit /s \\%servname%\netlogon\templates\registry\mapping_desktop.reg >nul


rem ====================================================== OS specific features

goto %__header_osver%

rem if %__header_osver% is unknown, we skip right to the end. This avoids messing
rem with a different OS script. All customized scripts should do the same, even
rem if they don't define any OS-specific feature.
goto __header_end


:__header_Win95
regedit /s \\%servname%\netlogon\templates\registry\common-Win95.reg >nul
goto __header_end

:__header_WinNT
goto __header_end

:__header_Win2k
regedit /s \\%servname%\netlogon\templates\registry\nosynchro_offline.reg >nul
goto __header_end

:__header_WinXP
regedit /s \\%servname%\netlogon\templates\registry\nosynchro_offline.reg >nul
goto __header_end

:__header_end

rem use the server proxy.
rem regedit /s \\%servname%\netlogon\templates\registry\autoproxy.reg     >nul


