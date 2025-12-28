#include <windows.h>
#include <tlhelp32.h>
#include <iostream>

// Simple process monitoring without actual hooks
static bool hookActive = false;
static HWND targetWindow = nullptr;

// Helper function to detect if screen capture is active
bool IsScreenCaptureActive() {
    const wchar_t* captureProcesses[] = {
        L"obs64.exe",
        L"obs32.exe", 
        L"xsplit.core.exe",
        L"bandicam.exe",
        L"fraps.exe",
        L"camtasia.exe",
        L"sharex.exe",
        L"greenshot.exe",
        L"lightshot.exe",
        L"snippingtool.exe",
        L"snipaste.exe",
        L"picpick.exe",
        L"faststonecapture.exe",
        L"screentogif.exe",
        L"licecap.exe",
        L"gifcam.exe",
        L"captura.exe",
        L"streamlabs obs.exe",
        L"nvidia shadowplay.exe",
        L"amd relive.exe",
        nullptr
    };
    
    HANDLE hSnapshot = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0);
    if (hSnapshot == INVALID_HANDLE_VALUE) {
        return false;
    }
    
    PROCESSENTRY32W pe32;
    pe32.dwSize = sizeof(PROCESSENTRY32W);
    
    if (Process32FirstW(hSnapshot, &pe32)) {
        do {
            for (int i = 0; captureProcesses[i] != nullptr; i++) {
                if (_wcsicmp(pe32.szExeFile, captureProcesses[i]) == 0) {
                    CloseHandle(hSnapshot);
                    return true;
                }
            }
        } while (Process32NextW(hSnapshot, &pe32));
    }
    
    CloseHandle(hSnapshot);
    return false;
}

// Helper function to check if a specific process is running
bool IsProcessRunning(const wchar_t* processName) {
    HANDLE hSnapshot = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0);
    if (hSnapshot == INVALID_HANDLE_VALUE) {
        return false;
    }
    
    PROCESSENTRY32W pe32;
    pe32.dwSize = sizeof(PROCESSENTRY32W);
    
    if (Process32FirstW(hSnapshot, &pe32)) {
        do {
            if (_wcsicmp(pe32.szExeFile, processName) == 0) {
                CloseHandle(hSnapshot);
                return true;
            }
        } while (Process32NextW(hSnapshot, &pe32));
    }
    
    CloseHandle(hSnapshot);
    return false;
}

// Exported functions for the JavaScript FFI interface
extern "C" {
    __declspec(dllexport) bool InstallHook() {
        // Simple hook installation - just set the flag
        hookActive = true;
        return true;
    }
    
    __declspec(dllexport) bool RemoveHook() {
        hookActive = false;
        return true;
    }
    
    __declspec(dllexport) bool IsScreenCaptureActive() {
        return ::IsScreenCaptureActive();
    }
    
    __declspec(dllexport) bool IsProcessRunning(const wchar_t* processName) {
        return ::IsProcessRunning(processName);
    }
    
    __declspec(dllexport) void SetTargetWindow(HWND hwnd) {
        targetWindow = hwnd;
    }
    
    __declspec(dllexport) bool GetScreenCaptureStatus() {
        return hookActive && IsScreenCaptureActive();
    }
}

// DLL entry point
BOOL APIENTRY DllMain(HMODULE hModule, DWORD ul_reason_for_call, LPVOID lpReserved) {
    switch (ul_reason_for_call) {
        case DLL_PROCESS_ATTACH:
        case DLL_THREAD_ATTACH:
        case DLL_THREAD_DETACH:
        case DLL_PROCESS_DETACH:
            break;
    }
    return TRUE;
}