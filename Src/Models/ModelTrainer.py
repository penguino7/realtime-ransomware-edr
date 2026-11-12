
import itertools
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import confusion_matrix, f1_score, precision_score, recall_score, roc_auc_score

try:
    from ..Core.Config import Config
    from .DataSplitter import DataSplitter, DatasetSplits
except (ImportError, ValueError):
    from Src.Core.Config import Config
    from Src.Models.DataSplitter import DataSplitter, DatasetSplits


# Gói dữ liệu lưu trữ mô hình đã huấn luyện và siêu dữ liệu đi kèm
@dataclass
class TrainedModelBundle:
    model: Any
    model_name: str
    variant: str
    feature_names: List[str]
    best_params: Dict[str, Any]
    val_metrics: Dict[str, float]
    optimal_threshold: float
    model_path: Optional[Path] = None


# Lớp điều phối quá trình huấn luyện, tinh chỉnh siêu tham số và lưu trữ mô hình EDR
class ModelTrainer:

    # Khởi tạo trainer với thư mục lưu model, bộ chia dữ liệu, seed và trần FPR mục tiêu
    def __init__(
        self,
        models_dir: Optional[Path] = None,
        splitter: Optional[DataSplitter] = None,
        random_state: int = Config.RANDOM_STATE,
        max_target_fpr: float = 0.001
    ) -> None:
        self.models_dir: Path = Path(models_dir if models_dir is not None else Config.MODELS_DIR)
        self.models_dir.mkdir(parents=True, exist_ok=True)
        self.splitter: DataSplitter = splitter if splitter is not None else DataSplitter()
        self.random_state: int = int(random_state)
        self.max_target_fpr: float = float(max_target_fpr)

    # Tạo toàn bộ 72 tổ hợp siêu tham số Random Forest để thử nghiệm
    @staticmethod
    def _generate_rf_param_grid() -> List[Dict[str, Any]]:
        param_space = {
            "n_estimators": [50, 100, 150],
            "max_depth": [6, 10, 14, None],
            "min_samples_leaf": [1, 2, 4],
            "class_weight": ["balanced", None],
        }
        keys = list(param_space.keys())
        combinations = list(itertools.product(*(param_space[k] for k in keys)))
        return [dict(zip(keys, values)) for values in combinations]

    # Tính các chỉ số F1, Precision, Recall và FPR tại một ngưỡng cắt cụ thể
    @staticmethod
    def _compute_threshold_metrics(
        y_true: Any,
        y_prob: np.ndarray,
        threshold: float
    ) -> Dict[str, float]:
        y_arr = np.asarray(y_true)
        y_pred = (np.asarray(y_prob, dtype=float) >= threshold).astype(int)

        tn, fp, fn, tp = confusion_matrix(y_arr, y_pred, labels=[0, 1]).ravel()
        fpr = float(fp / (fp + tn)) if (fp + tn) > 0 else 0.0

        return {
            "f1": float(f1_score(y_arr, y_pred, zero_division=0)),
            "precision": float(precision_score(y_arr, y_pred, zero_division=0)),
            "recall": float(recall_score(y_arr, y_pred, zero_division=0)),
            "fpr": fpr,
        }

    # Tìm ngưỡng quyết định tối ưu trên tập Validation cho một bộ xác suất dự đoán
    @staticmethod
    def find_optimal_threshold(
        y_val: Any,
        y_val_prob: np.ndarray,
        max_target_fpr: float = 0.001
    ) -> float:
        y_true = np.asarray(y_val)
        probs = np.asarray(y_val_prob, dtype=float)

        benign_probs = probs[y_true == 0]
        rw_probs = probs[y_true == 1]

        # Nếu 2 lớp tách biệt hoàn toàn trên Validation: chọn trung điểm để tối đa hóa biên an toàn
        if len(benign_probs) > 0 and len(rw_probs) > 0:
            max_benign = float(np.max(benign_probs))
            min_rw = float(np.min(rw_probs))
            if max_benign < min_rw:
                return round((max_benign + min_rw) / 2.0, 4)

        # Khi 2 lớp có vùng giao nhau: quét lưới ngưỡng ưu tiên thỏa mãn FPR mục tiêu -> F1 -> Recall
        candidates = np.unique(np.concatenate([np.round(probs, 4), np.linspace(0.1, 0.9, 81)]))
        best_score: Optional[Tuple[int, float, float, float, float]] = None
        best_threshold = 0.5

        for thr in candidates:
            m = ModelTrainer._compute_threshold_metrics(y_true, probs, float(thr))
            meets_fpr = 1 if m["fpr"] <= max_target_fpr else 0
            score = (
                meets_fpr,
                round(m["f1"], 6),
                round(m["recall"], 6),
                round(-m["fpr"], 6),
                -abs(float(thr) - 0.5),
            )
            if best_score is None or score > best_score:
                best_score = score
                best_threshold = float(thr)

        return round(best_threshold, 4)

    # Chấm điểm một mô hình tại ngưỡng tối ưu trên tập Validation
    def _evaluate_validation(
        self,
        model: Any,
        X_val: pd.DataFrame,
        y_val: pd.Series
    ) -> Dict[str, float]:
        y_prob = model.predict_proba(X_val)[:, 1]
        opt_threshold = self.find_optimal_threshold(y_val, y_prob, self.max_target_fpr)

        metrics = self._compute_threshold_metrics(y_val, y_prob, opt_threshold)
        metrics["roc_auc"] = float(roc_auc_score(y_val, y_prob)) if y_val.nunique() > 1 else 0.0
        metrics["optimal_threshold"] = float(opt_threshold)
        return metrics

    # Tạo khóa so sánh để chọn mô hình tốt nhất (ROC-AUC -> F1 -> -FPR -> gọn nhẹ)
    @staticmethod
    def _compute_candidate_rank(
        metrics: Dict[str, float],
        params: Dict[str, Any]
    ) -> Tuple[float, float, float, int]:
        depth_penalty = 100 if params["max_depth"] is None else int(params["max_depth"])
        complexity_penalty = depth_penalty * 1000 + int(params["n_estimators"])
        return (
            round(metrics["roc_auc"], 6),
            round(metrics["f1"], 6),
            round(-metrics["fpr"], 6),
            -complexity_penalty,
        )

    # Khởi tạo và huấn luyện 1 mô hình Random Forest với bộ tham số truyền vào
    def _fit_rf_candidate(
        self,
        params: Dict[str, Any],
        X_train: pd.DataFrame,
        y_train: pd.Series
    ) -> RandomForestClassifier:
        
        clf = RandomForestClassifier(
            n_estimators=params["n_estimators"],
            max_depth=params["max_depth"],
            min_samples_leaf=params["min_samples_leaf"],
            class_weight=params["class_weight"],
            random_state=self.random_state,
            n_jobs=-1,
        )
        clf.fit(X_train, y_train)
        return clf

    # Huấn luyện và tinh chỉnh Random Forest cho 1 biến thể (Model A hoặc Model B)
    def train_random_forest(self, splits: DatasetSplits) -> TrainedModelBundle:
        candidates = self._generate_rf_param_grid()
        best_rank: Optional[Tuple[float, float, float, int]] = None
        best_model: Optional[RandomForestClassifier] = None
        best_params: Dict[str, Any] = {}
        best_metrics: Dict[str, float] = {}

        print(f"[*] Đang tinh chỉnh Random Forest [{splits.variant}] qua {len(candidates)} cấu hình trên tập Validation...")
        for params in candidates:
            model = self._fit_rf_candidate(params, splits.X_train, splits.y_train)
            val_metrics = self._evaluate_validation(model, splits.X_val, splits.y_val)
            rank = self._compute_candidate_rank(val_metrics, params)

            if best_rank is None or rank > best_rank:
                best_rank = rank
                best_model = model
                best_params = params
                best_metrics = val_metrics

        bundle = TrainedModelBundle(
            model=best_model,
            model_name="random_forest",
            variant=splits.variant,
            feature_names=list(splits.feature_names),
            best_params=best_params,
            val_metrics=best_metrics,
            optimal_threshold=float(best_metrics["optimal_threshold"]),
        )
        bundle.model_path = self.save_model(bundle)

        print(
            f"[+] Hoàn tất huấn luyện Random Forest [{splits.variant}] | "
            f"Best Params: {best_params} | Thr={bundle.optimal_threshold:.4f} | "
            f"Val F1={best_metrics['f1']:.4f}, AUC={best_metrics['roc_auc']:.4f}, FPR={best_metrics['fpr']:.4f}"
        )
        return bundle

    # Đóng gói mô hình, danh sách feature, ngưỡng tối ưu và metadata ra file .joblib
    def save_model(self, bundle: TrainedModelBundle) -> Path:
        filename = f"rf_{bundle.variant.lower()}.joblib"
        out_path = self.models_dir / filename

        payload = {
            "model": bundle.model,
            "model_name": bundle.model_name,
            "variant": bundle.variant,
            "feature_names": bundle.feature_names,
            "best_params": bundle.best_params,
            "val_metrics": bundle.val_metrics,
            "optimal_threshold": bundle.optimal_threshold,
        }
        joblib.dump(payload, out_path, compress=3)
        print(f"[+] Đã lưu trọng số mô hình tại: {out_path}")
        return out_path

    # Nạp lại gói mô hình đã lưu từ file .joblib
    @staticmethod
    def load_model(model_path: Union[str, Path]) -> Dict[str, Any]:
        path = Path(model_path)
        if not path.exists():
            raise FileNotFoundError(f"Không tìm thấy tệp mô hình tại: {path}")
        return joblib.load(path)

    # Chạy huấn luyện đầy đủ cho cả hai biến thể Model A (30 features) và Model B (23 features)
    def train_both_variants(self) -> Dict[str, Tuple[TrainedModelBundle, DatasetSplits]]:
        results: Dict[str, Tuple[TrainedModelBundle, DatasetSplits]] = {}
        for variant in ("model_a", "model_b"):
            splits = self.splitter.split(variant=variant)
            splits.print_summary()
            bundle = self.train_random_forest(splits=splits)
            results[variant] = (bundle, splits)

        return results
