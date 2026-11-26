#ifndef _ENTROPY_H_
#define _ENTROPY_H_

#include <fltKernel.h>

// Giới hạn tối đa số byte lấy mẫu để tính Entropy (64 KB)
#define ENTROPY_SIZE 65536

// Tính chỉ số Shannon Entropy (0.0 -> 8.0) cho một vùng đệm dữ liệu trên RAM.
// Lưu ý về SAL Annotation (_In_...): Đây là các macro mô tả quy ước bộ nhớ cho
// công cụ phân tích tĩnh của Visual Studio/WDK kiểm tra lỗi truy xuất vùng nhớ lúc biên dịch:
// - _In_reads_bytes_(Length): Buffer là tham số đầu vào (chỉ đọc), phải chứa tối thiểu Length byte hợp lệ.
// - _In_: Length là tham số đầu vào truyền theo giá trị.
float CalculateShannonEntropy(
    _In_reads_bytes_(Length) PUCHAR Buffer,
    _In_ ULONG Length);

#endif
