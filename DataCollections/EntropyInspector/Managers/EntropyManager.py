"""
EntropyManager.py
=================
Lớp điều phối (Orchestrator) toàn bộ phân hệ EntropyInspector:
- Quản lý vòng đời của SnapshotInspector (quét tĩnh) và RealtimeWatcher (giám sát động).
- Tự động hóa tổ chức kết xuất các tệp tin CSV chuẩn về đúng thư mục Data/Raw/.
- Cung cấp tiện ích so sánh chênh lệch Entropy Trước vs. Sau (Baseline vs. Final).
"""

import csv
import sys
from pathlib import Path
from typing import List, Dict, Optional, Any

try:
    from ..Inspectors import (
        BaseInspector,
        EntropyEvent,
        SnapshotInspector,
        RealtimeWatcher,
    )
    from ..Calculators import ShannonEntropyCalculator
except (ImportError, ValueError):
    from DataCollections.EntropyInspector.Inspectors import (
        BaseInspector,
        EntropyEvent,
        SnapshotInspector,
        RealtimeWatcher,
    )
    from DataCollections.EntropyInspector.Calculators import ShannonEntropyCalculator


class EntropyManager:
    """
    Bộ điều phối trung tâm quản lý các phiên giám định Shannon Entropy.
    """

    def __init__(
        self,
        target_dirs: Optional[List[Path]] = None,
        raw_data_dir: Optional[Path] = None,
        calculator: Optional[ShannonEntropyCalculator] = None,
    ) -> None:
        """
        Khởi tạo EntropyManager và nạp sẵn 2 bộ thanh tra (Snapshot & Realtime).
        """
        self.target_dirs: List[Path] = target_dirs or self._default_directories()
        self.raw_data_dir: Path = raw_data_dir or self._default_raw_dir()
        self.raw_data_dir.mkdir(parents=True, exist_ok=True)

        self.calculator: ShannonEntropyCalculator = calculator or ShannonEntropyCalculator()
        self.snapshot_inspector = SnapshotInspector(
            target_dirs=self.target_dirs,
            calculator=self.calculator
        )
        self.realtime_watcher = RealtimeWatcher(
            target_dirs=self.target_dirs,
            calculator=self.calculator
        )

    def _default_directories(self) -> List[Path]:
        """Xác định các thư mục mồi mặc định trên Windows Sandbox."""
        home = Path.home()
        return [
            home / "Desktop" / "DecoyDocs",
            home / "Documents" / "DecoyDocs",
            home / "Downloads" / "DecoyDocs",
        ]

    def _default_raw_dir(self) -> Path:
        """Xác định đường dẫn chuẩn tới thư mục Data/Raw của dự án."""
        # Trỏ ngược 3 cấp thư mục từ EntropyInspector/Managers -> Root -> Data/Raw
        return Path(__file__).resolve().parents[3] / "Data" / "Raw"

    def take_baseline_snapshot(self, filename: str = "baseline_entropy.csv") -> Path:
        """
        Chụp ảnh Entropy gốc của toàn bộ tệp tin mồi trước khi bắt đầu thử nghiệm.
        Lưu kết quả trực tiếp vào Data/Raw/<filename>.
        """
        print(f"\n[*] Đang quét Snapshot gốc (Baseline) trên {len(self.target_dirs)} thư mục mồi...")
        events = self.snapshot_inspector.scan(recursive=True)

        output_path = self.raw_data_dir / filename
        self.snapshot_inspector.export_to_csv(output_path, events=events)

        summary = self.snapshot_inspector.get_summary(events)
        self.print_summary("BÁO CÁO SNAPSHOT GỐC (BASELINE)", summary)
        print(f"[+] Đã lưu file Baseline Entropy thành công tại: {output_path}")
        return output_path

    def take_final_snapshot(self, filename: str = "final_entropy.csv") -> Path:
        """
        Quét kiểm kê lại toàn bộ tệp tin mồi sau khi kịch bản/ransomware kết thúc.
        Lưu kết quả trực tiếp vào Data/Raw/<filename>.
        """
        print(f"\n[*] Đang quét Snapshot sau thử nghiệm (Final) trên {len(self.target_dirs)} thư mục mồi...")
        events = self.snapshot_inspector.scan(recursive=True)

        output_path = self.raw_data_dir / filename
        self.snapshot_inspector.export_to_csv(output_path, events=events)

        summary = self.snapshot_inspector.get_summary(events)
        self.print_summary("BÁO CÁO SNAPSHOT SAU THỬ NGHIỆM (FINAL)", summary)
        print(f"[+] Đã lưu file Final Entropy thành công tại: {output_path}")
        return output_path

    def compare_snapshots(
        self,
        baseline_csv: Path,
        final_csv: Path
    ) -> Dict[str, Any]:
        """
        So sánh sự biến thiên Entropy giữa Snapshot trước và Snapshot sau thử nghiệm.
        """
        baseline_csv = Path(baseline_csv)
        final_csv = Path(final_csv)

        if not baseline_csv.exists() or not final_csv.exists():
            print("[!] Lỗi: Không tìm thấy tệp CSV Snapshot để so sánh.", file=sys.stderr)
            return {}

        baseline_map: Dict[str, float] = {}
        with open(baseline_csv, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                baseline_map[row["FilePath"]] = float(row["Entropy"])

        final_map: Dict[str, float] = {}
        with open(final_csv, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                final_map[row["FilePath"]] = float(row["Entropy"])

        # Tính toán biến thiên
        common_files = set(baseline_map.keys()) & set(final_map.keys())
        created_files = set(final_map.keys()) - set(baseline_map.keys())
        deleted_files = set(baseline_map.keys()) - set(final_map.keys())

        modified_high_entropy = 0
        deltas: List[float] = []

        for p in common_files:
            b_ent = baseline_map[p]
            f_ent = final_map[p]
            diff = f_ent - b_ent
            deltas.append(diff)
            # Phát hiện tệp bị tăng vọt Entropy từ thấp lên ngưỡng mã hóa
            if b_ent < 6.5 and f_ent >= 7.0:
                modified_high_entropy += 1

        avg_delta = sum(deltas) / len(deltas) if deltas else 0.0

        comparison = {
            "total_baseline_files": len(baseline_map),
            "total_final_files": len(final_map),
            "retained_files": len(common_files),
            "created_files": len(created_files),
            "deleted_files": len(deleted_files),
            "modified_to_high_entropy": modified_high_entropy,
            "average_entropy_delta": round(avg_delta, 4),
        }

        print(f"\n{'=' * 60}")
        print("          BÁO CÁO SO SÁNH BIẾN THIÊN ENTROPY")
        print(f"{'=' * 60}")
        print(f"• Số tệp gốc (Baseline)          : {comparison['total_baseline_files']}")
        print(f"• Số tệp sau thử nghiệm (Final)   : {comparison['total_final_files']}")
        print(f"• Số tệp mới sinh ra             : {comparison['created_files']}")
        print(f"• Số tệp đã bị xóa               : {comparison['deleted_files']}")
        print(f"• Số tệp BỊ MÃ HÓA (Entropy >=7) : {comparison['modified_to_high_entropy']}")
        print(f"• Độ tăng Entropy trung bình ΔH  : {comparison['average_entropy_delta']}")
        print(f"{'=' * 60}\n")

        return comparison

    def start_realtime_watch(self) -> None:
        """Kích hoạt RealtimeWatcher chạy ngầm."""
        self.realtime_watcher.start()

    def stop_realtime_watch(self, filename: str = "raw_entropy_events.csv") -> Path:
        """
        Dừng RealtimeWatcher, xuất toàn bộ sự kiện ra file CSV và in tóm tắt.
        Lưu kết quả trực tiếp vào Data/Raw/<filename>.
        """
        events = self.realtime_watcher.stop()
        output_path = self.raw_data_dir / filename
        self.realtime_watcher.export_to_csv(output_path, events=events)

        summary = self.realtime_watcher.get_summary(events)
        self.print_summary("BÁO CÁO GIÁM SÁT THỜI GIAN THỰC (REALTIME)", summary)
        print(f"[+] Đã lưu file Realtime Entropy Events tại: {output_path}")
        return output_path

    @staticmethod
    def print_summary(title: str, summary: Dict[str, Any]) -> None:
        """In bảng tóm tắt trực quan ra màn hình terminal."""
        print(f"\n{'=' * 60}")
        print(f"               {title}")
        print(f"{'=' * 60}")
        for key, val in summary.items():
            formatted_key = key.replace("_", " ").title()
            if isinstance(val, dict):
                print(f"• {formatted_key}:")
                for sub_k, sub_v in val.items():
                    print(f"   - {sub_k:<15}: {sub_v}")
            else:
                print(f"• {formatted_key:<26}: {val}")
        print(f"{'=' * 60}\n")

