@echo off
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvarsall.bat" x64
cl /LD UltracodeHook.cpp /I. /Ic:\Users\yumkh\Desktop\ultracode-clone\shared\native\Detours\include /link detours.lib user32.lib