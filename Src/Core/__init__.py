"""
Package Src.Core
================
Chứa các thành phần cốt lõi dùng chung cho toàn bộ hệ thống EDR:
- Config: Lớp cấu hình hằng số và siêu tham số hệ thống.
- IRPOperation, IRPEvent, WindowSlice, FeatureVector, DetectionAlert: Các cấu trúc dữ liệu chuẩn mực.
"""

from .Config import Config
from .Schemas import (
    IRPOperation,
    IRPEvent,
    WindowSlice,
    FeatureVector,
    DetectionAlert,
)

__all__ = [
    "Config",
    "IRPOperation",
    "IRPEvent",
    "WindowSlice",
    "FeatureVector",
    "DetectionAlert",
]
