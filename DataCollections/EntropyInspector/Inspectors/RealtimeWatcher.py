import time
import queue
import logging
import threading
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Any, Tuple, Union
from logging.handlers import RotatingFileHandler

logger = logging.getLogger(__name__)

try:
    from watchdog.observers import Observer
    from watchdog.events import (
        FileSystemEventHandler,
        FileModifiedEvent,
        FileCreatedEvent,
        FileMovedEvent,
        FileDeletedEvent,
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
    Đóng dấu thời gian ngay tại thời điểm phát sinh sự kiện và đẩy nhanh vào hàng đợi trong micro-giây.
    """

    def __init__(self, event_queue: queue.Queue, debounce_sec: float = 0.05) -> None:
        super().__init__()
        self.event_queue = event_queue
        self.debounce_sec = debounce_sec
        self._last_event_times: Dict[Tuple[str, str], float] = {}
        self._lock = threading.Lock()

    def _should_process(self, file_path_str: str, event_type: str) -> bool:
        p = Path(file_path_str)
        # Bỏ qua các tệp ẩn hệ thống (.git, .vscode, .)
        if p.name.startswith("."):
            return False

        now = time.time()
        key = (file_path_str, event_type)
        with self._lock:
            last_time = self._last_event_times.get(key, 0.0)
            if now - last_time < self.debounce_sec:
                logger.debug("Bỏ qua sự kiện %s cho '%s' do debounce (%.3fs)", event_type, file_path_str, now - last_time)
                return False
            self._last_event_times[key] = now

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
        if self._should_process(event.src_path, "MODIFIED"):
            event_time = time.time()
            self.event_queue.put(("MODIFIED", event.src_path, None, event_time))

    def on_created(self, event) -> None:
        if event.is_directory:
            return
        if self._should_process(event.src_path, "CREATED"):
            event_time = time.time()
            self.event_queue.put(("CREATED", event.src_path, None, event_time))

    def on_moved(self, event) -> None:
        if event.is_directory:
            return
        if self._should_process(event.dest_path, "RENAMED"):
            event_time = time.time()
            self.event_queue.put(("RENAMED", event.dest_path, event.src_path, event_time))

    def on_deleted(self, event) -> None:
        if event.is_directory:
            return
        if self._should_process(event.src_path, "DELETED"):
            event_time = time.time()
            self.event_queue.put(("DELETED", event.src_path, None, event_time))


class RealtimeWatcher(BaseInspector):
    """
    Bộ thanh tra và lắng nghe sự kiện hệ thống tệp thời gian thực (Realtime Watchdog).
    Mô hình Producer-Consumer đa luồng:
    - 1 Producer (Watchdog Observer) đẩy sự kiện kèm timestamp gốc vào Queue.
    - 3 Background Worker Threads tiêu thụ Queue và tính toán Shannon Entropy song song.
    - Hỗ trợ ghi log chuyên biệt theo từng session (RotatingFileHandler) để chẩn đoán lỗi đo đạc.
    """

    def __init__(
        self,
        target_dirs: Optional[List[Path]] = None,
        calculator: Optional[ShannonEntropyCalculator] = None,
        debounce_sec: float = 0.05,
        num_workers: int = 3,
        log_file: Optional[Union[str, Path]] = None,
        log_level: int = logging.INFO,
    ) -> None:
        super().__init__(target_dirs=target_dirs, calculator=calculator)
        self.debounce_sec = debounce_sec
        self.num_workers = max(1, num_workers)
        self.event_queue: queue.Queue = queue.Queue()
        self.observer: Optional[Any] = None
        self.worker_threads: List[threading.Thread] = []
        self.is_running: bool = False
        self._stop_event = threading.Event()
        self._events_lock = threading.Lock()

        # Quản lý file log riêng cho từng session
        self.log_file: Optional[Path] = Path(log_file) if log_file else None
        self.log_level: int = log_level
        self._file_handler: Optional[RotatingFileHandler] = None

        # Bộ đếm chẩn đoán chất lượng thu thập
        self.error_count: int = 0
        self.not_found_count: int = 0

    def _setup_file_logger(self) -> None:
        """Thiết lập RotatingFileHandler riêng cho session (5MB, 3 backups) chống tràn ổ đĩa."""
        if not self.log_file:
            return

        self._teardown_file_logger()

        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] [%(threadName)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler = RotatingFileHandler(
            str(self.log_file),
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
        handler.setFormatter(formatter)
        handler.setLevel(self.log_level)
        logger.addHandler(handler)
        if logger.level > self.log_level or logger.level == 0:
            logger.setLevel(self.log_level)
        self._file_handler = handler

    def _teardown_file_logger(self) -> None:
        """Đóng và giải phóng file handler tránh lock tệp trên Windows."""
        if self._file_handler:
            try:
                self._file_handler.flush()
                self._file_handler.close()
                logger.removeHandler(self._file_handler)
            except Exception:
                pass
            finally:
                self._file_handler = None

    def _worker_loop(self) -> None:
        """
        Vòng lặp tiêu thụ sự kiện trong Background Worker Thread.
        Rút sự kiện từ Queue, sử dụng timestamp gốc của Producer và đo đạc Entropy an toàn.
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

            event_type, file_path, old_path, event_time = item
            timestamp_str = datetime.fromtimestamp(event_time).strftime("%H:%M:%S.%f")

            try:
                # 1. Xử lý riêng sự kiện DELETED (không đọc đĩa vì file đã biến mất)
                if event_type == "DELETED":
                    ev = EntropyEvent(
                        timestamp=timestamp_str,
                        event_type="DELETED",
                        file_path=file_path,
                        old_path=None,
                        entropy=0.0,
                        file_size=0,
                        status="STATUS_DELETED",
                        read_time_ms=0.0,
                    )
                    with self._events_lock:
                        self.events.append(ev)
                    logger.debug("Ghi nhận sự kiện xóa tệp: %s", file_path)
                    continue

                # 2. Xử lý các sự kiện MODIFIED, CREATED, RENAMED (Đo 64KB đầu buffer)
                res: EntropyResult = self.calculator.inspect_file(file_path)

                # Bỏ qua an toàn nếu tệp tạm đã bị xóa chớp nhoáng (ví dụ .tmp)
                if res.status == self.calculator.STATUS_NOT_FOUND:
                    self.not_found_count += 1
                    logger.debug("Tệp tạm đã bị xóa trước khi đo (STATUS_NOT_FOUND): %s", file_path)
                    continue

                ev = EntropyEvent(
                    timestamp=timestamp_str,
                    event_type=event_type,
                    file_path=file_path,
                    old_path=old_path,
                    entropy=res.entropy,
                    file_size=res.file_size,
                    status=res.status,
                    read_time_ms=res.read_time_ms,
                )
                with self._events_lock:
                    self.events.append(ev)
                logger.debug("Đo entropy [%s] %s: H=%.4f (status=%s)", event_type, file_path, res.entropy, res.status)
            except FileNotFoundError:
                self.not_found_count += 1
                logger.debug("File đã biến mất trước khi kịp đo: %s", file_path)
            except Exception as e:
                self.error_count += 1
                logger.warning("Lỗi đo entropy tệp %s: %s", file_path, e, exc_info=True)
            finally:
                try:
                    self.event_queue.task_done()
                except ValueError:
                    pass

    def start(self) -> None:
        """
        Kích hoạt luồng lắng nghe Watchdog và Worker Pool 3 luồng tính toán ngầm.
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
        self.error_count = 0
        self.not_found_count = 0
        self._setup_file_logger()

        # 1. Khởi động Worker Pool đa luồng (3 workers song song)
        self.worker_threads.clear()
        for i in range(self.num_workers):
            t = threading.Thread(
                target=self._worker_loop,
                name=f"RealtimeWatcherWorker-{i+1}",
                daemon=True,
            )
            t.start()
            self.worker_threads.append(t)

        # 2. Khởi động Producer Watchdog Observer
        self.observer = Observer()
        handler = _EntropyEventHandler(
            event_queue=self.event_queue,
            debounce_sec=self.debounce_sec,
        )

        active_dirs = 0
        for directory in self.target_dirs:
            if directory.exists() and directory.is_dir():
                self.observer.schedule(handler, str(directory), recursive=True)
                active_dirs += 1

        if active_dirs > 0:
            self.observer.start()
            logger.info(
                "Đã khởi động RealtimeWatcher trên %d thư mục mồi (Workers: %d, Debounce: %.2fs)",
                active_dirs, self.num_workers, self.debounce_sec,
            )
            print(
                f"[*] [RealtimeWatcher] Đã khởi động lắng nghe thời gian thực trên {active_dirs} thư mục mồi "
                f"(Worker Pool: {self.num_workers} threads, Debounce: {self.debounce_sec}s)..."
            )
        else:
            logger.warning("Không có thư mục mục tiêu nào tồn tại trên đĩa.")
            print("[!] [RealtimeWatcher] Cảnh báo: Không có thư mục mục tiêu nào tồn tại trên đĩa.")

    def stop(self) -> List[EntropyEvent]:
        """
        Dừng Observer, đợi Worker Pool xử lý hết sạch hàng đợi (event_queue.join)
        và trả về danh sách toàn bộ EntropyEvent đã sắp xếp theo thứ tự thời gian.
        """
        if not self.is_running:
            self._teardown_file_logger()
            return self.events

        self.is_running = False

        # 1. Dừng Watchdog Observer để ngừng nhận thêm sự kiện mới từ OS
        if self.observer:
            try:
                self.observer.stop()
                self.observer.join(timeout=2.0)
            except Exception as e:
                logger.warning("Lỗi dừng Observer: %s", e, exc_info=True)
            self.observer = None

        # 2. Đợi Worker Pool xử lý HẾT SẠCH hàng đợi (bảo toàn 100% sự kiện cuối phiên)
        try:
            self.event_queue.join()
        except Exception as e:
            logger.warning("Lỗi đợi hàng đợi: %s", e, exc_info=True)

        # 3. Ra cờ dừng và gửi Poison Pill cho tất cả worker threads
        self._stop_event.set()
        for _ in self.worker_threads:
            self.event_queue.put(None)

        # 4. Đợi các luồng worker kết thúc an toàn
        for t in self.worker_threads:
            try:
                t.join(timeout=5.0)
            except Exception as e:
                logger.warning("Lỗi kết thúc luồng worker %s: %s", t.name, e, exc_info=True)
        self.worker_threads.clear()

        # 5. Sắp xếp lại danh sách sự kiện theo thứ tự thời gian tuyệt đối
        with self._events_lock:
            self.events.sort(key=lambda x: x.timestamp)

        # 6. Ghi 1 dòng tổng kết duy nhất vào log file
        summary_msg = (
            f"Phiên giám sát kết thúc: Tổng thu thập {len(self.events)} sự kiện | "
            f"{self.error_count} lỗi đo đạc | {self.not_found_count} tệp không tồn tại/xóa nhanh."
        )
        logger.info(summary_msg)
        print(f"[+] [RealtimeWatcher] Đã dừng. Thu thập thành công {len(self.events)} sự kiện Entropy.")

        # 7. Đóng file handler và dọn dẹp
        self._teardown_file_logger()

        return self.events

    def get_summary(
        self,
        events: Optional[List[EntropyEvent]] = None,
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
                "error_count": self.error_count,
                "not_found_count": self.not_found_count,
            }

        by_type: Dict[str, int] = {}
        for e in target_events:
            by_type[e.event_type] = by_type.get(e.event_type, 0) + 1

        entropies = [e.entropy for e in target_events if e.event_type != "DELETED"]
        mean_entropy = sum(entropies) / len(entropies) if entropies else 0.0
        high_entropy_count = sum(1 for h in entropies if h >= 7.0)

        return {
            "total_events": total,
            "by_event_type": by_type,
            "mean_entropy": round(mean_entropy, 4),
            "high_entropy_count": high_entropy_count,
            "high_entropy_ratio": round(high_entropy_count / total, 4) if total > 0 else 0.0,
            "error_count": self.error_count,
            "not_found_count": self.not_found_count,
        }
