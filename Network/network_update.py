import time
from collections import deque

from Network.stats import get_network_io


previous_received = None
previous_sent = None
previous_time = None

download_history = deque(maxlen=5)
upload_history = deque(maxlen=5)
throughput_history = deque(maxlen=60)


def network_update(labels):
    global previous_received, previous_sent, previous_time

    network = get_network_io()
    current_time = time.monotonic()
    current_received = network["bytes_recv"]
    current_sent = network["bytes_sent"]

    if previous_received is None or previous_time is None:
        download_speed = 0.0
        upload_speed = 0.0
    else:
        elapsed = current_time - previous_time
        if elapsed <= 0:
            elapsed = 1.0
        # Interface counters can reset when an adapter reconnects.
        download_speed = max(0, current_received - previous_received) / elapsed
        upload_speed = max(0, current_sent - previous_sent) / elapsed

    download_history.append(download_speed)
    upload_history.append(upload_speed)
    throughput_history.append(
        (
            current_time,
            download_speed * 8 / 1_000_000,
            upload_speed * 8 / 1_000_000,
        )
    )
    average_download = sum(download_history) / len(download_history)
    average_upload = sum(upload_history) / len(upload_history)

    labels["download"].setText(f"{average_download * 8 / 1_000_000:.2f} Mbit/s")
    labels["upload"].setText(f"{average_upload * 8 / 1_000_000:.2f} Mbit/s")
    labels["total_received"].setText(f"{current_received / (1024 ** 3):.2f} GB")
    labels["total_sent"].setText(f"{current_sent / (1024 ** 3):.2f} GB")
    labels["chart"].set_samples(throughput_history)

    previous_received = current_received
    previous_sent = current_sent
    previous_time = current_time
