@echo off
REM Try to find cl.exe in common locations
set CL_PATH=

REM Check for Visual Studio 2022
if exist "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Tools\MSVC\14.30.30705\bin\Hostx64\x64\cl.exe" (
    set CL_PATH="C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Tools\MSVC\14.30.30705\bin\Hostx64\x64\cl.exe"
    goto :found
)

REM Check for Visual Studio 2019
if exist "C:\Program Files (x86)\Microsoft Visual Studio\2019\Community\VC\Tools\MSVC\14.29.30133\bin\Hostx64\x64\cl.exe" (
    set CL_PATH="C:\Program Files (x86)\Microsoft Visual Studio\2019\Community\VC\Tools\MSVC\14.29.30133\bin\Hostx64\x64\cl.exe"
    goto :found
)

REM Check for Windows SDK
if exist "C:\Program Files (x86)\Windows Kits\10\bin\10.0.19041.0\x64\cl.exe" (
    set CL_PATH="C:\Program Files (x86)\Windows Kits\10\bin\10.0.19041.0\x64\cl.exe"
    goto :found
)

echo Could not find cl.exe
exit /b 1

:found
echo Found cl.exe at %CL_PATH%
%CL_PATH% /LD UltracodeHook.cpp /I. /Ic:\Users\yumkh\Desktop\ultracode-clone\shared\native\Detours\include /link detours.lib user32.lib