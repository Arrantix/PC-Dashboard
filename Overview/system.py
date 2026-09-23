import csv
import ctypes
import os
import platform
import socket
import subprocess
import time
from pathlib import Path

import psutil


def get_cpu_usage():
    cpu_frequency = psutil.cpu_freq()
    return {
        "cpu_usage": psutil.cpu_percent(percpu=False),
        "cpu_core_usage": psutil.cpu_percent(percpu=True),
        "cpu_physical_cores": psutil.cpu_count(logical=False),
        "cpu_logical_cores": psutil.cpu_count(logical=True),
        "cpu_frequency": cpu_frequency.current if cpu_frequency else None,
    }


def get_ram_usage():
    ram = psutil.virtual_memory()
    return {
        "total": ram.total,
        "used": ram.used,
        "available": ram.available,
        "percent": ram.percent,
    }


def _nvidia_smi_path():
    if os.name != "nt":
        return None

    candidates = [
        Path(r"C:\Program Files\NVIDIA Corporation\NVSMI\nvidia-smi.exe"),
    ]
    system_directory = ctypes.create_unicode_buffer(32768)
    length = ctypes.windll.kernel32.GetSystemDirectoryW(
        system_directory,
        len(system_directory),
    )
    if length and length < len(system_directory):
        candidates.insert(0, Path(system_directory.value) / "nvidia-smi.exe")

    return next((path for path in candidates if path.is_file()), None)


def get_gpu_usage():
    executable = _nvidia_smi_path()
    if executable is None:
        return None

    try:
        result = subprocess.run(
            [
                str(executable),
                "--query-gpu=name,utilization.gpu,memory.used,memory.total",
                "--format=csv,noheader,nounits",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=2,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.TimeoutExpired):
        return None

    if result.returncode != 0:
        return None

    gpus = []
    for row in csv.reader(result.stdout.splitlines(), skipinitialspace=True):
        if len(row) < 4:
            continue
        try:
            utilization = float(row[1].strip())
        except ValueError:
            continue

        def parse_memory(value):
            try:
                return float(value.strip())
            except ValueError:
                return None

        gpus.append({
            "name": row[0].strip(),
            "utilization": utilization,
            "memory_used": parse_memory(row[2]),
            "memory_total": parse_memory(row[3]),
        })
    return gpus or None


def get_disk_usages():
    """Return usage for each distinct mounted partition reported by psutil."""
    partitions = psutil.disk_partitions(all=False)
    usages = []
    seen_mountpoints = set()

    for partition in sorted(
        partitions,
        key=lambda item: (item.mountpoint or "").casefold(),
    ):
        mountpoint = partition.mountpoint
        if not mountpoint:
            continue

        key = os.path.normcase(os.path.normpath(mountpoint))
        if key in seen_mountpoints:
            continue
        seen_mountpoints.add(key)

        drive, tail = os.path.splitdrive(mountpoint)
        name = drive.upper() if drive and not tail.strip("\\/") else mountpoint
        entry = {
            "name": name,
            "mountpoint": mountpoint,
            "device": partition.device,
            "filesystem": partition.fstype,
            "available": False,
            "total": 0,
            "used": 0,
            "free": 0,
            "percent": 0,
        }
        try:
            usage = psutil.disk_usage(mountpoint)
        except (OSError, psutil.Error):
            usages.append(entry)
            continue

        entry.update({
            "available": True,
            "total": usage.total,
            "used": usage.used,
            "free": usage.free,
            "percent": usage.percent,
        })
        usages.append(entry)

    return usages


def get_uptime():
    return time.time() - psutil.boot_time()


def get_system_info():
    return {
        "os": platform.system(),
        "release": platform.release(),
        "version": platform.version(),
        "architecture": platform.machine(),
        "hostname": socket.gethostname(),
    }
