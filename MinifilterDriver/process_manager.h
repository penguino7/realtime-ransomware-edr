#ifndef _PROCESS_MANAGER_H_
#define _PROCESS_MANAGER_H_

#include <fltKernel.h>

// giá trị GID cho tiến trình hệ thống được bỏ qua
// hoặc tiến trình ko bao giờ nằm trong blacklist
#define GID_INVALID 0

// Nhãn 4 byte Pool Tag đánh dấu bộ nhớ được cấp phát động của 1 module Process Manager
#define PROC_POOL_TAG 'MCRP'

// Khởi tạo khóa Spinlock, các danh sách liên kết PID -> GID và Blacklist.
// Gọi 1 lần duy nhất bên trong DriverEntry.
NTSTATUS ProcessManager_Init(VOID);

// Thu hồi bộ nhớ đã cấp phát động cho bảng tiến trình và Blacklist
VOID ProcessManager_Cleanup(VOID);

// Hàm Callback đăng kí với ntoskrnl.exe
// CreateInfo != NULL: Tiến trình mới tạo -> cấp hoặc kế thừa GID.
// CreateInfo == NULL: Tiến trình vừa thoát -> xóa khỏi bảng theo dõi.
VOID ProcessNotifyCallback(
    _Inout_ PEPROCESS Process,
    _In_ HANDLE ProcessId,
    _Inout_opt_ PPS_CREATE_NOTIFY_INFO CreateInfo);

// Tra cứu GroupId của 1 processId
// Trả về GID_INVALID nếu PID ko tồn tại trong bảng hoặc thuộc tiến trình được bỏ qua
ULONG ProcessManager_GetGidByPid(
    _In_ ULONG ProcessId);

// Kiểm tra xem một GroupId có đang nằm trong blacklist hay ko
// trả về true nếu bị chặn và false nếu được phép hoạt động

BOOLEAN ProcessManager_IsGidBlacklisted(
    _In_ ULONG GroupId);

// Thêm hoặc gỡ một GroupId khỏi danh sách đen (gọi từ PortMessageNotify).
// - Block == TRUE:  Khóa toàn bộ I/O của GID này (CMD_BLOCK_GID).
// - Block == FALSE: Mở khóa GID (CMD_UNBLOCK_GID).
NTSTATUS ProcessManager_SetBlacklistGID(
    _In_ ULONG GroupId,
    _In_ BOOLEAN Block);
#endif