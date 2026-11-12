# Package Workloads: các chiến lược mô phỏng hành vi người dùng lành tính (Benign Workloads)

from .BaseWorkload import BaseWorkload
from .CompressionWorkload import CompressionWorkload
from .OfficeWorkload import OfficeWorkload
from .FileOpsWorkload import FileOpsWorkload
from .ImageWorkload import ImageWorkload
from .DevelopmentWorkload import DevelopmentWorkload
from .CompileWorkload import CompileWorkload

__all__ = [
    "BaseWorkload",
    "CompressionWorkload",
    "OfficeWorkload",
    "FileOpsWorkload",
    "ImageWorkload",
    "DevelopmentWorkload",
    "CompileWorkload",
]
