# Academy System — Deployment Notes

## Building the .exe

On this (development) machine:

1. **Install PyInstaller** (once):
   ```
   pip install pyinstaller
   ```

2. **Download `libzbar-64.dll`** and place it at the project root
   (next to `academy_system.spec`).
   - Source: https://github.com/NaturalHistoryMuseum/pyzbar/issues/77
   - The exact filename must be `libzbar-64.dll`.

3. **Run the build:**
   ```
   build.bat
   ```
   or:
   ```
   python -m PyInstaller --clean --noconfirm academy_system.spec
   ```

4. After ~2 minutes you'll have:
   ```
   dist\AcademySystem.exe
   ```
   This single file is the entire app. Roughly 120–180 MB.

## Installing on the target PC

1. Copy `AcademySystem.exe` to the target machine. Anywhere is fine —
   `C:\Users\<user>\Desktop\` or `C:\Program Files\AcademySystem\`.

2. Double-click `AcademySystem.exe`. First launch takes 5–15 seconds
   (Windows unpacks the app to a temp folder).

3. Optional: right-click the .exe → "Pin to Start" or "Create shortcut".

## Where the data lives

**All user data is stored at:**
```
%LOCALAPPDATA%\AcademySystem\
```

That's typically:
```
C:\Users\<username>\AppData\Local\AcademySystem\
```

Contents:
```
AcademySystem\
├── academy.db              ← all players, subscriptions, attendance
└── assets\
    └── qr_codes\           ← QR PNG files, regenerated on demand
        └── player_*.png
```

**This folder is what you back up.** Copy the whole `AcademySystem` folder
to a USB stick, or right-click → "Send to → Compressed folder" for a zip.

## Restoring from a backup

1. Close the app.
2. Replace `%LOCALAPPDATA%\AcademySystem\` with the backed-up copy.
3. Relaunch.

## Resetting the app (wipe all data)

1. Close the app.
2. Delete `%LOCALAPPDATA%\AcademySystem\`.
3. Relaunch — the app creates a fresh, empty database.

## Updating the app to a new version

1. Build a new `AcademySystem.exe` on the dev machine.
2. Replace the old `.exe` on the target PC.
3. **Don't touch `%LOCALAPPDATA%\AcademySystem\`** — the new version reads
   the same database. That's the whole point of keeping data outside the .exe.

## Troubleshooting

### "Windows protected your PC" on first launch
Click "More info" → "Run anyway". This is SmartScreen because the .exe is
not code-signed. One-time prompt per machine.

### Antivirus flags the .exe
PyInstaller-built executables often trigger false positives, especially
with Windows Defender's "unusual file" heuristic. Options:
- Add an exclusion for `AcademySystem.exe`.
- Or submit it to Microsoft's false-positive report:
  https://www.microsoft.com/en-us/wdsi/filesubmission

### First scan doesn't work / crashes
`libzbar-64.dll` wasn't bundled correctly. Verify it was in the project
root when you ran `build.bat`. Check the build output for:
```
WARNING: libzbar-64.dll not found
```
If you see that warning, re-download the DLL and rebuild.

### "Camera unavailable" but webcam works elsewhere
Windows camera privacy settings. Settings → Privacy → Camera → make sure
"Let desktop apps access your camera" is on.