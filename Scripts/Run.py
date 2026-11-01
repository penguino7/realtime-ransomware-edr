"""
Giao diện dòng lệnh điều phối tập trung (Central CLI Dispatcher) cho hệ thống Realtime Ransomware EDR:
- Tự động nạp Project Root vào sys.path.
- Cung cấp giao diện CLI thống nhất điều phối 4 phân hệ chính:
  1. filegen  : Sinh và dọn dẹp môi trường file mồi DecoyDocs (FileGenerator)
  2. workload : Giả lập hành vi người dùng lành tính (WorkloadSimulator)
  3. entropy  : Giám định Shannon Entropy snapshot / realtime (EntropyInspector)
  4. dataset  : Xây dựng tập dữ liệu huấn luyện dataset.csv (DatasetBuilder)
"""

import sys
import argparse
from pathlib import Path

# Đảm bảo console Windows hiển thị UTF-8 chuẩn xác, chống lỗi cp1252
if sys.platform.startswith("win"):
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Xác định Project Root và chèn vào đầu sys.path
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
for p in [str(SCRIPT_DIR), str(PROJECT_ROOT)]:
    if p not in sys.path:
        sys.path.insert(0, p)


def run_filegen(args: list) -> None:
    """Điều hướng tới FileGenerator Main CLI."""
    from DataCollections.FileGenerator.Main import main as filegen_main
    sys.argv = [sys.argv[0]] + args
    filegen_main()


def run_workload(args: list) -> None:
    """Điều hướng tới WorkloadSimulator Main CLI."""
    from DataCollections.WorkloadSimulator.Main import main as workload_main
    sys.argv = [sys.argv[0]] + args
    workload_main()


def run_entropy(args: list) -> None:
    """Điều hướng tới EntropyInspector Main CLI."""
    from DataCollections.EntropyInspector.Main import main as entropy_main
    sys.argv = [sys.argv[0]] + args
    entropy_main()


def run_dataset(args: list) -> None:
    """Điều hướng tới DatasetBuilder để xây dựng dataset.csv."""
    from Src.Data.DatasetBuilder import DatasetBuilder
    parser = argparse.ArgumentParser(description="DatasetBuilder - Xây dựng dataset.csv từ log Interim.")
    parser.add_argument("--reparse", action="store_true", help="Làm sạch và phân tích lại toàn bộ log thô Data/Raw/.")
    parsed = parser.parse_args(args)
    builder = DatasetBuilder(
        raw_dir=PROJECT_ROOT / "Data" / "Raw",
        interim_dir=PROJECT_ROOT / "Data" / "Interim",
        output_csv_path=PROJECT_ROOT / "Data" / "Processed" / "dataset.csv"
    )
    output_path = builder.build(reparse_raw=parsed.reparse)
    print(f"[+] Dataset hoàn thành tại: {output_path}")


SUBCOMMANDS = {
    "filegen": run_filegen,
    "workload": run_workload,
    "entropy": run_entropy,
    "dataset": run_dataset,
}


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print("Cách dùng: python Scripts/run.py <lệnh> [tham số...]")
        print("\nCác lệnh khả dụng:")
        print("  filegen   Sinh hoặc dọn dẹp file mồi DecoyDocs (--count, --cleanup, --dir)")
        print("  workload  Giả lập hành vi người dùng (--mode, --count, --delay-min, --delay-max)")
        print("  entropy   Giám định Entropy (--mode [realtime|snapshot-before|snapshot-after|compare], --session-dir, --output)")
        print("  dataset   Xây dựng dataset.csv (--reparse)")
        sys.exit(0)

    cmd = sys.argv[1].lower()
    if cmd not in SUBCOMMANDS:
        print(f"[!] Lệnh không hợp lệ: '{cmd}'. Chọn 1 trong: {list(SUBCOMMANDS.keys())}")
        sys.exit(1)

    handler = SUBCOMMANDS[cmd]
    handler(sys.argv[2:])


if __name__ == "__main__":
    main()

