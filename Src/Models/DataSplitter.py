"""
Module DataSplitter: Tiền xử lý và phân tách tập dữ liệu huấn luyện/kiểm thử.
- Đọc và kiểm định tính toàn vẹn của Data/Processed/dataset.csv.
- Hỗ trợ kiến trúc song mô hình (Dual-Model Paradigm):
    + Model A (Full, Time-Aware): 30 đặc trưng vật lý đa tầng.
    + Model B (Clock-Free / Anti-Sleep-Evasion): 23 đặc trưng độc lập thời gian.
- Áp dụng chiến lược phân tách chống rò rỉ dữ liệu (Anti-Leakage Protocol):
    + Lớp Benign: GroupShuffleSplit theo sample_id (cách ly hoàn toàn các phiên giữa Train, Val, Test).
    + Lớp Ransomware: Phân tách theo chuỗi thời gian/mốc tick (Time-series Sequence Split)
      hoặc GroupShuffleSplit khi có nhiều phiên mã độc.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Any, Set
import pandas as pd
import numpy as np
from sklearn.model_selection import GroupShuffleSplit
from sklearn.utils import shuffle

try:
    from ..Core.Config import Config
except (ImportError, ValueError):
    from Src.Core.Config import Config


@dataclass
class DatasetSplits:
    """
    Cấu trúc dữ liệu đóng gói kết quả phân tách tập dữ liệu huấn luyện, kiểm chứng và kiểm thử.
    """
    X_train: pd.DataFrame
    y_train: pd.Series
    X_val: pd.DataFrame
    y_val: pd.Series
    X_test: pd.DataFrame
    y_test: pd.Series
    feature_names: List[str]
    variant: str
    metadata_train: pd.DataFrame
    metadata_val: pd.DataFrame
    metadata_test: pd.DataFrame

    def get_summary(self) -> Dict[str, Any]:
        """Trích xuất bảng thống kê tóm tắt số lượng mẫu và phân bố nhãn."""
        return {
            "variant": self.variant,
            "num_features": len(self.feature_names),
            "train": {
                "total": len(self.X_train),
                "benign": int((self.y_train == 0).sum()),
                "ransomware": int((self.y_train == 1).sum()),
                "pos_ratio": round(float(self.y_train.mean()) * 100, 2),
            },
            "val": {
                "total": len(self.X_val),
                "benign": int((self.y_val == 0).sum()),
                "ransomware": int((self.y_val == 1).sum()),
                "pos_ratio": round(float(self.y_val.mean()) * 100, 2),
            },
            "test": {
                "total": len(self.X_test),
                "benign": int((self.y_test == 0).sum()),
                "ransomware": int((self.y_test == 1).sum()),
                "pos_ratio": round(float(self.y_test.mean()) * 100, 2),
            },
        }

    def print_summary(self) -> None:
        """In báo cáo phân tách dữ liệu trực quan ra console."""
        s = self.get_summary()
        print(f"\n=======================================================")
        print(f" DATA SPLIT SUMMARY [{s['variant'].upper()}] - {s['num_features']} Features")
        print(f"=======================================================")
        for split_name in ["train", "val", "test"]:
            info = s[split_name]
            print(f"  * {split_name.upper():5s}: {info['total']:4d} mẫu "
                  f"(Benign: {info['benign']:3d}, Ransomware: {info['ransomware']:3d} "
                  f"| Tỷ lệ mã độc: {info['pos_ratio']}%)")
        print(f"=======================================================\n")


class DataSplitter:
    """
    Lớp điều phối tiền xử lý và phân tách dữ liệu chống rò rỉ (Data Leakage Protection).
    """

    METADATA_COLS: List[str] = ["sample_id", "pid", "process_name", "tick_index"]
    LABEL_COL: str = "label"

    # 7 đặc trưng phụ thuộc thời gian / tốc độ cần loại bỏ đối với Model B (Clock-Free)
    TIME_DEPENDENT_FEATURES: Set[str] = {
        "short_duration_sec",
        "short_write_ops_per_sec",
        "short_read_ops_per_sec",
        "short_write_bytes_per_sec",
        "med_duration_sec",
        "med_write_ops_per_sec",
        "long_duration_sec",
    }

    def __init__(
        self,
        dataset_path: Optional[Path] = None,
        test_size: float = Config.TEST_SIZE,
        val_size: float = Config.VAL_SIZE,
        random_state: int = Config.RANDOM_STATE
    ) -> None:
        """
        Khởi tạo DataSplitter với đường dẫn dataset và siêu tham số phân tách.
        """
        self.dataset_path: Path = Path(
            dataset_path if dataset_path is not None
            else Config.PROCESSED_DATA_DIR / Config.DATASET_FILENAME
        )
        self.test_size: float = float(test_size)
        self.val_size: float = float(val_size)
        self.random_state: int = int(random_state)

    def load_dataset(self) -> pd.DataFrame:
        """
        Đọc và kiểm định tính toàn vẹn của tệp dataset.csv.
        """
        if not self.dataset_path.exists():
            raise FileNotFoundError(
                f"Không tìm thấy tập dữ liệu tại: {self.dataset_path}. "
                f"Vui lòng chạy 'python Scripts/Run.py dataset --reparse' trước."
            )

        df = pd.read_csv(self.dataset_path)

        # Kiểm tra tính toàn vẹn cơ bản
        if df.empty:
            raise ValueError(f"Tập dữ liệu {self.dataset_path} đang rỗng!")

        missing_count = int(df.isnull().sum().sum())
        if missing_count > 0:
            raise ValueError(
                f"Tập dữ liệu chứa {missing_count} giá trị khuyết thiếu (NaN/Null). "
                f"Vui lòng kiểm tra lại pipeline bóc tách IRP!"
            )

        return df

    def get_feature_names(self, df: pd.DataFrame, variant: str = "model_a") -> List[str]:
        """
        Trích xuất danh sách tên cột đặc trưng theo biến thể mô hình:
        - "model_a": 30 đặc trưng vật lý đầy đủ (Time-Aware).
        - "model_b": 23 đặc trưng độc lập thời gian (Clock-Free / Anti-Sleep-Evasion).
        """
        excluded = set(self.METADATA_COLS) | {self.LABEL_COL}
        all_features = [col for col in df.columns if col not in excluded]

        variant_clean = variant.strip().lower()
        if variant_clean in ("model_a", "a", "full"):
            return all_features
        elif variant_clean in ("model_b", "b", "clock_free", "time_invariant"):
            clock_free_features = [
                col for col in all_features if col not in self.TIME_DEPENDENT_FEATURES
            ]
            return clock_free_features
        else:
            raise ValueError(
                f"Biến thể '{variant}' không hợp lệ! Chỉ chấp nhận: 'model_a' hoặc 'model_b'."
            )

    def _split_benign(
        self, benign_df: pd.DataFrame
    ) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """
        Phân tách lớp Benign theo nhóm phiên (GroupShuffleSplit theo sample_id).
        Đảm bảo 100% không rò rỉ dữ liệu: các tick của cùng 1 phiên lành tính
        chỉ được nằm ở đúng một tập duy nhất (Train, Val hoặc Test).
        """
        num_sessions = benign_df["sample_id"].nunique()
        if num_sessions < 3:
            raise ValueError(
                f"Số lượng phiên Benign ({num_sessions}) không đủ để chia 3 tập Train/Val/Test!"
            )

        # 1. Tách Test set (~20%)
        gss_test = GroupShuffleSplit(
            n_splits=1, test_size=self.test_size, random_state=self.random_state
        )
        train_val_idx, test_idx = next(
            gss_test.split(benign_df, groups=benign_df["sample_id"])
        )
        b_train_val = benign_df.iloc[train_val_idx].copy()
        b_test = benign_df.iloc[test_idx].copy()

        # 2. Tách Validation set (~20% của tổng thể) từ tập Train_Val
        val_relative_size = self.val_size / (1.0 - self.test_size)
        gss_val = GroupShuffleSplit(
            n_splits=1, test_size=val_relative_size, random_state=self.random_state
        )
        train_idx, val_idx = next(
            gss_val.split(b_train_val, groups=b_train_val["sample_id"])
        )
        b_train = b_train_val.iloc[train_idx].copy()
        b_val = b_train_val.iloc[val_idx].copy()

        return b_train, b_val, b_test

    def _split_ransomware(
        self, rw_df: pd.DataFrame
    ) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """
        Phân tách lớp Ransomware chống rò rỉ:
        - Nếu có >= 3 phiên mã độc: Dùng GroupShuffleSplit theo sample_id.
        - Nếu chỉ có 1-2 phiên mã độc (ví dụ hiện tại có LockBit 3.0):
          Dùng chiến lược phân tách chuỗi thời gian (Time-series / Sequence Split theo tick_index).
          Mô hình học từ các tick sớm và kiểm thử mù trên các tick muộn.
        """
        num_rw_sessions = rw_df["sample_id"].nunique()

        if num_rw_sessions >= 3:
            # Khi đã có đủ nhiều phiên ransomware khác nhau (WannaCry, LockBit, Babuk...)
            gss_test = GroupShuffleSplit(
                n_splits=1, test_size=self.test_size, random_state=self.random_state
            )
            train_val_idx, test_idx = next(
                gss_test.split(rw_df, groups=rw_df["sample_id"])
            )
            rw_train_val = rw_df.iloc[train_val_idx].copy()
            rw_test = rw_df.iloc[test_idx].copy()

            val_relative_size = self.val_size / (1.0 - self.test_size)
            gss_val = GroupShuffleSplit(
                n_splits=1, test_size=val_relative_size, random_state=self.random_state
            )
            train_idx, val_idx = next(
                gss_val.split(rw_train_val, groups=rw_train_val["sample_id"])
            )
            rw_train = rw_train_val.iloc[train_idx].copy()
            rw_val = rw_train_val.iloc[val_idx].copy()
        else:
            # Trường hợp thực nghiệm ban đầu (1 phiên mã độc quy mô lớn như LockBit 3.0)
            # Sắp xếp nghiêm ngặt theo tick_index để mô phỏng diễn biến tấn công theo thời gian thực
            rw_sorted = rw_df.sort_values("tick_index").reset_index(drop=True)
            n_total = len(rw_sorted)
            n_test = max(1, int(n_total * self.test_size))
            n_val = max(1, int(n_total * self.val_size))
            n_train = n_total - n_test - n_val

            rw_train = rw_sorted.iloc[:n_train].copy()
            rw_val = rw_sorted.iloc[n_train:n_train + n_val].copy()
            rw_test = rw_sorted.iloc[n_train + n_val:].copy()

        return rw_train, rw_val, rw_test

    def split(self, variant: str = "model_a") -> DatasetSplits:
        """
        Quy trình điều phối chính:
        1. Nạp và kiểm định dataset.
        2. Xác định tập đặc trưng theo biến thể ('model_a' hoặc 'model_b').
        3. Phân tách Benign (Group-aware) và Ransomware (Time-aware) độc lập.
        4. Ghép cặp, xáo trộn nội bộ (shuffle) và đóng gói đối tượng DatasetSplits.
        """
        df = self.load_dataset()
        feature_names = self.get_feature_names(df, variant=variant)

        benign_df = df[df[self.LABEL_COL] == 0].copy()
        rw_df = df[df[self.LABEL_COL] == 1].copy()

        if benign_df.empty or rw_df.empty:
            raise ValueError(
                f"Tập dữ liệu phải chứa cả 2 lớp Benign và Ransomware! "
                f"Hiện có: Benign={len(benign_df)}, Ransomware={len(rw_df)}"
            )

        # Phân tách độc lập 2 lớp chống rò rỉ dữ liệu
        b_train, b_val, b_test = self._split_benign(benign_df)
        rw_train, rw_val, rw_test = self._split_ransomware(rw_df)

        # Ghép cặp tương ứng
        train_df = pd.concat([b_train, rw_train], ignore_index=True)
        val_df = pd.concat([b_val, rw_val], ignore_index=True)
        test_df = pd.concat([b_test, rw_test], ignore_index=True)

        # Xáo trộn nội bộ trong từng tập để thuật toán không học theo thứ tự nối
        train_df = shuffle(train_df, random_state=self.random_state).reset_index(drop=True)
        val_df = shuffle(val_df, random_state=self.random_state).reset_index(drop=True)
        test_df = shuffle(test_df, random_state=self.random_state).reset_index(drop=True)

        return DatasetSplits(
            X_train=train_df[feature_names].copy(),
            y_train=train_df[self.LABEL_COL].copy(),
            X_val=val_df[feature_names].copy(),
            y_val=val_df[self.LABEL_COL].copy(),
            X_test=test_df[feature_names].copy(),
            y_test=test_df[self.LABEL_COL].copy(),
            feature_names=feature_names,
            variant=variant,
            metadata_train=train_df[self.METADATA_COLS].copy(),
            metadata_val=val_df[self.METADATA_COLS].copy(),
            metadata_test=test_df[self.METADATA_COLS].copy(),
        )
