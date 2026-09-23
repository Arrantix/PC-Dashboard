import re
import socket
import subprocess

import psutil


def get_network_io():
    net = psutil.net_io_counters()
    return {
        "bytes_sent": net.bytes_sent,
        "bytes_recv": net.bytes_recv,
        "packets_sent": net.packets_sent,
        "packets_recv": net.packets_recv,
    }


def get_local_ip():
    for addresses in psutil.net_if_addrs().values():
        for address in addresses:
            if address.family == socket.AF_INET and not address.address.startswith("127."):
                return address.address
    return None


def get_ping():
    try:
        result = subprocess.run(
            ["ping", "-n", "1", "-w", "1200", "1.1.1.1"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="cp850",
            errors="replace",
            timeout=2,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.TimeoutExpired):
        return None

    match = re.search(r"(?:time|zeit)[=<]\s*(\d+)\s*ms", result.stdout, re.IGNORECASE)
    if match:
        return int(match.group(1))
    return None
