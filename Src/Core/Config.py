
from pathlib import Path
from typing import Set, Dict, Any


class Config:
    """
    Lớp quản lý toàn bộ cấu hình và hằng số vận hành của hệ thống EDR.
    Tất cả các thuộc tính đều được định nghĩa tĩnh (static attributes) để truy xuất thuận tiện.
    """

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
    # Số lượng tệp tin riêng biệt cơ sở để kích hoạt 1 Tick (N_base = 10 * k)
    # Đảm bảo bán kính thiệt hại tối đa (Blast Radius) khi phát hiện luôn <= 10 files
    N_BASE: int = 10

    # Kích thước cửa sổ Ngắn (Short Window): 10 file gần nhất
    SHORT_WINDOW_SIZE: int = 10

    # Kích thước tối đa của cửa sổ Vừa (Medium Window): 50 file gần nhất
    MEDIUM_WINDOW_SIZE: int = 50

    # Hệ số làm mượt mẫu số (Smoothing factor) chống lỗi ZeroDivisionError
    # Dùng khi tính tốc độ (Ops/sec hoặc Bytes/sec) khi delta_time tiến tới 0 micro-giây
    EPSILON: float = 1e-6

    # Ngưỡng sàn thời gian tối thiểu (Duration Floor) tính bằng giây (5 mili-giây)
    # Ngăn chặn hiện tượng bùng nổ tốc độ phi thực tế (Numerical Explosion) khi duration tiến tới 0 micro-giây
    MIN_DURATION_FLOOR_SEC: float = 0.005

    # =========================================================================
    # 3. ĐỊNH CHUẨN ĐO LƯỜNG SHANNON ENTROPY
    # =========================================================================
    # Kích thước khối byte đầu tiên được đọc để tính toán Entropy (64 KB)
    ENTROPY_SAMPLE_SIZE: int = 65536

    # Ngưỡng đánh dấu khối dữ liệu có độ hỗn loạn cao (nguy cơ mã hóa)
    # Theo chuẩn thực nghiệm các bài báo UNVEIL (USENIX 2016) và ShieldFS (CCS 2016)
    HIGH_ENTROPY_THRESHOLD: float = 7.0

    # Ngưỡng xác định file gốc ban đầu là tài liệu văn bản / chưa nén
    # Dùng để phát hiện bước nhảy biến thiên Delta H chuyển dịch trạng thái (Transition)
    BASELINE_LOW_ENTROPY_THRESHOLD: float = 6.5

    # =========================================================================
    # 4. THAM SỐ LÀM SẠCH VÀ GHÉP CẶP DỮ LIỆU (IRP PARSER)
    # =========================================================================
    # Độ lệch thời gian tối đa cho phép giữa log Procmon và log Realtime Entropy (mili-giây)
    TIMESTAMP_TOLERANCE_MS: float = 200.0

    # Tập hợp các phần mở rộng tệp tin mồi (Decoy Files) được hệ thống giám sát
    MONITORED_EXTENSIONS: Set[str] = {
        ".docx", ".xlsx", ".pdf", ".txt", ".csv",
        ".json", ".jpg", ".png", ".rar", ".7z", ".zip"
    }

    # Danh sách tiến trình hệ thống hoặc công cụ đo lường cần lọc bỏ khỏi tập train
    EXCLUDED_PROCESSES: Set[str] = {
        "procmon.exe", "procmon64.exe",
        "searchprotocolhost.exe", "searchindexer.exe",
        "explorer.exe", "msmpeng.exe"
    }

    # =========================================================================
    # 5. SIÊU THAM SỐ HUẤN LUYỆN HỌC MÁY (MACHINE LEARNING)
    # =========================================================================
    # Hạt giống ngẫu nhiên đảm bảo tính tái lập (Reproducibility)
    RANDOM_STATE: int = 42

    # Tỷ lệ phân chia tập kiểm thử (Test set ratio)
    TEST_SIZE: float = 0.20

    # Tỷ lệ phân chia tập kiểm tra chéo nội bộ (Validation set ratio)
    VAL_SIZE: float = 0.20

    # Ngưỡng xác suất tin cậy của mô hình (Confidence Threshold >= 95%)
    # Khi P(Ransomware) >= ngưỡng này, Responder mới được phép tiêu diệt tiến trình
    MALWARE_CONFIDENCE_THRESHOLD: float = 0.95

    # Danh sách tên 27 đặc trưng vật lý chuẩn mực của mô hình
    FEATURE_NAMES: list = [
        # --- Short Window (10 features) ---
        "short_duration_sec",
        "short_write_ops_per_sec",
        "short_read_ops_per_sec",
        "short_write_bytes_per_sec",
        "short_mean_entropy",
        "short_max_entropy",
        "short_entropy_diff",
        "short_rename_count",
        "short_delete_count",
        "short_ext_diversity",
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
        # --- Long Window (8 features) ---
        "long_total_files",
        "long_duration_sec",
        "long_mean_entropy",
        "long_rename_count",
        "long_delete_count",
        "long_new_ext_count",
        "long_dir_traversal_count",
        "long_inplace_rewrite_ratio",
    ]

    # =========================================================================
    # 6. KẾT NỐI NHÂN KERNEL RING 0 (MINIFILTER IPC)
    # =========================================================================
    # Tên cổng kết nối Filter Communication Port của Minifilter Driver
    PORT_NAME: str = "\\RansomCollectorPort"

    # Số lượng bản ghi IRP nhị phân tối đa đọc từ kernel trong một lượt nhận tin
    MAX_IRP_RECORDS_PER_READ: int = 1024

    # =========================================================================
    # 7. PHƯƠNG THỨC TIỆN ÍCH (HELPER METHODS)
    # =========================================================================
    @classmethod
    def ensure_directories(cls) -> None:
        """
        Tự động kiểm tra và khởi tạo toàn bộ các thư mục làm việc theo chuẩn CCDS.
        Đảm bảo các thư mục luôn sẵn sàng trước khi ghi dữ liệu hoặc lưu mô hình.
        """
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

    @classmethod
    def to_dict(cls) -> Dict[str, Any]:
        """
        Trích xuất toàn bộ cấu hình dưới dạng từ điển (Dictionary) phục vụ logging.
        """
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
            "MALWARE_CONFIDENCE_THRESHOLD": cls.MALWARE_CONFIDENCE_THRESHOLD,
            "TOTAL_FEATURES": len(cls.FEATURE_NAMES),
            "PORT_NAME": cls.PORT_NAME,
        }
