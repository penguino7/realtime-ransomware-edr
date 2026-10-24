from .Workloads import (
    BaseWorkload,
    CompressionWorkload,
    OfficeWorkload,
    FileOpsWorkload,
    ImageWorkload,
)
from .Managers import WorkloadManager

__all__ = [
    "BaseWorkload",
    "CompressionWorkload",
    "OfficeWorkload",
    "FileOpsWorkload",
    "ImageWorkload",
    "WorkloadManager",
]

