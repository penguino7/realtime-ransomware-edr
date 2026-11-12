
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


# Gói kết quả dữ liệu sau khi tách Train, Validation và Test
@dataclass
class DatasetSplits:
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


# Lớp điều phối đọc dataset và phân tách Train/Val/Test chống rò rỉ
class DataSplitter:

    # Giữ long_total_files ở metadata để đối chiếu quy mô nhưng không đưa vào tập đặc trưng huấn luyện
    METADATA_COLS: List[str] = ["sample_id", "pid", "process_name", "tick_index", "long_total_files"]
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

    # Khởi tạo bộ chia dữ liệu với đường dẫn dataset và tỷ lệ tách
    def __init__(
        self,
        dataset_path: Optional[Path] = None,
        test_size: float = Config.TEST_SIZE,
        val_size: float = Config.VAL_SIZE,
        random_state: int = Config.RANDOM_STATE
    ) -> None:
        self.dataset_path: Path = Path(
            dataset_path if dataset_path is not None
            else Config.PROCESSED_DATA_DIR / Config.DATASET_FILENAME
        )
        self.test_size: float = float(test_size)
        self.val_size: float = float(val_size)
        self.random_state: int = int(random_state)

    # Đọc file dataset.csv và kiểm tra tính toàn vẹn (không rỗng, không NaN)
    def load_dataset(self) -> pd.DataFrame:
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

    # Lấy danh sách tên cột đặc trưng cho Model A (30 cột) hoặc Model B (23 cột)
    def get_feature_names(self, df: pd.DataFrame, variant: str = "model_a") -> List[str]:
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

    # Tách lớp Benign theo từng phiên (GroupShuffleSplit theo sample_id)
    def _split_benign(
        self, benign_df: pd.DataFrame
    ) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
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

    # Tách lớp Ransomware theo phiên (>=3 phiên) hoặc theo chuỗi thời gian tick_index
    def _split_ransomware(
        self, rw_df: pd.DataFrame
    ) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
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

    # Xuất các tập train/val/test và bảng tổng hợp phiên ra file CSV để kiểm tra trực quan
    def export_splits(
        self,
        splits: DatasetSplits,
        output_dir: Optional[Path] = None
    ) -> Path:
        variant_dir = (
            "Model_A"
            if splits.variant.strip().lower() in ("model_a", "a", "full")
            else "Model_B"
        )
        target_dir = Path(
            output_dir if output_dir is not None
            else self.dataset_path.parent / "Splits" / variant_dir
        )
        target_dir.mkdir(parents=True, exist_ok=True)

        split_items = [
            ("train", splits.metadata_train, splits.X_train, splits.y_train),
            ("val", splits.metadata_val, splits.X_val, splits.y_val),
            ("test", splits.metadata_test, splits.X_test, splits.y_test),
        ]

        session_rows: List[Dict[str, Any]] = []
        for split_name, meta_df, feat_df, label_series in split_items:
            full_df = pd.concat(
                [meta_df, feat_df, label_series.rename(self.LABEL_COL)],
                axis=1,
            )
            full_df.to_csv(target_dir / f"{split_name}.csv", index=False)

            grouped = (
                full_df.groupby([self.LABEL_COL, "sample_id"], sort=True)["tick_index"]
                .agg(num_ticks="count", tick_min="min", tick_max="max")
                .reset_index()
            )
            for _, row in grouped.iterrows():
                session_rows.append(
                    {
                        "split": split_name,
                        "label": int(row[self.LABEL_COL]),
                        "sample_id": row["sample_id"],
                        "num_ticks": int(row["num_ticks"]),
                        "tick_min": int(row["tick_min"]),
                        "tick_max": int(row["tick_max"]),
                    }
                )

        pd.DataFrame(session_rows).to_csv(
            target_dir / "split_sessions.csv", index=False
        )
        print(f"[+] Đã xuất dữ liệu chia [{variant_dir}] tại: {target_dir}")
        return target_dir

    # Chạy toàn bộ quy trình chia Train/Val/Test và đóng gói thành DatasetSplits
    def split(
        self,
        variant: str = "model_a",
        save_splits: bool = True
    ) -> DatasetSplits:
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

        splits = DatasetSplits(
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

        if save_splits:
            self.export_splits(splits)

        return splits
