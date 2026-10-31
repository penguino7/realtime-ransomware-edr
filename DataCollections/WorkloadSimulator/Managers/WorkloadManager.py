
import sys
import time
import random
from pathlib import Path
from typing import List, Dict, Optional, Any

# Thiết lập encoding UTF-8 cho console Windows tránh UnicodeEncodeError (cp1252)
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

try:
    from ..Workloads import (
        BaseWorkload,
        CompressionWorkload,
        OfficeWorkload,
        DevelopmentWorkload,
        FileOpsWorkload,
        ImageWorkload,
    )
except (ImportError, ValueError):
    from Workloads import (
        BaseWorkload,
        CompressionWorkload,
        OfficeWorkload,
        DevelopmentWorkload,
        FileOpsWorkload,
        ImageWorkload,
    )


class WorkloadManager:
    """
    Bộ quản lý và điều phối các workload mô phỏng hành vi người dùng.
    """

    def __init__(
        self,
        target_dirs: Optional[List[Path]] = None,
        custom_tool_path: Optional[str] = None
    ) -> None:
        """
        Khởi tạo WorkloadManager và nạp 5 kịch bản hành vi.
        """
        self.target_dirs: List[Path] = target_dirs or self._default_directories()
        self.custom_tool_path = custom_tool_path
        self.history: List[Dict[str, Any]] = []

        # Khởi tạo đầy đủ 5 workload thành phần
        self.workloads: Dict[str, BaseWorkload] = {
            "compression": CompressionWorkload(
                target_dirs=self.target_dirs,
                custom_tool_path=self.custom_tool_path
            ),
            "office": OfficeWorkload(target_dirs=self.target_dirs),
            "development": DevelopmentWorkload(target_dirs=self.target_dirs),
            "fileops": FileOpsWorkload(target_dirs=self.target_dirs),
            "image": ImageWorkload(target_dirs=self.target_dirs),
        }

    def _default_directories(self) -> List[Path]:
        """
        Xác định 8 thư mục mục tiêu chuẩn của người dùng trên Windows cùng phân vùng ổ đĩa:
        Đồng bộ với FileEnvironmentManager và BaseWorkload.
        """
        home = Path.home()
        standard_user_folders = [
            "Desktop",
            "Documents",
            "Downloads",
            "Pictures",
            "Contacts",
            "Favorites",
            "Music",
            "Videos",
        ]

        directories: List[Path] = []
        for folder_name in standard_user_folders:
            folder_path = home / folder_name / "DecoyDocs"
            directories.append(folder_path)

        for drive in ["C:\\", "D:\\"]:
            drive_path = Path(drive)
            if drive_path.exists():
                decoy_drive_folder = drive_path / "DecoyDocs"
                try:
                    test_dir = decoy_drive_folder / ".test_write"
                    test_dir.mkdir(parents=True, exist_ok=True)
                    test_dir.rmdir()
                    directories.append(decoy_drive_folder)
                except (PermissionError, OSError):
                    pass

        if not directories:
            directories.append(Path.cwd() / "DecoyDocs")

        return directories

    def _delay(self, min_sec: float, max_sec: float) -> None:
        """Nghỉ ngẫu nhiên giữa các lần thực thi."""
        if max_sec > 0:
            time.sleep(random.uniform(min_sec, max_sec))

    def run_workload(
        self,
        task_name: str,
        iterations: int = 1,
        min_delay: float = 1.0,
        max_delay: float = 3.0
    ) -> List[Dict[str, Any]]:
        """
        Thực thi một kịch bản chỉ định trong N chu kỳ.
        """
        task_key = task_name.lower().strip()
        if task_key not in self.workloads:
            print(f"[!] Kịch bản '{task_name}' không tồn tại. Các kịch bản khả dụng: {list(self.workloads.keys())}")
            return []

        workload = self.workloads[task_key]
        print(f"\n{'=' * 60}")
        print(f"[*] Bắt đầu thực thi kịch bản '{task_key}' ({iterations} lần)...")
        print(f"{'=' * 60}")

        results: List[Dict[str, Any]] = []
        for i in range(1, iterations + 1):
            print(f"\n---> [{task_key.upper()}] Chu kỳ {i}/{iterations}")
            res = workload.execute()
            results.append(res)
            self.history.append(res)

            if i < iterations:
                self._delay(min_delay, max_delay)

        return results

    def run_all_sequential(
        self,
        iterations_per_task: int = 1,
        min_delay: float = 1.0,
        max_delay: float = 3.0
    ) -> List[Dict[str, Any]]:
        """
        Thực thi tuần tự từng kịch bản, mỗi kịch bản N chu kỳ.
        """
        print(f"\n{'=' * 60}")
        print(f"[*] Bắt đầu chạy tuần tự tất cả 5 kịch bản...")
        print(f"{'=' * 60}")

        results: List[Dict[str, Any]] = []
        for task_key in self.workloads:
            task_results = self.run_workload(
                task_name=task_key,
                iterations=iterations_per_task,
                min_delay=min_delay,
                max_delay=max_delay
            )
            results.extend(task_results)
            self._delay(min_delay, max_delay)

        return results

    def run_mixed(
        self,
        total_actions: int = 10,
        min_delay: float = 1.0,
        max_delay: float = 3.0,
        weights: Optional[Dict[str, float]] = None
    ) -> List[Dict[str, Any]]:
        """
        Mô phỏng ngày làm việc tự nhiên của người dùng bằng cách chọn ngẫu nhiên
        các kịch bản xen kẽ nhau dựa trên phân phối trọng số xác suất thực tế:
        - Soạn thảo Office/Text: 30%
        - Lập trình Development & Database/Config: 25%
        - Thao tác tệp Copy/Rename/Delete: 20%
        - Xử lý đồ họa ảnh (Hard Benign): 15%
        - Nén/Giải nén tệp tin (thường & mật khẩu): 10%
        """
        if weights is None:
            weights = {
                "office": 0.30,
                "development": 0.25,
                "fileops": 0.20,
                "image": 0.15,
                "compression": 0.10,
            }

        tasks = list(self.workloads.keys())
        prob_weights = [weights.get(task, 1.0 / len(tasks)) for task in tasks]

        print(f"\n{'=' * 60}")
        print(f"[*] Bắt đầu kịch bản xen kẽ ngẫu nhiên (Mixed Mode: {total_actions} hành vi)...")
        print(f"[*] Phân phối trọng số: {weights}")
        print(f"{'=' * 60}")

        results: List[Dict[str, Any]] = []
        for i in range(1, total_actions + 1):
            chosen_task = random.choices(tasks, weights=prob_weights, k=1)[0]
            print(f"\n---> [MIXED {i}/{total_actions}] Chọn kịch bản: '{chosen_task.upper()}'")

            res = self.workloads[chosen_task].execute()
            results.append(res)
            self.history.append(res)

            if i < total_actions:
                self._delay(min_delay, max_delay)

        return results

    def print_summary(self, results: Optional[List[Dict[str, Any]]] = None) -> None:
        """
        In báo cáo thống kê tổng kết số lượt chạy của các kịch bản.
        """
        target_results = results if results is not None else self.history
        if not target_results:
            print("\n[i] Không có lịch sử thực thi để thống kê.")
            return

        total = len(target_results)
        success_count = sum(1 for r in target_results if r.get("status") == "success")
        failed_count = sum(1 for r in target_results if r.get("status") == "failed")
        skipped_count = sum(1 for r in target_results if r.get("status") == "skipped")

        # Thống kê theo từng loại workload
        by_workload: Dict[str, int] = {}
        for r in target_results:
            name = r.get("workload", "Unknown")
            by_workload[name] = by_workload.get(name, 0) + 1

        print(f"\n{'=' * 60}")
        print("               BÁO CÁO THỰC THI WORKLOAD")
        print(f"{'=' * 60}")
        print(f"- Tổng số lượt hành vi: {total}")
        print(f"  + Thành công : {success_count} ({success_count / total * 100:.1f}%)")
        print(f"  + Thất bại   : {failed_count} ({failed_count / total * 100:.1f}%)")
        print(f"  + Bỏ qua     : {skipped_count} ({skipped_count / total * 100:.1f}%)")
        print(f"- Phân bổ theo kịch bản:")
        for name, count in by_workload.items():
            print(f"  * {name:<24}: {count:>3} lần")
        print(f"{'=' * 60}\n")
