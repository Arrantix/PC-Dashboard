import sys
from datetime import datetime
from math import floor, log10

import psutil
from PySide6.QtCore import QEvent, QObject, QRunnable, QThreadPool, QTimer, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QScrollArea,
    QSizeGrip,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from Network.network_update import network_update
from Network.stats import get_local_ip, get_ping
from Overview.overview_update import overview_update
from Overview.system import get_disk_usages, get_gpu_usage, get_system_info


STYLESHEET = """
QWidget {
    color: #edf4f4;
    font-family: "Segoe UI";
    font-size: 10pt;
}
QWidget#dashboard {
    background: #20282c;
    border: none;
}
QLabel {
    background: transparent;
    border: none;
}
QToolButton#windowButton, QToolButton#closeButton {
    background: transparent;
    border: none;
    border-radius: 2px;
    color: #c7d6d5;
    font-size: 11pt;
}
QToolButton#windowButton:hover {
    background: #243136;
}
QToolButton#windowButton:focus {
    border: 1px solid #49e2c1;
}
QToolButton#closeButton:hover {
    background: #963b45;
    color: white;
}
QFrame#header {
    background: transparent;
    border: none;
}
QFrame#brandMark {
    background: #49e2c1;
    border: none;
    border-radius: 7px;
}
QLabel#brandLetters {
    color: #0e1316;
    font-size: 11pt;
    font-weight: 800;
}
QLabel#appTitle {
    font-size: 18pt;
    font-weight: 700;
    letter-spacing: 0.4px;
}
QLabel#appSubtitle, QLabel#muted, QLabel#detail {
    color: #9aabad;
}
QLabel#appSubtitle {
    font-size: 9pt;
    letter-spacing: 1.2px;
}
QLabel#liveBadge {
    background: #142923;
    color: #67e7c8;
    border: 1px solid #28584b;
    border-radius: 10px;
    padding: 5px 11px;
    font-size: 8pt;
    font-weight: 700;
    letter-spacing: 0.8px;
}
QTabWidget {
    background: transparent;
}
QTabBar {
    background: transparent;
}
QTabWidget::pane {
    background: #20282c;
    border: none;
    top: -1px;
}
QTabBar::tab {
    background: transparent;
    color: #9aabad;
    padding: 11px 18px;
    margin-right: 8px;
    border-bottom: 2px solid transparent;
    font-weight: 600;
}
QTabBar::tab:selected {
    color: #edf4f4;
    border-bottom: 2px solid #49e2c1;
}
QTabBar::tab:hover:!selected {
    color: #c7d6d5;
}
QTabBar::tab:focus {
    outline: 1px solid #49e2c1;
}
QFrame#panel {
    background: transparent;
    border: none;
    border-radius: 0;
}
QLabel#panelTitle {
    color: #8fa6a5;
    font-size: 9pt;
    font-weight: 700;
    letter-spacing: 1px;
    border-bottom: 1px solid #354247;
    padding-bottom: 7px;
}
QLabel#metricLarge {
    color: #f2f8f7;
    font-size: 27pt;
    font-weight: 700;
}
QLabel#metric {
    color: #edf4f4;
    font-size: 17pt;
    font-weight: 650;
}
QLabel#metricAccent {
    color: #64e4c5;
    font-size: 17pt;
    font-weight: 700;
}
QLabel#value {
    color: #dfe9e8;
    font-size: 10pt;
    font-weight: 600;
}
QLabel#coreName {
    color: #9aabad;
    font-size: 8pt;
}
QLabel#networkDownload {
    color: #49e2c1;
    font-size: 9pt;
    font-weight: 700;
    letter-spacing: 0.8px;
}
QLabel#networkUpload {
    color: #86b8c0;
    font-size: 9pt;
    font-weight: 700;
    letter-spacing: 0.8px;
}
QProgressBar {
    background: transparent;
    border: none;
}
QScrollArea {
    background: transparent;
    border: none;
}
QScrollArea > QWidget > QWidget {
    background: transparent;
}
"""


class ProbeSignals(QObject):
    finished = Signal(object, object, object)


class MeterBar(QProgressBar):
    """Flat instrument-style utilization bar with subtle scale marks."""

    def __init__(self, height=6, parent=None):
        super().__init__(parent)
        self._track_height = height
        self.setRange(0, 100)
        self.setTextVisible(False)
        self.setFixedHeight(height + 4)

    def paintEvent(self, event):
        painter = QPainter(self)
        track_y = (self.height() - self._track_height) // 2
        track_width = max(0, self.width())
        painter.fillRect(0, track_y, track_width, self._track_height, QColor("#303b40"))
        span = max(1, self.maximum() - self.minimum())
        ratio = (self.value() - self.minimum()) / float(span)
        filled_width = int(track_width * max(0.0, min(1.0, ratio)))
        if filled_width:
            painter.fillRect(0, track_y, filled_width, self._track_height, QColor("#49e2c1"))
        for tick in (0.25, 0.5, 0.75):
            x = int(track_width * tick)
            tick_color = "#17433b" if x < filled_width else "#526164"
            painter.fillRect(x, track_y, 1, self._track_height, QColor(tick_color))
        painter.end()


class WindowButton(QToolButton):
    """Compact window control with consistently sized vector symbols."""

    def __init__(self, symbol, parent=None):
        super().__init__(parent)
        self._symbol = symbol
        self.setFocusPolicy(Qt.TabFocus)
        self.setFixedSize(27, 23)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect()
        if self.underMouse():
            color = QColor("#963b45") if self.objectName() == "closeButton" else QColor("#243136")
            painter.setPen(Qt.NoPen)
            painter.setBrush(color)
            painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), 2, 2)
        if self.hasFocus():
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(QColor("#49e2c1"), 1))
            painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), 2, 2)

        painter.setPen(QPen(QColor("#c7d6d5"), 1))
        cx = rect.center().x()
        cy = rect.center().y()
        if self._symbol == "minimize":
            painter.drawLine(cx - 4, cy + 3, cx + 4, cy + 3)
        elif self._symbol == "maximize":
            painter.drawRect(cx - 3, cy - 3, 7, 7)
        else:
            painter.drawLine(cx - 3, cy - 3, cx + 3, cy + 3)
            painter.drawLine(cx + 3, cy - 3, cx - 3, cy + 3)
        painter.end()


class NetworkChart(QWidget):
    """Lightweight 60-second throughput plot."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.samples = []
        self.setMinimumHeight(112)
        self.setAccessibleName("Network throughput over the last 60 seconds")
        self.setAccessibleDescription(
            "Download is a solid teal line; upload is a dashed blue-green line."
        )

    def set_samples(self, samples):
        self.samples = list(samples)
        self.update()

    @staticmethod
    def _nice_scale(maximum):
        target = max(maximum * 1.1, 1.0)
        magnitude = 10 ** floor(log10(target))
        normalized = target / magnitude
        for step in (1, 2, 5, 10):
            if normalized <= step:
                return step * magnitude
        return 10 * magnitude

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        plot = self.rect().adjusted(0, 10, -92, -20)
        if plot.width() <= 0 or plot.height() <= 0:
            painter.end()
            return

        values = [sample[1] for sample in self.samples]
        values.extend(sample[2] for sample in self.samples)
        scale = self._nice_scale(max(values) if values else 0.0)

        painter.setPen(QPen(QColor("#354247"), 1))
        for tick in (0.25, 0.5, 0.75):
            y = int(plot.bottom() - plot.height() * tick)
            painter.drawLine(plot.left(), y, plot.right(), y)
        painter.setPen(QPen(QColor("#65767b"), 1))
        painter.drawLine(plot.left(), plot.bottom(), plot.right(), plot.bottom())

        painter.setFont(QFont("Segoe UI", 8))
        painter.setPen(QColor("#9aabad"))
        painter.drawText(
            self.rect().adjusted(self.width() - 88, 0, -2, 0),
            Qt.AlignRight | Qt.AlignTop,
            f"{scale:g} Mbit/s",
        )
        labels_y = plot.bottom() + 4
        painter.drawText(plot.left(), labels_y, 28, 16, Qt.AlignLeft, "60s")
        painter.drawText(
            plot.center().x() - 20, labels_y, 40, 16, Qt.AlignHCenter, "30s"
        )
        painter.drawText(
            plot.right() - 30, labels_y, 30, 16, Qt.AlignRight, "NOW"
        )

        if not self.samples:
            painter.end()
            return

        last_time = self.samples[-1][0]
        window_start = last_time - 60.0
        for value_index, color, style in (
            (1, QColor("#49e2c1"), Qt.SolidLine),
            (2, QColor("#86b8c0"), Qt.DashLine),
        ):
            path = QPainterPath()
            first = True
            for sample in self.samples:
                x_ratio = max(0.0, min(1.0, (sample[0] - window_start) / 60.0))
                y_ratio = max(0.0, min(1.0, sample[value_index] / scale))
                point_x = plot.left() + x_ratio * plot.width()
                point_y = plot.bottom() - y_ratio * plot.height()
                if first:
                    path.moveTo(point_x, point_y)
                    first = False
                else:
                    path.lineTo(point_x, point_y)
            painter.setPen(QPen(color, 1.8, style, Qt.RoundCap, Qt.RoundJoin))
            painter.drawPath(path)
            if len(self.samples) == 1:
                sample = self.samples[0]
                x = plot.left() + max(0.0, min(1.0, (sample[0] - window_start) / 60.0)) * plot.width()
                y = plot.bottom() - max(0.0, min(1.0, sample[value_index] / scale)) * plot.height()
                painter.setBrush(color)
                painter.drawEllipse(int(x - 2), int(y - 2), 4, 4)
        painter.end()


class WindowDragFilter(QObject):
    def __init__(self, window):
        super().__init__(window)
        self.window = window

    def eventFilter(self, watched, event):
        if event.type() == QEvent.MouseButtonDblClick:
            if event.button() == Qt.LeftButton:
                self.window._toggle_maximized()
                return True
        elif event.type() == QEvent.MouseButtonPress:
            if event.button() == Qt.LeftButton:
                handle = self.window.windowHandle()
                if handle is not None and handle.startSystemMove():
                    return True
        return False


class NetworkProbe(QRunnable):
    """Runs the local-address lookup and bounded ping outside the UI thread."""

    def __init__(self):
        super().__init__()
        self.signals = ProbeSignals()

    def run(self):
        try:
            local_ip = get_local_ip()
        except (OSError, psutil.Error):
            local_ip = None
        try:
            ping = get_ping()
        except (OSError, psutil.Error):
            ping = None
        try:
            gpu = get_gpu_usage()
        except (OSError, psutil.Error):
            gpu = None
        self.signals.finished.emit(local_ip, ping, gpu)


class DiskProbeSignals(QObject):
    finished = Signal(object, str)


class DiskProbe(QRunnable):
    """Enumerates mounted volumes without blocking the dashboard UI."""

    def __init__(self):
        super().__init__()
        self.signals = DiskProbeSignals()

    def run(self):
        try:
            volumes = get_disk_usages()
        except (OSError, psutil.Error):
            self.signals.finished.emit(None, "Storage information unavailable")
            return
        self.signals.finished.emit(volumes, "")

class Dashboard(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PC Dashboard")
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
        self.setMinimumSize(880, 700)
        self.resize(1080, 900)
        self.setObjectName("dashboard")
        self.setStyleSheet(STYLESHEET)
        self.setFont(QFont("Segoe UI", 10))

        self._probe_pending = False
        self._probe_worker = None
        self._last_ip = None
        self._last_ping = None
        self._disk_probe_pending = False
        self._disk_probe_worker = None
        self._disk_signature = None
        self.disk_rows = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(14)
        self.header = self._make_header()
        root.addWidget(self.header)
        self._drag_filter = WindowDragFilter(self)
        header_widgets = [self.header] + self.header.findChildren(QWidget)
        for widget in header_widgets:
            if not isinstance(widget, QToolButton):
                widget.installEventFilter(self._drag_filter)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.addTab(self._make_overview_tab(), "Overview")
        self.tabs.addTab(self._make_network_tab(), "Network")
        root.addWidget(self.tabs, 1)
        self.tabs.setFocus(Qt.OtherFocusReason)
        self.size_grip = QSizeGrip(self)
        self.size_grip.setAccessibleName("Resize window")
        grip_row = QHBoxLayout()
        grip_row.addStretch()
        grip_row.addWidget(self.size_grip)
        root.addLayout(grip_row)

        self.overview_timer = QTimer(self)
        self.overview_timer.timeout.connect(self._refresh_overview)
        self.overview_timer.start(1000)

        self.network_timer = QTimer(self)
        self.network_timer.timeout.connect(self._refresh_network)
        self.network_timer.start(1000)

        self.disk_timer = QTimer(self)
        self.disk_timer.timeout.connect(self._start_disk_probe)
        self.disk_timer.start(10000)

        self.probe_timer = QTimer(self)
        self.probe_timer.timeout.connect(self._start_network_probe)
        self.probe_timer.start(5000)

        self._refresh_overview()
        self._refresh_network()
        self._start_disk_probe()
        self._start_network_probe()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setPen(QPen(QColor("#718084"), 1))
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(self.rect().adjusted(0, 0, -1, -1))
        painter.end()

    @staticmethod
    def _label(text="", object_name=None):
        label = QLabel(text)
        if object_name:
            label.setObjectName(object_name)
        return label

    @staticmethod
    def _panel(title):
        panel = QFrame()
        panel.setObjectName("panel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(4, 3, 4, 3)
        layout.setSpacing(10)
        heading = QLabel(title.upper())
        heading.setObjectName("panelTitle")
        layout.addWidget(heading)
        return panel, layout

    def _make_header(self):
        header = QFrame()
        header.setObjectName("header")
        layout = QHBoxLayout(header)
        layout.setContentsMargins(0, 0, 0, 2)
        layout.setSpacing(13)

        mark = QFrame()
        mark.setObjectName("brandMark")
        mark.setFixedSize(38, 38)
        mark_layout = QVBoxLayout(mark)
        mark_layout.setContentsMargins(0, 0, 0, 0)
        mark_letters = QLabel("PC")
        mark_letters.setObjectName("brandLetters")
        mark_letters.setAlignment(Qt.AlignCenter)
        mark_layout.addWidget(mark_letters)

        title_stack = QVBoxLayout()
        title_stack.setSpacing(0)
        title = QLabel("PC DASHBOARD")
        title.setObjectName("appTitle")
        subtitle = QLabel("REAL-TIME SYSTEM MONITOR")
        subtitle.setObjectName("appSubtitle")
        title_stack.addWidget(title)
        title_stack.addWidget(subtitle)

        layout.addWidget(mark)
        layout.addLayout(title_stack)
        layout.addStretch()
        live = QLabel("LIVE  ·  LOCAL")
        live.setObjectName("liveBadge")
        layout.addWidget(live, 0, Qt.AlignVCenter)

        self.min_button = self._make_window_button("minimize", "Minimize")
        self.max_button = self._make_window_button("maximize", "Maximize")
        self.close_button = self._make_window_button("close", "Close", close=True)
        self.min_button.clicked.connect(self.showMinimized)
        self.max_button.clicked.connect(self._toggle_maximized)
        self.close_button.clicked.connect(self.close)
        layout.addWidget(self.min_button)
        layout.addWidget(self.max_button)
        layout.addWidget(self.close_button)
        return header

    @staticmethod
    def _make_window_button(symbol, name, close=False):
        button = WindowButton(symbol)
        button.setObjectName("closeButton" if close else "windowButton")
        button.setToolTip(name)
        button.setAccessibleName(name)
        return button

    def _toggle_maximized(self):
        if self.isMaximized():
            self.showNormal()
            self.max_button.setToolTip("Maximize")
            self.max_button.setAccessibleName("Maximize")
        else:
            self.showMaximized()
            self.max_button.setToolTip("Restore")
            self.max_button.setAccessibleName("Restore")

    def _make_overview_tab(self):
        page, grid = self._make_scroll_grid()
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)

        cpu_panel, cpu_layout = self._panel("Processor")
        cpu_head = QHBoxLayout()
        self.cpu_total = self._label("—", "metricLarge")
        self.cpu_total.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        cpu_head.addWidget(self._label("Overall utilization", "muted"))
        cpu_head.addStretch()
        cpu_head.addWidget(self.cpu_total)
        cpu_layout.addLayout(cpu_head)

        cpu_details = QHBoxLayout()
        self.cpu_cores_label = self._label("Physical cores  ·  —", "detail")
        self.cpu_threads_label = self._label("Logical threads  ·  —", "detail")
        self.cpu_frequency_label = self._label("Frequency  ·  —", "detail")
        cpu_details.addWidget(self.cpu_cores_label)
        cpu_details.addWidget(self.cpu_threads_label)
        cpu_details.addWidget(self.cpu_frequency_label)
        cpu_layout.addLayout(cpu_details)

        self.cpu_bars = []
        self.cpu_cores = psutil.cpu_count(logical=True) or 1
        core_grid = QGridLayout()
        core_grid.setHorizontalSpacing(22)
        core_grid.setVerticalSpacing(12)
        for index in range(self.cpu_cores):
            row, column = divmod(index, 4)
            item = QHBoxLayout()
            name = QLabel(f"CORE {index + 1:02}")
            name.setObjectName("coreName")
            name.setFixedWidth(46)
            bar = MeterBar(height=4)
            bar.setObjectName("coreBar")
            bar.setRange(0, 100)
            bar.setTextVisible(False)
            bar.setAccessibleName(f"Core {index + 1} utilization")
            percent = QLabel("—")
            percent.setObjectName("coreName")
            percent.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            percent.setFixedWidth(30)
            item.addWidget(name)
            item.addWidget(bar, 1)
            item.addWidget(percent)
            core_grid.addLayout(item, row, column)
            self.cpu_bars.append({"bar": bar, "percent": percent})
        cpu_layout.addLayout(core_grid)
        cpu_layout.addWidget(self._label("Per-core activity", "muted"))
        grid.addWidget(cpu_panel, 0, 0, 1, 2)

        ram_panel, ram_layout = self._panel("Memory")
        self.ram_percent = self._label("—", "metricAccent")
        self.ram_percent.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        ram_head = QHBoxLayout()
        ram_head.addWidget(self._label("In use", "muted"))
        ram_head.addStretch()
        ram_head.addWidget(self.ram_percent)
        ram_layout.addLayout(ram_head)
        self.ram_bar = MeterBar(height=7)
        self.ram_bar.setRange(0, 100)
        self.ram_bar.setTextVisible(False)
        self.ram_usage = self._label("Sampling…", "value")
        self.ram_available = self._label("", "detail")
        ram_layout.addWidget(self.ram_bar)
        ram_layout.addWidget(self.ram_usage)
        ram_layout.addWidget(self.ram_available)
        grid.addWidget(ram_panel, 1, 0)

        storage_panel, storage_layout = self._panel("Storage")
        self.disk_heading = storage_panel.findChild(QLabel, "panelTitle")
        self.disk_rows_layout = QVBoxLayout()
        self.disk_rows_layout.setContentsMargins(0, 0, 0, 0)
        self.disk_rows_layout.setSpacing(9)
        self.disk_status = self._label("Detecting partitions…", "detail")
        self.disk_status.setWordWrap(True)
        self.disk_rows_layout.addWidget(self.disk_status)
        storage_layout.addLayout(self.disk_rows_layout)
        grid.addWidget(storage_panel, 1, 1)

        system_panel, system_layout = self._panel("This device")
        self.system_os = self._label("—", "value")
        self.system_arch = self._label("", "detail")
        self.system_hostname = self._label("", "detail")
        self.system_uptime = self._label("Uptime  ·  —", "value")
        self.system_boot = self._label("", "detail")
        system_layout.addWidget(self.system_os)
        system_layout.addWidget(self.system_arch)
        system_layout.addWidget(self.system_hostname)
        system_layout.addSpacing(4)
        system_layout.addWidget(self.system_uptime)
        system_layout.addWidget(self.system_boot)
        grid.addWidget(system_panel, 2, 0)

        gpu_panel, gpu_layout = self._panel("Graphics")
        self.gpu_name = self._label("Checking NVIDIA telemetry…", "value")
        self.gpu_util = self._label("—", "metricAccent")
        self.gpu_util.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        gpu_head = QHBoxLayout()
        gpu_head.addWidget(self._label("GPU utilization", "muted"))
        gpu_head.addStretch()
        gpu_head.addWidget(self.gpu_util)
        gpu_layout.addWidget(self.gpu_name)
        gpu_layout.addLayout(gpu_head)
        self.gpu_bar = MeterBar(height=7)
        self.gpu_bar.setRange(0, 100)
        self.gpu_bar.setTextVisible(False)
        self.gpu_bar.setEnabled(False)
        self.gpu_memory = self._label("VRAM  ·  —", "detail")
        self.gpu_note = self._label(
            "NVIDIA driver telemetry. AMD/Intel utilization is not available.",
            "detail",
        )
        self.gpu_note.setWordWrap(True)
        gpu_layout.addWidget(self.gpu_bar)
        gpu_layout.addWidget(self.gpu_memory)
        gpu_layout.addWidget(self.gpu_note)
        grid.addWidget(gpu_panel, 2, 1)

        return page

    def _make_network_tab(self):
        page, grid = self._make_scroll_grid()
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(2, 1)

        speed_panel, speed_layout = self._panel("Live throughput")
        rate_row = QHBoxLayout()
        rate_row.setSpacing(34)
        self.download_value = self._label("Sampling…", "metricLarge")
        self.upload_value = self._label("Sampling…", "metricLarge")
        download_column = QVBoxLayout()
        download_column.setSpacing(2)
        download_column.addWidget(self._label("DOWNLOAD", "networkDownload"))
        download_column.addWidget(self.download_value)
        upload_column = QVBoxLayout()
        upload_column.setSpacing(2)
        upload_column.addWidget(self._label("UPLOAD", "networkUpload"))
        upload_column.addWidget(self.upload_value)
        rate_row.addLayout(download_column, 1)
        rate_row.addLayout(upload_column, 1)
        speed_layout.addLayout(rate_row)

        self.network_chart = NetworkChart()
        speed_layout.addWidget(self.network_chart)
        grid.addWidget(speed_panel, 0, 0, 1, 3)

        traffic_panel, traffic_layout = self._panel("Session totals")
        self.received_value = self._label("Sampling…", "metric")
        self.sent_value = self._label("Sampling…", "metric")
        self._add_network_row(traffic_layout, "Received", self.received_value)
        self._add_network_row(traffic_layout, "Sent", self.sent_value)
        traffic_hint = self._label("Since this session started", "detail")
        traffic_layout.addSpacing(5)
        traffic_layout.addWidget(traffic_hint)
        grid.addWidget(traffic_panel, 1, 0)

        connection_panel, connection_layout = self._panel("Connection")
        self.ip_value = self._label("Looking up…", "value")
        self.ping_value = self._label("Checking…", "value")
        self.ip_value.setMinimumWidth(105)
        self.ping_value.setMinimumWidth(95)
        self.ip_value.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._add_network_row(connection_layout, "Local IPv4", self.ip_value)
        self._add_network_row(connection_layout, "Ping to 1.1.1.1", self.ping_value)
        connection_hint = self._label("Ping updates every 5 seconds", "detail")
        connection_layout.addSpacing(5)
        connection_layout.addWidget(connection_hint)
        grid.addWidget(connection_panel, 1, 1, 1, 2)

        grid.setRowStretch(2, 1)
        return page

    @staticmethod
    def _add_network_row(layout, title, value):
        row = QHBoxLayout()
        name = QLabel(title)
        name.setObjectName("muted")
        row.addWidget(name)
        row.addStretch()
        row.addWidget(value)
        layout.addLayout(row)

    @staticmethod
    def _make_scroll_grid():
        content = QWidget()
        grid = QGridLayout(content)
        grid.setContentsMargins(10, 18, 10, 18)
        grid.setHorizontalSpacing(28)
        grid.setVerticalSpacing(24)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidget(content)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        return scroll, grid

    def _refresh_overview(self):
        labels = {
            "cpu_total": self.cpu_total,
            "cpu_bars": self.cpu_bars,
            "cpu_cores": self.cpu_cores_label,
            "cpu_threads": self.cpu_threads_label,
            "cpu_frequency": self.cpu_frequency_label,
            "ram_usage": self.ram_usage,
            "ram_bar": self.ram_bar,
            "ram_available": self.ram_available,
            "ram_percent": self.ram_percent,
            "uptime_time": self.system_uptime,
        }
        overview_update(labels)

        info = get_system_info()
        self.system_os.setText(f"{info['os']}  {info['release']}")
        self.system_arch.setText(f"Architecture  ·  {info['architecture']}")
        self.system_hostname.setText(f"Hostname  ·  {info['hostname']}")
        self.system_boot.setText(
            "Booted  ·  "
            + datetime.fromtimestamp(psutil.boot_time()).strftime("%d.%m.%Y  %H:%M")
        )

    @staticmethod
    def _format_storage_size(byte_count):
        gib = byte_count / float(1024 ** 3)
        if gib >= 1024:
            return f"{gib / 1024:.1f} TB"
        return f"{gib:.1f} GB"

    def _make_disk_row(self, volume):
        row = QWidget()
        row_layout = QVBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(3)

        heading = QHBoxLayout()
        heading.setSpacing(7)
        name = self._label(volume["name"], "value")
        name.setTextFormat(Qt.PlainText)
        name.setMinimumWidth(42)
        name.setMaximumWidth(130)
        filesystem = self._label(volume["filesystem"] or "—", "detail")
        filesystem.setTextFormat(Qt.PlainText)
        usage = self._label("—", "detail")
        usage.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        percent = self._label("—", "value")
        percent.setMinimumWidth(34)
        percent.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        heading.addWidget(name)
        heading.addWidget(filesystem)
        heading.addStretch()
        heading.addWidget(usage)
        heading.addWidget(percent)

        meter_row = QHBoxLayout()
        meter_row.setSpacing(8)
        bar = MeterBar(height=5)
        bar.setAccessibleName("Disk space used on " + volume["name"])
        free = self._label("", "detail")
        free.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        meter_row.addWidget(bar, 1)
        meter_row.addWidget(free)

        row_layout.addLayout(heading)
        row_layout.addLayout(meter_row)
        return {
            "widget": row,
            "name": name,
            "filesystem": filesystem,
            "usage": usage,
            "percent": percent,
            "bar": bar,
            "free": free,
        }

    def _update_disk_rows(self, volumes):
        count = len(volumes)
        if count:
            suffix = "PARTITION" if count == 1 else "PARTITIONS"
            self.disk_heading.setText(f"STORAGE  ·  {count} {suffix}")
        else:
            self.disk_heading.setText("STORAGE")

        signature = tuple(volume["mountpoint"] for volume in volumes)
        if signature != self._disk_signature:
            for row in self.disk_rows.values():
                self.disk_rows_layout.removeWidget(row["widget"])
                row["widget"].deleteLater()
            self.disk_rows = {}
            self._disk_signature = signature
            for volume in volumes:
                row = self._make_disk_row(volume)
                self.disk_rows[volume["mountpoint"]] = row
                self.disk_rows_layout.addWidget(row["widget"])

        self.disk_status.setVisible(not volumes)
        if not volumes:
            self.disk_status.setText("No mounted partitions found.")
            return

        for volume in volumes:
            row = self.disk_rows[volume["mountpoint"]]
            details = (
                f"Mount point: {volume['mountpoint']}\n"
                f"Device: {volume['device'] or '—'}\n"
                f"File system: {volume['filesystem'] or '—'}"
            )
            for widget in row.values():
                if isinstance(widget, QWidget):
                    widget.setToolTip(details)
            row["name"].setText(volume["name"])
            row["filesystem"].setText(volume["filesystem"] or "—")

            if not volume["available"]:
                row["usage"].setText("Unavailable")
                row["percent"].setText("—")
                row["bar"].setValue(0)
                row["bar"].setEnabled(False)
                row["free"].setText("Access unavailable")
                continue

            row["bar"].setEnabled(True)
            row["bar"].setValue(max(0, min(100, int(volume["percent"]))))
            row["usage"].setText(
                f"{self._format_storage_size(volume['used'])} / "
                f"{self._format_storage_size(volume['total'])}"
            )
            row["percent"].setText(f"{volume['percent']:.0f}%")
            row["free"].setText(self._format_storage_size(volume["free"]) + " free")

    def _start_disk_probe(self):
        if self._disk_probe_pending:
            return
        self._disk_probe_pending = True
        worker = DiskProbe()
        worker.signals.finished.connect(self._disk_probe_finished)
        self._disk_probe_worker = worker
        QThreadPool.globalInstance().start(worker)

    def _disk_probe_finished(self, volumes, error):
        self._disk_probe_pending = False
        self._disk_probe_worker = None
        if error:
            self.disk_status.setText(
                "Storage refresh failed; showing the last available readings."
                if self.disk_rows else error
            )
            self.disk_status.show()
            return
        self._update_disk_rows(volumes)

    def _refresh_network(self):
        labels = {
            "download": self.download_value,
            "upload": self.upload_value,
            "total_received": self.received_value,
            "total_sent": self.sent_value,
            "chart": self.network_chart,
        }
        network_update(labels)

    def _start_network_probe(self):
        if self._probe_pending:
            return
        self._probe_pending = True
        worker = NetworkProbe()
        worker.signals.finished.connect(self._network_probe_finished)
        self._probe_worker = worker
        QThreadPool.globalInstance().start(worker)

    def _network_probe_finished(self, local_ip, ping, gpu):
        self._probe_pending = False
        self._probe_worker = None
        self._last_ip = local_ip
        self._last_ping = ping
        self.ip_value.setText(local_ip or "Unavailable")
        self.ping_value.setText(
            f"{ping} ms" if ping is not None else "Unavailable"
        )

        if not gpu:
            self.gpu_name.setText("NVIDIA telemetry unavailable")
            self.gpu_util.setText("—")
            self.gpu_bar.setValue(0)
            self.gpu_bar.setEnabled(False)
            self.gpu_memory.setText("VRAM  ·  unavailable")
            return

        primary = gpu[0]
        self.gpu_name.setText(
            f"NVIDIA GPU 1 / {len(gpu)}  ·  {primary['name']}"
        )
        utilization = max(0, min(100, round(primary["utilization"])))
        self.gpu_util.setText(f"{utilization}%")
        self.gpu_bar.setValue(utilization)
        self.gpu_bar.setEnabled(True)
        used = primary["memory_used"]
        total = primary["memory_total"]
        if used is None or total is None:
            self.gpu_memory.setText("VRAM  ·  unavailable")
        else:
            self.gpu_memory.setText(
                f"VRAM  ·  {used / 1024:.1f} / {total / 1024:.1f} GB"
            )




if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName("PC Dashboard")
    app.setStyle("Fusion")
    window = Dashboard()
    window.show()
    sys.exit(app.exec())
