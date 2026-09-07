# Build a standalone executable

The scripts bundle Wordflow and its dependencies with PyInstaller. Python and internet access are needed on the build machine. Build on the target operating system; the scripts do not cross-compile.

These are source build instructions, not links to prebuilt releases. Test the resulting executable on the intended system before distributing it.

## Windows

From a repository checkout in PowerShell:

```powershell
.\scripts\build-windows.cmd
.\dist\windows\wordflow.exe
```

The build script creates `.venv-build-win` and writes the executable to `dist/windows/wordflow.exe`. You can copy the executable to a convenient folder and run it from your terminal.

## Linux

From a repository checkout:

```bash
./scripts/build-linux.sh
./dist/linux/wordflow
```

The build script creates `.venv-build-linux` and writes the executable to `dist/linux/wordflow`. To install it for your user:

```bash
mkdir -p ~/.local/bin
cp dist/linux/wordflow ~/.local/bin/wordflow
chmod +x ~/.local/bin/wordflow
```

Ensure `~/.local/bin` is in your shell's `PATH`, then run `wordflow`.

## macOS

Use the Python installation in the [README](../README.md#get-started). This repository does not include a dedicated macOS packaging script.
