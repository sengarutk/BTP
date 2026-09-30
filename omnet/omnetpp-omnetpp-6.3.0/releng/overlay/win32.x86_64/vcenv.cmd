@echo off
rem * If you want to build MS-ABI compatible binaries (not recommended as it is not regularly tested),
rem * uncomment the following line and specify the location of your Visual Studio installation.
rem * You will need the Visual C++ compiler, clang, vcpkg and the Windows SDK installed.

rem set VS_INSTALL_DIR=C:\Program Files\Microsoft Visual Studio\2022\Community

rem * Do not change anything below this line *

rem Visual Studio batch file to set-up a developer console for 64-bit host/target builds.
set VCVARS64=%VS_INSTALL_DIR%\VC\Auxiliary\Build\vcvars64.bat
set VS_INSTALL_DIR=

rem check for existing MS Visual C++ installation
if NOT EXIST "%VCVARS64%" goto SKIP_DEV_CONSOLE_SETUP
call "%VCVARS64%"
set MS_ABI=yes

:SKIP_DEV_CONSOLE_SETUP
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
