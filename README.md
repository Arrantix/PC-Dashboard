# PC Dashboard

A lightweight Windows desktop dashboard for live CPU, memory, storage, and network monitoring.

[Download the latest Windows build](https://github.com/Arrantix/PC-Dashboard/releases/latest) · [View all releases](https://github.com/Arrantix/PC-Dashboard/releases)

## Features

- CPU utilization, per-core activity, core counts, and current frequency
- Memory usage and available memory
- Every mounted disk partition, including used and free space
- Network throughput, session totals, local address, and latency
- NVIDIA GPU utilization and VRAM when the NVIDIA driver provides `nvidia-smi`
- Frameless, resizable dark graphite interface with a teal accent

GPU utilization is currently available through NVIDIA driver telemetry only. AMD and Intel GPU utilization are not reported yet.

## Download and run

1. Open the [latest release](https://github.com/Arrantix/PC-Dashboard/releases/latest).
2. Download `PC-Dashboard.exe` and the matching `.sha256` file.
3. Optionally verify the download in PowerShell:

   ```powershell
   Get-FileHash .\PC-Dashboard.exe -Algorithm SHA256
   Get-Content .\PC-Dashboard.exe.sha256
   ```

4. Run `PC-Dashboard.exe`. The standalone build includes the Python runtime and application dependencies; Python does not need to be installed.

The executable is not code-signed, so Windows may show an unknown-publisher notice. Only download it from this repository's Releases page, and compare its SHA-256 value with the published checksum.

## Run from source

Use 64-bit Python 3.10 or newer on Windows:

```powershell
python -m pip install -r requirements.txt
python main.py
```

## Build the Windows executable

The release build uses Python 3.13 and the pinned dependencies in `requirements-build.txt`:

```powershell
python -m venv .venv-build
.\.venv-build\Scripts\Activate.ps1
python -m pip install -r requirements-build.txt
python -m PyInstaller --clean --noconfirm PC-Dashboard.spec
```

The executable is written to `dist/PC-Dashboard.exe`. Build a release by pushing a version tag in the form `v*` (for example, `v0.1.0`). GitHub Actions builds the Windows executable, creates a SHA-256 checksum, and publishes both on the GitHub Release page. Pull requests and pushes to `main` also run the Windows build workflow.

## Network behavior

The dashboard reads local system metrics and does not upload them. The latency display sends an ICMP echo request to `1.1.1.1` while collecting network information.

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE).
