"""
Giám sát sự thay đổi I/O realtime và tính entropy trong realtime
"""

import time
import queue
import threading
from pathlib import Path
from typing import List, Dict, Optional, Any, Tuple

try:
    from watchdog.observers import Observer
    from watchdog.events import (
        FileSystemEventHandler,
        FileModifiedEvent,
        FileCreatedEvent,
        FileMovedEvent,
    )
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False
    Observer = None
    FileSystemEventHandler = object

try:
    from .BaseInspector import BaseInspector, EntropyEvent
    from ..Calculators import ShannonEntropyCalculator, EntropyResult
except (ImportError, ValueError):
    from DataCollections.EntropyInspector.Inspectors.BaseInspector import (
        BaseInspector,
        EntropyEvent,
    )
    from DataCollections.EntropyInspector.Calculators import (
        ShannonEntropyCalculator,
        EntropyResult,
    )


class _EntropyEventHandler(FileSystemEventHandler if WATCHDOG_AVAILABLE else object):
    """
    Bộ lắng nghe sự kiện từ Windows Kernel qua Watchdog (Producer).
    Đẩy nhanh sự kiện vào hàng đợi thread-safe trong micro-giây, không chặn luồng hệ điều hành.
    """

    def __init__(self, event_queue: queue.Queue, debounce_sec: float = 0.1) -> None:
        super().__init__()
        self.event_queue = event_queue
        self.debounce_sec = debounce_sec
        self._last_event_times: Dict[str, float] = {}
        self._lock = threading.Lock()

    def _should_process(self, file_path_str: str) -> bool:
        """
        Lọc bỏ thư mục, tệp ẩn hệ thống và loại bỏ sự kiện trùng lặp.
        """
        p = Path(file_path_str)
        # Bỏ qua thư mục và các tệp ẩn hệ thống (.git, .vscode, .)
        if p.name.startswith("."):
            return False

        now = time.time()
        with self._lock:
            last_time = self._last_event_times.get(file_path_str, 0.0)
            if now - last_time < self.debounce_sec:
                return False
            self._last_event_times[file_path_str] = now

            # Dọn dẹp cache debounce định kỳ để không phình bộ nhớ RAM
            if len(self._last_event_times) > 5000:
                cutoff = now - 5.0
                self._last_event_times = {
                    k: v for k, v in self._last_event_times.items() if v > cutoff
                }
        return True

    def on_modified(self, event) -> None:
        if event.is_directory:
            return
        if self._should_process(event.src_path):
            self.event_queue.put(("MODIFIED", event.src_path, None))

    def on_created(self, event) -> None:
        if event.is_directory:
            return
        if self._should_process(event.src_path):
            self.event_queue.put(("CREATED", event.src_path, None))

    def on_moved(self, event) -> None:
        if event.is_directory:
            return
        # Khi tệp bị đổi tên / đổi đuôi: dest_path là đường dẫn tệp mới
        if self._should_process(event.dest_path):
            self.event_queue.put(("RENAMED", event.dest_path, event.src_path))


class RealtimeWatcher(BaseInspector):
    """
    Giám sát động thời gian thực (Realtime Event-Driven Watcher).
    """

    def __init__(
        self,
        target_dirs: Optional[List[Path]] = None,
        calculator: Optional[ShannonEntropyCalculator] = None,
        debounce_sec: float = 0.1,
    ) -> None:
        super().__init__(target_dirs=target_dirs, calculator=calculator)
        self.debounce_sec = debounce_sec
        self.event_queue: queue.Queue = queue.Queue()
        self.observer: Optional[Any] = None
        self.worker_thread: Optional[threading.Thread] = None
        self.is_running: bool = False
        self._stop_event = threading.Event()

    def _worker_loop(self) -> None:
        """
        Vòng lặp tiêu thụ sự kiện trong Background Thread.
        Rút sự kiện từ Queue và đo đạc Entropy 64KB đầu an toàn bằng Calculator.
        """
        while not self._stop_event.is_set() or not self.event_queue.empty():
            try:
                item = self.event_queue.get(timeout=0.1)
            except queue.Empty:
                continue

            if item is None:
                try:
                    self.event_queue.task_done()
                except ValueError:
                    pass
                break

            event_type, file_path, old_path = item

            try:
                # Gọi calculator đo đạc an toàn (có Exponential Backoff chống lock)
                res: EntropyResult = self.calculator.inspect_file(file_path)

                # Bỏ qua an toàn nếu tệp tạm đã bị xóa chớp nhoáng
                if res.status == self.calculator.STATUS_NOT_FOUND:
                    continue

                timestamp = self.get_current_timestamp()
                ev = EntropyEvent(
                    timestamp=timestamp,
                    event_type=event_type,
                    file_path=file_path,
                    old_path=old_path,
                    entropy=res.entropy,
                    file_size=res.file_size,
                    status=res.status,
                    read_time_ms=res.read_time_ms,
                )
                self.events.append(ev)
            except Exception:
                pass
            finally:
                try:
                    self.event_queue.task_done()
                except ValueError:
                    pass

    def start(self) -> None:
        """
        Kích hoạt luồng lắng nghe Watchdog và luồng Worker tính toán ngầm.
        """
        if not WATCHDOG_AVAILABLE:
            raise RuntimeError(
                "Thư viện 'watchdog' chưa được cài đặt trong môi trường. "
                "Vui lòng cài đặt bằng lệnh: pip install watchdog"
            )

        if self.is_running:
            return

        self.is_running = True
        self._stop_event.clear()

        # 1. Khởi động Consumer Worker Thread
        self.worker_thread = threading.Thread(
            target=self._worker_loop,
            name="RealtimeWatcherWorker",
            daemon=True
        )
        self.worker_thread.start()

        # 2. Khởi động Producer Watchdog Observer
        self.observer = Observer()
        handler = _EntropyEventHandler(
            event_queue=self.event_queue,
            debounce_sec=self.debounce_sec
        )

        active_dirs = 0
        for directory in self.target_dirs:
            if directory.exists() and directory.is_dir():
                self.observer.schedule(handler, str(directory), recursive=True)
                active_dirs += 1

        if active_dirs > 0:
            self.observer.start()
            print(f"[*] [RealtimeWatcher] Đã khởi động lắng nghe thời gian thực trên {active_dirs} thư mục mồi...")
        else:
            print("[!] [RealtimeWatcher] Cảnh báo: Không có thư mục mục tiêu nào tồn tại trên đĩa.")

    def stop(self) -> List[EntropyEvent]:
        """
        Dừng Observer, đợi Worker xử lý hết hàng đợi và trả về danh sách toàn bộ EntropyEvent.
        """
        if not self.is_running:
            return self.events

        self.is_running = False

        # 1. Dừng Watchdog Observer
        if self.observer:
            try:
                self.observer.stop()
                self.observer.join(timeout=2.0)
            except Exception:
                pass
            self.observer = None

        # 2. Dừng Consumer Worker Thread
        self._stop_event.set()
        self.event_queue.put(None)  # Sentinel báo kết thúc

        if self.worker_thread and self.worker_thread.is_alive():
            self.worker_thread.join(timeout=3.0)
            self.worker_thread = None

        print(f"[+] [RealtimeWatcher] Đã dừng. Thu thập được tổng cộng {len(self.events)} sự kiện Entropy.")
        return self.events

    def get_summary(
        self,
        events: Optional[List[EntropyEvent]] = None
    ) -> Dict[str, Any]:
        """
        Tổng hợp thống kê các sự kiện động đã bắt được trong phiên.
        """
        target_events = events if events is not None else self.events
        total = len(target_events)

        if total == 0:
            return {
                "total_events": 0,
                "by_event_type": {},
                "mean_entropy": 0.0,
                "high_entropy_count": 0,
            }

        by_type: Dict[str, int] = {}
        for e in target_events:
            by_type[e.event_type] = by_type.get(e.event_type, 0) + 1

        entropies = [e.entropy for e in target_events]
        mean_entropy = sum(entropies) / total
        high_entropy_count = sum(1 for h in entropies if h >= 7.0)

        return {
            "total_events": total,
            "by_event_type": by_type,
            "mean_entropy": round(mean_entropy, 4),
            "high_entropy_count": high_entropy_count,
            "high_entropy_ratio": round(high_entropy_count / total, 4),
        }
