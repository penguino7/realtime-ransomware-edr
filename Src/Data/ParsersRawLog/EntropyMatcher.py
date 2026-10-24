

from typing import Tuple

try:
    from ...Core.Schemas import IRPOperation
    from .EntropyLoader import EntropyLoader
except (ImportError, ValueError):
    from Src.Core.Schemas import IRPOperation
    from Src.Data.ParsersRawLog.EntropyLoader import EntropyLoader


class EntropyMatcher:
    """
    Thực hiện ghép cặp thời gian thực giữa thao tác IRP của tiến trình
    với giá trị Shannon Entropy tương ứng từ EntropyLoader.
    """

    def __init__(self, loader: EntropyLoader, tolerance_sec: float = 2.0) -> None:
        """
        Khởi tạo EntropyMatcher với bộ nạp EntropyLoader.
        """
        self.loader = loader
        self.tolerance_sec = tolerance_sec

    def match(
        self,
        norm_path: str,
        irp_ts: float,
        op: IRPOperation
    ) -> Tuple[float, float]:
        """
        Tìm giá trị Shannon Entropy tương ứng với thời điểm và thao tác IRP.
        """
        baseline_h = self.loader.baseline_map.get(norm_path, 0.0)

        # 1. Thao tác XÓA file -> Entropy sau khi xóa bằng 0.0
        if op == IRPOperation.DELETE:
            return 0.0, baseline_h

        # 2. Tìm sự kiện đo Watchdog gần nhất trong realtime map
        events = self.loader.realtime_map.get(norm_path)
        if events:
            best_event = min(events, key=lambda e: abs(e[0] - irp_ts))
            diff_sec = abs(best_event[0] - irp_ts)
            if diff_sec <= self.tolerance_sec:
                return best_event[1], baseline_h

        # 3. Fallback an toàn: Thao tác READ hoặc chưa kịp đo -> giữ nguyên baseline
        return baseline_h, baseline_h
