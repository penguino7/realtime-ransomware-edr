
import sys
import time
import random
from pathlib import Path
from typing import List, Dict, Optional, Any

try:
    from Src.Core.Config import Config
except (ImportError, ValueError):
    from Core.Config import Config

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
        CompileWorkload,
        FileOpsWorkload,
        ImageWorkload,
    )
except (ImportError, ValueError):
    from Workloads import (
        BaseWorkload,
        CompressionWorkload,
        OfficeWorkload,
        DevelopmentWorkload,
        CompileWorkload,
        FileOpsWorkload,
        ImageWorkload,
    )


# Bộ quản lý và điều phối các workload mô phỏng hành vi người dùng
class WorkloadManager:

    # Khởi tạo WorkloadManager và nạp các kịch bản hành vi
    def __init__(
        self,
        target_dirs: Optional[List[Path]] = None,
        custom_tool_path: Optional[str] = None
    ) -> None:
        self.target_dirs: List[Path] = target_dirs or self._default_directories()
        self.custom_tool_path = custom_tool_path
        self.history: List[Dict[str, Any]] = []

        # Khởi tạo các workload thành phần và các chế độ thao tác tệp độc lập
        self.workloads: Dict[str, BaseWorkload] = {
            "compression": CompressionWorkload(
                target_dirs=self.target_dirs,
                custom_tool_path=self.custom_tool_path
            ),
            "office": OfficeWorkload(target_dirs=self.target_dirs),
            "development": DevelopmentWorkload(target_dirs=self.target_dirs),
            "compile": CompileWorkload(target_dirs=self.target_dirs),
            "fileops": FileOpsWorkload(target_dirs=self.target_dirs, mode="mixed"),
            # 4 chế độ thao tác tệp độc lập quy mô lớn (80 - 200 files) kích hoạt Ticks
            "copy": FileOpsWorkload(target_dirs=self.target_dirs, mode="copy"),
            "rename": FileOpsWorkload(target_dirs=self.target_dirs, mode="rename"),
            "delete": FileOpsWorkload(target_dirs=self.target_dirs, mode="delete"),
            "read": FileOpsWorkload(target_dirs=self.target_dirs, mode="read"),
            # Đặt thêm alias fileops_* để tương thích tối đa các cách gọi
            "fileops_copy": FileOpsWorkload(target_dirs=self.target_dirs, mode="copy"),
            "fileops_rename": FileOpsWorkload(target_dirs=self.target_dirs, mode="rename"),
            "fileops_delete": FileOpsWorkload(target_dirs=self.target_dirs, mode="delete"),
            "fileops_read": FileOpsWorkload(target_dirs=self.target_dirs, mode="read"),
            "image": ImageWorkload(target_dirs=self.target_dirs),
        }

    def _default_directories(self) -> List[Path]:
        return Config.get_monitored_directories()

    # Nghỉ ngẫu nhiên giữa các lần thực thi
    def _delay(self, min_sec: float, max_sec: float) -> None:
        if max_sec > 0:
            time.sleep(random.uniform(min_sec, max_sec))

    # Thực thi một kịch bản chỉ định trong N chu kỳ
    def run_workload(
        self,
        task_name: str,
        iterations: int = 1,
        min_delay: float = 1.0,
        max_delay: float = 3.0
    ) -> List[Dict[str, Any]]:
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
       
        sequential_tasks = [
            "office",
            "development",
            "compile",
            "copy",
            "rename",
            "delete",
            "read",
            "image",
            "compression",
        ]

        print(f"\n{'=' * 60}")
        print(f"[*] Bắt đầu chạy tuần tự {len(sequential_tasks)} kịch bản chuyên biệt...")
        print(f"{'=' * 60}")

        results: List[Dict[str, Any]] = []
        for task_key in sequential_tasks:
            task_results = self.run_workload(
                task_name=task_key,
                iterations=iterations_per_task,
                min_delay=min_delay,
                max_delay=max_delay
            )
            results.extend(task_results)
            self._delay(min_delay, max_delay)

        return results

    # Mô phỏng ngày làm việc bằng cách chọn xen kẽ các kịch bản theo trọng số xác suất
    def run_mixed(
        self,
        total_actions: int = 10,
        min_delay: float = 1.0,
        max_delay: float = 3.0,
        weights: Optional[Dict[str, float]] = None
    ) -> List[Dict[str, Any]]:
        if weights is None:
            weights = {
                "office": 0.25,
                "development": 0.20,
                "compile": 0.15,
                "fileops": 0.15,
                "image": 0.15,
                "compression": 0.10,
            }

        tasks = list(weights.keys())
        prob_weights = [weights[task] for task in tasks]

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

    # In báo cáo thống kê tổng kết số lượt chạy của các kịch bản
    def print_summary(self, results: Optional[List[Dict[str, Any]]] = None) -> None:
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
