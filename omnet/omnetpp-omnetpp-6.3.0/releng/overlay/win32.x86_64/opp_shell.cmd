@echo off
set HOME=
set HOME=%~dp0
cd "%HOME%\tools"

rem msys environment: clang64 or mingw64
set ENVIRONMENT=clang64

IF EXIST "opp-tools-win32-x86_64-clang64-toolchain.7z" (
  cls
  echo.
  echo We need to unpack the MinGW/clang64 toolchain before continuing.
  echo This can take a while, please be patient.
  echo.
  7za x -aos -bb0 -bso0 -bsp1 -y -owin32.x86_64 opp-tools-win32-x86_64-clang64-toolchain.7z && del opp-tools-win32-x86_64-clang64-toolchain.7z
)

cd "%HOME%"
rem Open the MinGW command shell (you may add -full-path to force the MSYS shell to inherit the current system path)
if "%1" == "ide" (
  rem if the first paramter is "ide" we start the IDE instead of the shell. This can be used to start the IDE from a shortcut
  call "%HOME%\tools\win32.x86_64\msys2_shell.cmd" -%ENVIRONMENT% -c "nohup >/dev/null 2>/dev/null $HOME/bin/opp_ide"
) else (
  call "%HOME%\tools\win32.x86_64\msys2_shell.cmd" -%ENVIRONMENT% -defterm %*
)
