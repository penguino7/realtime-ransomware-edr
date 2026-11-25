#ifndef _RANSOM_SHARED_H_
#define _RANSOM_SHARED_H_

#ifdef _KERNEL_MODE
#include <fltKernel.h>
#else
#include <windows.h>
#endif

// Ép cho cpu không chèn byte rác vào struct
#pragma pack(push, 1)

// 1. Cấu hình Cổng Giao Tiếp (Communication Port) & Độ dài đường dẫn
#define RANSOM_PORT_NAME L"\\RansomAgentPort"
#define MAX_PATH_CHARS 260

// 2. Định nghĩa các loại thao tác I/O (Mã chuẩn hóa 1 byte)
#define OP_CREATE 1 // Thao tác tạo mới hoặc mở file
#define OP_WRITE 2  // Thao tác ghi dữ liệu vào file
#define OP_RENAME 3 // Thao tác đổi tên hoặc đổi đuôi file
#define OP_DELETE 4 // Thao tác xóa file
#define OP_READ 5   // Thao tác đọc dữ liệu từ file

// 3. Định nghĩa các lệnh từ User Agent gửi xuống Driver
#define CMD_BLOCK_GID 1    // Khóa toàn bộ I/O của cây tiến trình (GID)
#define CMD_UNBLOCK_GID 2  // Mở khóa GID khỏi danh sách đen
#define CMD_QUERY_STATUS 3 // Truy vấn trạng thái hoạt động của Driver

// 4. Struct IRP_RECORD: Gói tin từ Kernel đẩy lên User Agent
// Được Minifilter đóng gói và đẩy qua cổng Communication Port mỗi khi có I/O
typedef struct _IRP_RECORD
{
    ULONG ProcessId;                   // PID của tiến trình thực hiện thao tác (4 bytes)
    ULONG GroupId;                     // Định danh nhóm GID của cây tiến trình (4 bytes)
    UCHAR OperationType;               // Loại thao tác: OP_CREATE, OP_WRITE, OP_RENAME, OP_DELETE, OP_READ (1 byte)
    float ShannonEntropy;              // Độ hỗn loạn tính trên 64KB RAM khi đọc/ghi file: 0.0 -> 8.0 (4 bytes)
    LARGE_INTEGER FileSize;            // Kích thước của file tính theo bytes (8 bytes)
    LARGE_INTEGER Timestamp;           // Mốc thời gian hệ thống chuẩn Windows 100-nanosecond (8 bytes)
    WCHAR FilePath[MAX_PATH_CHARS];    // Đường dẫn file gốc bị tác động (520 bytes)
    WCHAR NewFilePath[MAX_PATH_CHARS]; // Đường dẫn mới (chỉ dùng khi đổi tên file / OP_RENAME) (520 bytes)
} IRP_RECORD, *PIRP_RECORD;

// 5. Struct COMMAND_RECORD: Gói lệnh từ User Agent gửi xuống Kernel
// Dùng để ra lệnh cho Minifilter Driver chặn đứng hành vi độc hại
typedef struct _COMMAND_RECORD
{
    ULONG CommandType;   // Loại lệnh: CMD_BLOCK_GID hoặc CMD_UNBLOCK_GID (4 bytes)
    ULONG TargetGroupId; // GID mục tiêu cần khóa hoặc mở khóa (4 bytes)
} COMMAND_RECORD, *PCOMMAND_RECORD;

#pragma pack(pop)

#endif
