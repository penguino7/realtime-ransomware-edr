import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "mpl_cache"))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    confusion_matrix,
    precision_recall_curve,
    roc_auc_score,
    roc_curve,
)

try:
    from ..Core.Config import Config
    from .DataSplitter import DataSplitter, DatasetSplits
    from .ModelTrainer import ModelTrainer
except (ImportError, ValueError):
    from Src.Core.Config import Config
    from Src.Models.DataSplitter import DataSplitter, DatasetSplits
    from Src.Models.ModelTrainer import ModelTrainer


# Gói kết quả đánh giá mô hình trên tập Test độc lập
@dataclass
class EvaluationResult:
    variant: str
    model_name: str
    num_features: int
    threshold: float
    metrics: Dict[str, float]
    y_true: np.ndarray
    y_prob: np.ndarray
    y_pred: np.ndarray
    feature_importances: pd.DataFrame
    misclassified: pd.DataFrame


# Lớp đánh giá mô hình đã huấn luyện, xuất báo cáo so sánh và vẽ biểu đồ
class ModelEvaluator:

    # Khởi tạo thư mục lưu báo cáo và biểu đồ đánh giá
    def __init__(
        self,
        reports_dir: Optional[Path] = None,
        figures_dir: Optional[Path] = None,
    ) -> None:
        self.reports_dir: Path = Path(reports_dir if reports_dir is not None else Config.REPORTS_DIR)
        self.figures_dir: Path = Path(figures_dir if figures_dir is not None else Config.FIGURES_DIR)
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        self.figures_dir.mkdir(parents=True, exist_ok=True)

    # Tính đầy đủ các chỉ số phân loại nhị phân tại ngưỡng quyết định cho trước
    @staticmethod
    def compute_binary_metrics(
        y_true: Any,
        y_prob: np.ndarray,
        threshold: float,
    ) -> Dict[str, float]:
        y_arr = np.asarray(y_true)
        probs = np.asarray(y_prob, dtype=float)
        y_pred = (probs >= threshold).astype(int)

        base = ModelTrainer._compute_threshold_metrics(y_arr, probs, threshold)
        tn, fp, fn, tp = confusion_matrix(y_arr, y_pred, labels=[0, 1]).ravel()
        has_two_classes = len(np.unique(y_arr)) > 1

        return {
            "accuracy": float(accuracy_score(y_arr, y_pred)),
            "precision": base["precision"],
            "recall": base["recall"],
            "f1": base["f1"],
            "fpr": base["fpr"],
            "roc_auc": float(roc_auc_score(y_arr, probs)) if has_two_classes else 0.0,
            "pr_auc": float(average_precision_score(y_arr, probs)) if has_two_classes else 0.0,
            "tn": int(tn),
            "fp": int(fp),
            "fn": int(fn),
            "tp": int(tp),
        }

    # Trích xuất danh sách các mẫu dự đoán sai (FP và FN) kèm metadata để phân tích lỗi
    @staticmethod
    def extract_misclassified_samples(
        metadata_test: pd.DataFrame,
        y_true: Any,
        y_prob: np.ndarray,
        threshold: float,
    ) -> pd.DataFrame:
        y_arr = np.asarray(y_true)
        probs = np.asarray(y_prob, dtype=float)
        y_pred = (probs >= threshold).astype(int)

        df = metadata_test.reset_index(drop=True).copy()
        df["y_true"] = y_arr
        df["y_pred"] = y_pred
        df["y_prob"] = np.round(probs, 4)

        mask = df["y_true"] != df["y_pred"]
        errors = df.loc[mask].copy()
        if errors.empty:
            return errors

        errors["error_type"] = np.where(errors["y_pred"] == 1, "FP", "FN")
        return errors.sort_values(by=["error_type", "y_prob"], ascending=[True, False]).reset_index(drop=True)

    # Đánh giá một tệp mô hình .joblib trên tập Test tương ứng
    def evaluate_variant(self, model_path: Path, splits: DatasetSplits) -> EvaluationResult:
        payload = ModelTrainer.load_model(model_path)
        model = payload["model"]
        feature_names: List[str] = list(payload["feature_names"])

        X_test = splits.X_test[feature_names]
        y_true = np.asarray(splits.y_test)
        y_prob = model.predict_proba(X_test)[:, 1]

        if "optimal_threshold" in payload:
            threshold = float(payload["optimal_threshold"])
        else:
            threshold = ModelTrainer.find_optimal_threshold(splits.y_val, model.predict_proba(splits.X_val[feature_names])[:, 1])

        y_pred = (y_prob >= threshold).astype(int)
        metrics = self.compute_binary_metrics(y_true, y_prob, threshold)
        misclassified = self.extract_misclassified_samples(splits.metadata_test, y_true, y_prob, threshold)

        importances = getattr(model, "feature_importances_", np.zeros(len(feature_names)))
        fi_df = (
            pd.DataFrame({"feature": feature_names, "importance": importances})
            .sort_values(by="importance", ascending=False)
            .reset_index(drop=True)
        )

        return EvaluationResult(
            variant=splits.variant,
            model_name=str(payload.get("model_name", "random_forest")),
            num_features=len(feature_names),
            threshold=threshold,
            metrics=metrics,
            y_true=y_true,
            y_prob=y_prob,
            y_pred=y_pred,
            feature_importances=fi_df,
            misclassified=misclassified,
        )

    # Vẽ ma trận nhầm lẫn (Confusion Matrix) so sánh các biến thể
    def plot_confusion_matrices(self, results: Dict[str, EvaluationResult]) -> Path:
        variants = list(results.keys())
        fig, axes = plt.subplots(1, len(variants), figsize=(6 * len(variants), 5))
        if len(variants) == 1:
            axes = [axes]

        for ax, variant in zip(axes, variants):
            res = results[variant]
            cm = confusion_matrix(res.y_true, res.y_pred, labels=[0, 1])
            sns.heatmap(
                cm,
                annot=True,
                fmt="d",
                cmap="Blues",
                annot_kws={"size": 13, "weight": "bold"},
                xticklabels=["Benign (0)", "Ransomware (1)"],
                yticklabels=["Benign (0)", "Ransomware (1)"],
                ax=ax,
            )
            ax.set_title(f"{variant.upper()} ({res.num_features} features)\nThr={res.threshold:.4f} | F1={res.metrics['f1']:.4f}")
            ax.set_xlabel("Predicted Label")
            ax.set_ylabel("True Label")

        fig.tight_layout()
        out_path = self.figures_dir / "confusion_matrices.png"
        fig.savefig(out_path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        return out_path

    # Vẽ đường cong ROC và Precision-Recall so sánh Model A và Model B
    def plot_roc_and_pr_curves(self, results: Dict[str, EvaluationResult]) -> Path:
        fig, (ax_roc, ax_pr) = plt.subplots(1, 2, figsize=(12, 5))

        for variant, res in results.items():
            fpr_vals, tpr_vals, _ = roc_curve(res.y_true, res.y_prob)
            prec_vals, rec_vals, _ = precision_recall_curve(res.y_true, res.y_prob)

            ax_roc.plot(fpr_vals, tpr_vals, linewidth=2, label=f"{variant.upper()} (AUC={res.metrics['roc_auc']:.4f})")
            ax_pr.plot(rec_vals, prec_vals, linewidth=2, label=f"{variant.upper()} (AP={res.metrics['pr_auc']:.4f})")

        ax_roc.plot([0, 1], [0, 1], linestyle="--", color="gray", linewidth=1)
        ax_roc.set_title("ROC Curve (Test Set)")
        ax_roc.set_xlabel("False Positive Rate (FPR)")
        ax_roc.set_ylabel("True Positive Rate (Recall)")
        ax_roc.legend(loc="lower right")
        ax_roc.grid(alpha=0.3)

        ax_pr.set_title("Precision-Recall Curve (Test Set)")
        ax_pr.set_xlabel("Recall")
        ax_pr.set_ylabel("Precision")
        ax_pr.legend(loc="lower left")
        ax_pr.grid(alpha=0.3)

        fig.tight_layout()
        out_path = self.figures_dir / "roc_pr_curves.png"
        fig.savefig(out_path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        return out_path

    # Vẽ biểu đồ Top-N đặc trưng quan trọng nhất của từng biến thể
    def plot_feature_importances(self, results: Dict[str, EvaluationResult], top_n: int = 12) -> Path:
        variants = list(results.keys())
        fig, axes = plt.subplots(1, len(variants), figsize=(7 * len(variants), 6))
        if len(variants) == 1:
            axes = [axes]

        for ax, variant in zip(axes, variants):
            res = results[variant]
            top_df = res.feature_importances.head(top_n)
            sns.barplot(data=top_df, x="importance", y="feature", color="#2b6cb0", ax=ax)
            ax.set_title(f"Top {len(top_df)} Feature Importances - {variant.upper()}")
            ax.set_xlabel("Importance")
            ax.set_ylabel("")
            ax.grid(axis="x", alpha=0.3)

        fig.tight_layout()
        out_path = self.figures_dir / "feature_importance_comparison.png"
        fig.savefig(out_path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        return out_path

    # Xuất bảng so sánh CSV vào thư mục Reports/
    def save_comparison_report(self, results: Dict[str, EvaluationResult]) -> Path:
        rows: List[Dict[str, Any]] = []
        for variant, res in results.items():
            m = res.metrics
            rows.append({
                "variant": variant,
                "model_name": res.model_name,
                "num_features": res.num_features,
                "threshold": round(res.threshold, 4),
                "accuracy": round(m["accuracy"], 4),
                "precision": round(m["precision"], 4),
                "recall": round(m["recall"], 4),
                "f1": round(m["f1"], 4),
                "roc_auc": round(m["roc_auc"], 4),
                "pr_auc": round(m["pr_auc"], 4),
                "fpr": round(m["fpr"], 4),
                "tn": m["tn"],
                "fp": m["fp"],
                "fn": m["fn"],
                "tp": m["tp"],
            })

        csv_path = self.reports_dir / "model_comparison.csv"
        pd.DataFrame(rows).to_csv(csv_path, index=False, encoding="utf-8-sig")
        return csv_path

    # Chạy đánh giá toàn bộ các mô hình đã lưu (.joblib) và sinh biểu đồ + báo cáo
    def evaluate_saved_models(
        self,
        models_dir: Optional[Path] = None,
        splitter: Optional[DataSplitter] = None,
    ) -> Dict[str, EvaluationResult]:
        target_models_dir = Path(models_dir if models_dir is not None else Config.MODELS_DIR)
        active_splitter = splitter if splitter is not None else DataSplitter()

        results: Dict[str, EvaluationResult] = {}
        for variant in ("model_a", "model_b"):
            model_path = target_models_dir / f"rf_{variant}.joblib"
            splits = active_splitter.split(variant=variant, save_splits=False)
            results[variant] = self.evaluate_variant(model_path=model_path, splits=splits)

        self.plot_confusion_matrices(results)
        self.plot_roc_and_pr_curves(results)
        self.plot_feature_importances(results)
        self.save_comparison_report(results)

        print(f"[+] Đã xuất biểu đồ và báo cáo tại: {self.reports_dir}")
        return results
