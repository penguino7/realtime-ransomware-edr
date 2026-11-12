
from pathlib import Path
from typing import Set, Dict, Any, List


# Lớp quản lý toàn bộ cấu hình và hằng số vận hành của hệ thống EDR.
# Tất cả các thuộc tính đều được định nghĩa tĩnh (static attributes) để truy xuất thuận tiện.
class Config:
    # =========================================================================
    # 1. QUẢN LÝ ĐƯỜNG DẪN DỰ ÁN (PROJECT DIRECTORY LAYOUT - CCDS)
    # =========================================================================
    # Đường dẫn gốc của toàn bộ repository (trỏ từ Src/Core/ -> Src/ -> Project Root)
    PROJECT_ROOT: Path = Path(__file__).resolve().parents[2]

    # Các phân tầng dữ liệu theo chuẩn Cookiecutter Data Science
    DATA_DIR: Path = PROJECT_ROOT / "Data"
    RAW_DATA_DIR: Path = DATA_DIR / "Raw"              # Nhật ký thô bất biến (Procmon, Entropy)
    INTERIM_DATA_DIR: Path = DATA_DIR / "Interim"      # Dữ liệu IRP sạch đã được merge và chuẩn hóa
    PROCESSED_DATA_DIR: Path = DATA_DIR / "Processed"  # Dataset đặc trưng hoàn chỉnh (dataset.csv)

    # Thư mục lưu trữ trọng số mô hình đã huấn luyện (.pkl, .onnx)
    MODELS_DIR: Path = PROJECT_ROOT / "Models"

    # Thư mục lưu báo cáo kỹ thuật và biểu đồ đánh giá
    REPORTS_DIR: Path = PROJECT_ROOT / "Reports"
    FIGURES_DIR: Path = REPORTS_DIR / "Figures"

    # Tên tệp dataset đặc trưng cuối cùng phục vụ huấn luyện và kiểm thử
    DATASET_FILENAME: str = "dataset.csv"

    # =========================================================================
    # 2. CƠ CHẾ TICK & 3 TẦNG CỬA SỔ TRƯỢT (SLIDING WINDOWS & TICKS)
    # =========================================================================
    N_BASE: int = 10                       # Giới hạn bán kính thiệt hại (Blast Radius) khi phát hiện và ngăn chặn <= 10 tệp tin
    SHORT_WINDOW_SIZE: int = 10            # Đồng bộ với N_BASE để bắt ngay hành vi cục bộ trong 10 file gần nhất
    MEDIUM_WINDOW_SIZE: int = 50           # Quan sát xu hướng trung hạn và tỷ lệ duyệt thư mục mà không làm phình RAM
    EPSILON: float = 1e-6                  # Hệ số làm mượt mẫu số chống ZeroDivisionError khi delta_time = 0
    MIN_DURATION_FLOOR_SEC: float = 0.005  # Ngưỡng sàn 5ms chống bùng nổ tốc độ phi thực tế khi I/O hoàn thành chớp nhoáng

    # =========================================================================
    # 3. ĐỊNH CHUẨN ĐO LƯỜNG SHANNON ENTROPY
    # =========================================================================
    ENTROPY_SAMPLE_SIZE: int = 65536               # Đọc 64KB đầu buffer: đủ phản ánh phân bố byte mã hóa mà không gây nghẽn đĩa
    HIGH_ENTROPY_THRESHOLD: float = 7.0            # Ngưỡng thực nghiệm USENIX 2016 (UNVEIL) phân định khối mã hóa với văn bản thông thường
    BASELINE_LOW_ENTROPY_THRESHOLD: float = 6.5    # Phân loại file gốc là văn bản thuần để bắt bước nhảy trạng thái Delta H

    # =========================================================================
    # 4. THAM SỐ LÀM SẠCH VÀ GHÉP CẶP DỮ LIỆU (IRP PARSER)
    # =========================================================================
    TIMESTAMP_TOLERANCE_MS: float = 200.0  # Watchdog đo sau Procmon ~10-150ms do độ trễ I/O nên cần dung sai này

    # 22 phần mở rộng tệp tin mồi (Decoy Files) đại diện cho các nhóm tài sản số
    MONITORED_EXTENSIONS: Set[str] = {
        # Văn phòng & dữ liệu cấu trúc
        ".docx", ".xlsx", ".pdf", ".txt", ".csv", ".json",
        # Mã nguồn & kịch bản lập trình (Entropy tự nhiên thấp: 4.5 - 5.5)
        ".py", ".sql", ".html", ".xml", ".cpp",
        # Cơ sở dữ liệu & cấu hình hệ thống
        ".db", ".sqlite", ".ini", ".yaml", ".log",
        # Đồ họa hình ảnh
        ".jpg", ".png",
        # Tệp nén lưu trữ (Entropy tự nhiên cao: 7.0 - 7.5)
        ".rar", ".7z", ".zip", ".tar.gz",
    }

    # Lọc bỏ Procmon và Windows Search để tránh ô nhiễm tập dữ liệu huấn luyện
    EXCLUDED_PROCESSES: Set[str] = {
        "procmon.exe", "procmon64.exe",
        "searchprotocolhost.exe", "searchindexer.exe",
        "explorer.exe", "msmpeng.exe"
    }

    # =========================================================================
    # 5. SIÊU THAM SỐ HUẤN LUYỆN HỌC MÁY (MACHINE LEARNING)
    # =========================================================================
    RANDOM_STATE: int = 42                 # Hạt giống cố định để bảo đảm tính tái lập (Reproducibility)
    TEST_SIZE: float = 0.20                # 20% dữ liệu dùng cho tập kiểm thử độc lập
    VAL_SIZE: float = 0.20                 # 20% dữ liệu dùng cho tập kiểm chứng nội bộ (Validation)

    # Danh sách 33 đặc trưng vật lý đa tầng đã chuẩn hóa (16 Short + 9 Medium + 8 Long)
    FEATURE_NAMES: list = [
        # --- Short Window (16 features) ---
        "short_duration_sec",
        "short_write_ops_per_sec",
        "short_read_ops_per_sec",
        "short_write_bytes_per_sec",
        "short_write_ops_per_file",
        "short_write_bytes_per_file",
        "short_read_to_write_ratio",
        "short_mean_entropy",
        "short_max_entropy",
        "short_entropy_diff",
        "short_high_entropy_ratio",
        "short_rename_count",
        "short_delete_count",
        "short_ext_diversity",
        "short_new_ext_files_ratio",
        "short_inplace_rewrite_ratio",
        # --- Medium Window (9 features) ---
        "med_duration_sec",
        "med_write_ops_per_sec",
        "med_read_to_write_ratio",
        "med_mean_entropy",
        "med_high_entropy_ratio",
        "med_rename_count",
        "med_delete_count",
        "med_ext_diversity",
        "med_dir_traversal_count",
        # --- Long Window (8 features - không gồm long_total_files) ---
        "long_duration_sec",
        "long_mean_entropy",
        "long_entropy_diff",
        "long_high_entropy_ratio",
        "long_rename_ratio",
        "long_delete_ratio",
        "long_new_ext_files_ratio",
        "long_inplace_rewrite_ratio",
    ]

    # =========================================================================
    # 6. KẾT NỐI NHÂN KERNEL RING 0 (MINIFILTER IPC)
    # =========================================================================
    PORT_NAME: str = "\\RansomCollectorPort"      # Filter Communication Port dùng chung với Minifilter Driver Ring 0
    MAX_IRP_RECORDS_PER_READ: int = 1024        # Kích thước bộ đệm nhận tin ctypes IPC tránh nghẽn hàng đợi kernel

    # =========================================================================
    # 7. PHƯƠNG THỨC TIỆN ÍCH (HELPER METHODS)
    # =========================================================================
    # Nguồn chuẩn duy nhất (SSoT) định nghĩa 8 thư mục người dùng + C:\DecoyDocs, D:\DecoyDocs.
    # Dùng chung cho toàn bộ FileGenerator, WorkloadSimulator và EntropyInspector.
    @classmethod
    def get_monitored_directories(cls) -> List[Path]:
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

    # Tự động kiểm tra và khởi tạo toàn bộ các thư mục làm việc theo chuẩn CCDS.
    # Đảm bảo các thư mục luôn sẵn sàng trước khi ghi dữ liệu hoặc lưu mô hình.
    @classmethod
    def ensure_directories(cls) -> None:
        directories = [
            cls.RAW_DATA_DIR,
            cls.INTERIM_DATA_DIR,
            cls.PROCESSED_DATA_DIR,
            cls.MODELS_DIR,
            cls.REPORTS_DIR,
            cls.FIGURES_DIR,
        ]
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)

    # Trích xuất toàn bộ cấu hình dưới dạng từ điển (Dictionary) phục vụ logging.
    @classmethod
    def to_dict(cls) -> Dict[str, Any]:
        return {
            "PROJECT_ROOT": str(cls.PROJECT_ROOT),
            "N_BASE": cls.N_BASE,
            "SHORT_WINDOW_SIZE": cls.SHORT_WINDOW_SIZE,
            "MEDIUM_WINDOW_SIZE": cls.MEDIUM_WINDOW_SIZE,
            "EPSILON": cls.EPSILON,
            "ENTROPY_SAMPLE_SIZE": cls.ENTROPY_SAMPLE_SIZE,
            "HIGH_ENTROPY_THRESHOLD": cls.HIGH_ENTROPY_THRESHOLD,
            "BASELINE_LOW_ENTROPY_THRESHOLD": cls.BASELINE_LOW_ENTROPY_THRESHOLD,
            "TIMESTAMP_TOLERANCE_MS": cls.TIMESTAMP_TOLERANCE_MS,
            "RANDOM_STATE": cls.RANDOM_STATE,
            "TEST_SIZE": cls.TEST_SIZE,
            "VAL_SIZE": cls.VAL_SIZE,
            "TOTAL_FEATURES": len(cls.FEATURE_NAMES),
            "PORT_NAME": cls.PORT_NAME,
        }
