

from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, Tuple

try:
    from ..Core.Config import Config
    from ..Core.Schemas import IRPEvent, WindowSlice, IRPOperation
except (ImportError, ValueError):
    from Src.Core.Config import Config
    from Src.Core.Schemas import IRPEvent, WindowSlice, IRPOperation


@dataclass
class _ProcessBuffer:
    """
    Bộ đệm trạng thái nội bộ lưu trữ toàn bộ lịch sử thao tác của 1 tiến trình (PID).
    """
    pid: int
    process_name: str
    events: List[IRPEvent] = field(default_factory=list)
    distinct_files_seen: Set[str] = field(default_factory=set)
    distinct_files_order: List[str] = field(default_factory=list)
    ticks_emitted: int = 0

    def add_event(self, event: IRPEvent) -> None:
        """Thêm một sự kiện IRP vào bộ đệm và cập nhật tập hợp file riêng biệt."""
        self.events.append(event)
        if event.file_path:
            norm_path = event.file_path.strip().lower()
            if norm_path and norm_path not in self.distinct_files_seen:
                self.distinct_files_seen.add(norm_path)
                self.distinct_files_order.append(norm_path)

    def is_tick_ready(self, n_base: int) -> bool:
        """Kiểm tra xem tiến trình đã tích lũy đủ file để kích hoạt Tick tiếp theo chưa."""
        next_threshold = (self.ticks_emitted + 1) * n_base
        return len(self.distinct_files_seen) >= next_threshold

    def create_slices(
        self,
        short_size: int,
        medium_size: int
    ) -> Tuple[WindowSlice, WindowSlice, WindowSlice]:
        """
        Cắt 3 tầng cửa sổ (Short, Medium, Long) tại thời điểm kích hoạt Tick hiện tại.
        """
        # 1. Cửa sổ Dài (Long Window): Toàn bộ sự kiện từ đầu đến hiện tại
        long_distinct_files = set(self.distinct_files_seen)
        long_events = list(self.events)
        long_start = long_events[0].timestamp if long_events else 0.0
        long_end = long_events[-1].timestamp if long_events else 0.0

        long_slice = WindowSlice(
            window_type="LONG",
            events=long_events,
            distinct_files=long_distinct_files,
            start_time=long_start,
            end_time=long_end,
        )

        # 2. Cửa sổ Vừa (Medium Window): Tối đa 50 file riêng biệt gần nhất
        med_files_list = self.distinct_files_order[-medium_size:]
        med_distinct_files = set(med_files_list)
        med_events = self._filter_events_by_files(self.events, med_distinct_files)
        med_start = med_events[0].timestamp if med_events else long_start
        med_end = med_events[-1].timestamp if med_events else long_end

        med_slice = WindowSlice(
            window_type="MEDIUM",
            events=med_events,
            distinct_files=med_distinct_files,
            start_time=med_start,
            end_time=med_end,
        )

        # 3. Cửa sổ Ngắn (Short Window): Đúng 10 file riêng biệt gần nhất
        short_files_list = self.distinct_files_order[-short_size:]
        short_distinct_files = set(short_files_list)
        short_events = self._filter_events_by_files(self.events, short_distinct_files)
        short_start = short_events[0].timestamp if short_events else long_start
        short_end = short_events[-1].timestamp if short_events else long_end

        short_slice = WindowSlice(
            window_type="SHORT",
            events=short_events,
            distinct_files=short_distinct_files,
            start_time=short_start,
            end_time=short_end,
        )

        return short_slice, med_slice, long_slice

    @staticmethod
    def _filter_events_by_files(
        all_events: List[IRPEvent],
        target_files: Set[str]
    ) -> List[IRPEvent]:
        """
        Lọc danh sách các sự kiện thuộc về tập hợp các file mục tiêu,
        bắt đầu từ thời điểm file mục tiêu đầu tiên được truy cập đến sự kiện cuối cùng.
        """
        if not target_files or not all_events:
            return []

        # Tìm vị trí sự kiện đầu tiên chạm vào một trong các target_files
        first_idx = None
        for i, ev in enumerate(all_events):
            norm_path = ev.file_path.strip().lower() if ev.file_path else ""
            if norm_path in target_files:
                first_idx = i
                break

        if first_idx is None:
            return []

        # Lấy toàn bộ sự kiện từ mốc bắt đầu đó trở đi mà thuộc target_files
        return [
            ev for ev in all_events[first_idx:]
            if ev.file_path and ev.file_path.strip().lower() in target_files
        ]


class WindowManager:
    """
    Lớp điều phối quản lý cửa sổ trượt đa tầng và kích hoạt sự kiện Tick theo PID.
    Được dùng chung cho cả DatasetBuilder (offline) và Detector (online).
    """

    def __init__(
        self,
        n_base: Optional[int] = None,
        short_window_size: Optional[int] = None,
        medium_window_size: Optional[int] = None,
    ) -> None:
        """
        Khởi tạo WindowManager với các tham số cấu hình lấy từ Config.
        """
        self.n_base: int = n_base or Config.N_BASE
        self.short_window_size: int = short_window_size or Config.SHORT_WINDOW_SIZE
        self.medium_window_size: int = medium_window_size or Config.MEDIUM_WINDOW_SIZE

        # Bảng băm lưu trữ bộ đệm tiến trình: Dict[PID, _ProcessBuffer]
        self._buffers: Dict[int, _ProcessBuffer] = {}

    def add_event(
        self,
        event: IRPEvent
    ) -> Optional[Tuple[WindowSlice, WindowSlice, WindowSlice, int]]:
        """
        Tiếp nhận một sự kiện IRP, nạp vào bộ đệm của PID tương ứng và kiểm tra điều kiện Tick.

        Returns:
            Tuple[WindowSlice, WindowSlice, WindowSlice, int]: (short, med, long, tick_index)
            nếu sự kiện này kích hoạt Tick mới.
            None: nếu tiến trình chưa tích lũy đủ số file riêng biệt để đạt mốc Tick mới.
        """
        pid = event.pid
        if pid not in self._buffers:
            self._buffers[pid] = _ProcessBuffer(
                pid=pid,
                process_name=event.process_name
            )

        buf = self._buffers[pid]
        buf.add_event(event)

        # Kiểm tra điều kiện kích hoạt Tick (chạm mốc N_base * k files)
        if buf.is_tick_ready(self.n_base):
            buf.ticks_emitted += 1
            tick_index = buf.ticks_emitted
            short_s, med_s, long_s = buf.create_slices(
                short_size=self.short_window_size,
                medium_size=self.medium_window_size
            )
            return short_s, med_s, long_s, tick_index

        return None

    def get_process_windows(
        self,
        pid: int
    ) -> Optional[Tuple[WindowSlice, WindowSlice, WindowSlice, int]]:
        """
        Truy vấn nhanh bộ 3 lát cắt cửa sổ hiện tại của một tiến trình mà không làm tăng Tick.
        """
        buf = self._buffers.get(pid)
        if not buf or not buf.events:
            return None

        short_s, med_s, long_s = buf.create_slices(
            short_size=self.short_window_size,
            medium_size=self.medium_window_size
        )
        return short_s, med_s, long_s, buf.ticks_emitted

    def get_distinct_files_count(self, pid: int) -> int:
        """Trả về số lượng file riêng biệt mà tiến trình PID đã tác động đến thời điểm hiện tại."""
        buf = self._buffers.get(pid)
        return len(buf.distinct_files_seen) if buf else 0

    def cleanup_process(self, pid: int) -> None:
        """Giải phóng bộ đệm của một tiến trình khi tiến trình đó kết thúc hoặc bị tiêu diệt."""
        if pid in self._buffers:
            del self._buffers[pid]

    def reset(self) -> None:
        """Xóa sạch bộ đệm của toàn bộ tiến trình (dùng khi bắt đầu phiên mới)."""
        self._buffers.clear()

