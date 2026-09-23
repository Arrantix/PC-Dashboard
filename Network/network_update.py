import time
from collections import deque

from Network.stats import get_network_io


previous_received = None
previous_sent = None
previous_time = None
session_received = 0
session_sent = 0

download_history = deque(maxlen=5)
upload_history = deque(maxlen=5)
throughput_history = deque(maxlen=60)


def _format_transfer_size(byte_count):
    if byte_count >= 1024 ** 3:
        return f"{byte_count / (1024 ** 3):.2f} GB"
    if byte_count >= 1024 ** 2:
        return f"{byte_count / (1024 ** 2):.1f} MB"
    return f"{byte_count / 1024:.0f} KB"


def network_update(labels):
    global previous_received, previous_sent, previous_time, session_received, session_sent

    network = get_network_io()
    current_time = time.monotonic()
    current_received = network["bytes_recv"]
    current_sent = network["bytes_sent"]

    if previous_received is None or previous_time is None:
        received_delta = 0
        sent_delta = 0
        elapsed = 1.0
    else:
        elapsed = current_time - previous_time
        if elapsed <= 0:
            elapsed = 1.0
        # Interface counters can reset when an adapter reconnects.
        received_delta = max(0, current_received - previous_received)
        sent_delta = max(0, current_sent - previous_sent)
    download_speed = received_delta / elapsed
    upload_speed = sent_delta / elapsed
    session_received += received_delta
    session_sent += sent_delta

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

    labels["download"].setText(f"{average_download * 8 / 1_000_000:.2f}")
    labels["upload"].setText(f"{average_upload * 8 / 1_000_000:.2f}")
    labels["total_received"].setText(_format_transfer_size(session_received))
    labels["total_sent"].setText(_format_transfer_size(session_sent))
    labels["chart"].set_samples(throughput_history)

    previous_received = current_received
    previous_sent = current_sent
    previous_time = current_time
