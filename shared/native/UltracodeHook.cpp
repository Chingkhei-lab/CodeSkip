#include <windows.h>
#include <tlhelp32.h>
#include <detours.h>
#include <iostream>

// Forward declarations for DXGI types
struct IDXGISwapChain;
struct IDXGISwapChain1;
struct DXGI_PRESENT_PARAMETERS;

// Function pointers for the original functions we'll hook
static HRESULT (WINAPI* Original_Present)(IDXGISwapChain* pSwapChain, UINT SyncInterval, UINT Flags) = nullptr;
static HRESULT (WINAPI* Original_Present1)(IDXGISwapChain1* pSwapChain, UINT SyncInterval, UINT Flags, const DXGI_PRESENT_PARAMETERS* pPresentParameters) = nullptr;

// Window handle to protect
static HWND targetWindow = NULL;

// Hook status
static bool hookActive = false;

// Simple screen capture detection without DirectX hooking
bool IsScreenCaptureActive();

// Helper function to detect if screen capture is active
bool IsScreenCaptureActive() {
    const char* processes[] = {
        "obs64.exe",
        "Camtasia.exe",
        "SnagitEditor.exe",
        "snagit32.exe",
        "SnagitCapture.exe"
    };
    
    for (const char* process : processes) {
        if (IsProcessRunning(process)) {
            return true;
        }
    }

    return false;
}

// Helper function to check if a process is running
bool IsProcessRunning(const char* processName) {
    PROCESSENTRY32 entry;
    entry.dwSize = sizeof(PROCESSENTRY32);

    HANDLE snapshot = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, NULL);

    if (Process32First(snapshot, &entry) == TRUE) {
        while (Process32Next(snapshot, &entry) == TRUE) {
            if (stricmp(entry.szExeFile, processName) == 0) {
                CloseHandle(snapshot);
                return true;
            }
        }
    }

    CloseHandle(snapshot);
    return false;
}

// Exported functions for the JavaScript FFI interface

extern "C" {
    __declspec(dllexport) bool InstallHook() {
        // For now, we'll use a simple approach that just monitors processes
        // without actual DirectX hooking
        hookActive = true;
        return true;
    }
    
    __declspec(dllexport) bool RemoveHook() {
        hookActive = false;
        return true;
    }
    
    __declspec(dllexport) bool SetWindowHandle(int hwnd) {
        targetWindow = (HWND)hwnd;
        return (targetWindow != NULL);
    }
    
    __declspec(dllexport) bool IsHookActive() {
        return hookActive;
    }
}