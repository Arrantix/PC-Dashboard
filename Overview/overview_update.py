from Overview.system import (
    get_cpu_usage,
    get_ram_usage,
    get_uptime,
)


def overview_update(labels):
    cpu = get_cpu_usage()
    ram = get_ram_usage()
    uptime = get_uptime()

    days = int(uptime // 86400)
    hours = int((uptime % 86400) // 3600)
    minutes = int((uptime % 3600) // 60)

    labels["cpu_total"].setText(f"{cpu['cpu_usage']:.0f}%")
    for core, usage in zip(labels["cpu_bars"], cpu["cpu_core_usage"]):
        core["bar"].setValue(max(0, min(100, int(usage))))
        core["percent"].setText(f"{usage:.0f}%")

    physical = cpu["cpu_physical_cores"]
    logical = cpu["cpu_logical_cores"]
    frequency = cpu["cpu_frequency"]
    labels["cpu_cores"].setText(
        f"Physical cores  ·  {physical if physical is not None else '—'}"
    )
    labels["cpu_threads"].setText(
        f"Logical threads  ·  {logical if logical is not None else '—'}"
    )
    labels["cpu_frequency"].setText(
        f"Frequency  ·  {frequency / 1000:.2f} GHz"
        if frequency is not None else "Frequency  ·  unavailable"
    )

    labels["ram_usage"].setText(
        f"{ram['used'] / (1024 ** 3):.1f} / {ram['total'] / (1024 ** 3):.1f} GB"
    )
    labels["ram_bar"].setValue(int(ram["percent"]))
    labels["ram_percent"].setText(f"{ram['percent']:.0f}%")
    labels["ram_available"].setText(
        f"Available  ·  {ram['available'] / (1024 ** 3):.1f} GB"
    )

    labels["uptime_time"].setText(
        f"Uptime  ·  {days}d  {hours:02}h  {minutes:02}m"
    )
