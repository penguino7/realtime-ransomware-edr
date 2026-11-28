#include "process_manager.h"

// node lưu ánh xạ Pid -> Gid
typedef struct _PROCESS_NODE
{
    LIST_ENTRY ListEntry; // danh sách liên kết đôi vòng
    ULONG ProcessId;
    ULONG GroupId;
    BOOLEAN BreakInheritance;
} PROCESS_NODE, *PPROCESS_NODE;

// node lưu các Gid đang ở bị đưa vào black list
typedef struct _BLACKLIST_NODE
{
    LIST_ENTRY ListEntry;
    ULONG GroupId;
} BLACKLIST_NODE, *PBLACKLIST_NODE;

static LIST_ENTRY gProcessListHead;
static LIST_ENTRY gBlacklistHead;
static KSPIN_LOCK gProcessLock;
static ULONG gNextGroupId = 0; // dùng AllocateUniqueGidLocked để tăng biến đếm này

// Vùng dùng KSPIN_LOCK
// tìm node theo PID
static PPROCESS_NODE FindProcessNodeLocked(_In_ ULONG ProcessId)
{
    PLIST_ENTRY currentNode = gProcessListHead.Flink;
    while (currentNode != &gProcessListHead)
    {
        PPROCESS_NODE node = CONTAINING_RECORD(currentNode, PROCESS_NODE, ListEntry);
        if (node->ProcessId == ProcessId)
        {
            return node;
        }
        currentNode = currentNode->Flink;
    }
    return NULL;
}

// tìm node trong BLACKLIST Gid
static PBLACKLIST_NODE FindBlackListNodeLocked(_In_ ULONG GroupId)
{
    PLIST_ENTRY currentNode = gBlacklistHead.Flink;
    while (currentNode != &gBlacklistHead)
    {
        PBLACKLIST_NODE node = CONTAINING_RECORD(currentNode, BLACKLIST_NODE, ListEntry);
        if (node->GroupId == GroupId)
        {
            return node;
        }
        currentNode = currentNode->Flink;
    }
    return NULL;
}

// hàm kiếm tra xem Gid đã thuộc về tiến trình nào chưa hoặc có nằm trong danh sách đen hay không
static BOOLEAN IsGroupIdInUseLocked(_In_ ULONG GroupId)
{
    // Nếu gid đang nằm trong blacklist -> ko được cấp gid đó
    if (FindBlackListNodeLocked(GroupId) != NULL)
    {
        return TRUE;
    }

    // Nếu còn ít nhất 1 tiến trình đang chạy mang gid này -> ko đc cấp trùng
    PLIST_ENTRY currentNode = gProcessListHead.Flink;
    while (currentNode != &gProcessListHead)
    {
        PPROCESS_NODE node = CONTAINING_RECORD(currentNode, PROCESS_NODE, ListEntry);
        if (node->GroupId == GroupId)
        {
            return TRUE;
        }
        currentNode = currentNode->Flink;
    }
    return FALSE;
}

// cấp gid mới nhất trừ GID_INVALID (0) và ko trùng các gid đang tồn tại

static ULONG AllocateUniqueGidLocked(VOID)
{
    ULONG candidate;
    do
    {
        gNextGroupId++;
        candidate = gNextGroupId;
    } while (candidate == GID_INVALID || IsGroupIdInUseLocked(candidate));

    return candidate;
}

// Hàm sánh không phân biệt chữ hoa/thường theo đúng số ký tự
static BOOLEAN EqualsInsensitiveN(
    _In_reads_(Count) const WCHAR *A,
    _In_reads_(Count) const WCHAR *B,
    _In_ USHORT Count)

{
    for (USHORT i = 0; i < Count; i++)
    {
        WCHAR ca = A[i];
        WCHAR cb = B[i];

        if (ca >= L'A' && ca <= L'Z')
        {
            ca += (L'a' - L'A');
        }
        if (cb >= L'A' && cb <= L'Z')
        {
            cb += (L'a' - L'A');
        }
        if (ca != cb)
        {
            return FALSE;
        }
    }
    return TRUE;
}

// Hàm kiểm tra xem đường dẫn của tiến trình có trùng với các đường dẫn tiến trình hệ thống chung ko
static BOOLEAN MatchesSystemImagePath(
    _In_opt_ PCUNICODE_STRING ImageFileName,
    _In_ PCUNICODE_STRING SystemRootPath,
    _In_ PCUNICODE_STRING VolumeWindowsPath)
{
    if (ImageFileName == NULL || ImageFileName->Buffer == NULL || ImageFileName->Length == 0)
    {
        return FALSE;
    }

    USHORT totalChars = ImageFileName->Length / sizeof(WCHAR);
    const WCHAR *buf = ImageFileName->Buffer;

    // Dạng 1: So khớp với "\SystemRoot\..."
    USHORT sysRootChars = SystemRootPath->Length / sizeof(WCHAR);
    if (totalChars == sysRootChars && EqualsInsensitiveN(buf, SystemRootPath->Buffer, sysRootChars))
    {
        return TRUE;
    }

    // Dạng 2: "\Device\HarddiskVolume" + toàn chữ số [0-9]+ + "\Windows\..."

    static const WCHAR volumePathPrefix[] = L"\\Device\\HarddiskVolume";

    USHORT volumePathPrefixChars = (USHORT)((sizeof(volumePathPrefix) / sizeof(WCHAR)) - 1);

    USHORT volumeRelChars = VolumeWindowsPath->Length / sizeof(WCHAR);

    // Cần ít nhất 1 chữ số cho số thứ tự của volume

    if (totalChars < volumePathPrefixChars + 1 + volumeRelChars)
    {
        return FALSE;
    }

    if (!EqualsInsensitiveN(buf, volumePathPrefix, volumePathPrefixChars))
    {
        return FALSE;
    }

    // phần giữa từ VolumePrefixChars tới trươcs VolumeRelativeChars bắt buộc chỉ được chứa chữ số
    USHORT suffixStart = totalChars - volumeRelChars;
    for (USHORT i = volumePathPrefixChars; i < suffixStart; i++)
    {
        if (buf[i] < L'0' || buf[i] > L'9')
        {
            return FALSE;
        }
    }
    return EqualsInsensitiveN(buf + suffixStart, VolumeWindowsPath->Buffer, volumeRelChars);
}

// Kiếm tra tiến trình core của hệ thống ( gọi ở PASSIVE_LEVEL trước khi vào SPINLOCK)
static BOOLEAN IsCoreSystemProcess(
    _In_ ULONG Pid,
    _In_opt_ PCUNICODE_STRING ImageFileName)
{
    if (Pid == 0 || Pid == 4)
    {
        return TRUE; // Idle (0) và System(4)
    }
    if (ImageFileName == NULL || ImageFileName->Length == 0)
    {
        return FALSE;
    }

    static UNICODE_STRING sysRootSmss = RTL_CONSTANT_STRING(L"\\SystemRoot\\System32\\smss.exe");
    static UNICODE_STRING volSmss = RTL_CONSTANT_STRING(L"\\Windows\\System32\\smss.exe");
    static UNICODE_STRING sysRootCsrss = RTL_CONSTANT_STRING(L"\\SystemRoot\\System32\\csrss.exe");
    static UNICODE_STRING volCsrss = RTL_CONSTANT_STRING(L"\\Windows\\System32\\csrss.exe");

        if (MatchesSystemImagePath(ImageFileName, &sysRootSmss, &volSmss) || MatchesSystemImagePath(ImageFileName, &sysRootCsrss, &volCsrss))
    {
        return TRUE;
    }
    return FALSE;
}

// Kiểm tra tiến trình bị ngắt kế thừa
static BOOLEAN IsInheritanceBreaker(_In_opt_ PCUNICODE_STRING ImageFileName)
{
    if (ImageFileName == NULL || ImageFileName->Length == 0)
    {
        return FALSE;
    }
    static UNICODE_STRING sysRootExplorer = RTL_CONSTANT_STRING(L"\\SystemRoot\\explorer.exe");
    static UNICODE_STRING volExplorer = RTL_CONSTANT_STRING(L"\\Windows\\explorer.exe");
    static UNICODE_STRING sysRootServices = RTL_CONSTANT_STRING(L"\\SystemRoot\\System32\\services.exe");
    static UNICODE_STRING volServices = RTL_CONSTANT_STRING(L"\\Windows\\System32\\services.exe");

    if (MatchesSystemImagePath(ImageFileName, &sysRootExplorer, &volExplorer) ||
        MatchesSystemImagePath(ImageFileName, &sysRootServices, &volServices))
    {
        return TRUE;
    }
    return FALSE;
}

NTSTATUS ProcessManager_Init(VOID)
{
    InitializeListHead(&gProcessListHead);
    InitializeListHead(&gBlacklistHead);
    KeInitializeSpinLock(&gProcessLock);
    gNextGroupId = 0;

    return STATUS_SUCCESS;
}

VOID ProcessManager_Cleanup(VOID)
{
    KIRQL oldIrql;
    KeAcquireSpinLock(&gProcessLock, &oldIrql);

    // Dọn bảng ánh xạ giữa PID -> GID
    while (!IsListEmpty(&gProcessListHead))
    {
        PLIST_ENTRY currentNode = RemoveHeadList(&gProcessListHead);
        PPROCESS_NODE node = CONTAINING_RECORD(currentNode, PROCESS_NODE, ListEntry);
        ExFreePoolWithTag(node, PROC_POOL_TAG);
    }
    // Don sạch danh sách Blacklist
    while (!IsListEmpty(&gBlacklistHead))
    {
        PLIST_ENTRY currentNode = RemoveHeadList(&gBlacklistHead);
        PBLACKLIST_NODE blNode = CONTAINING_RECORD(currentNode, BLACKLIST_NODE, ListEntry);
        ExFreePoolWithTag(blNode, PROC_POOL_TAG);
    }

    KeReleaseSpinLock(&gProcessLock, oldIrql);
}

// callback khi có 1 tiến trình mới

VOID ProcessNotifyCallback(
    _Inout_ PEPROCESS Process,
    _In_ HANDLE ProcessId,
    _Inout_opt_ PPS_CREATE_NOTIFY_INFO CreateInfo)
{
    UNREFERENCED_PARAMETER(Process);
    ULONG pid = HandleToUlong(ProcessId);

    KIRQL oldIrql;

    // Tiến trình kết thúc -> tìm và xóa node

    if (CreateInfo == NULL)
    {
        KeAcquireSpinLock(&gProcessLock, &oldIrql);
        PPROCESS_NODE node = FindProcessNodeLocked(pid);
        if (node != NULL)
        {
            RemoveEntryList(&node->ListEntry);
        }
        KeReleaseSpinLock(&gProcessLock, oldIrql);

        if (node != NULL)
        {
            ExFreePoolWithTag(node, PROC_POOL_TAG);
        }
        return;
    }

    // Tiến trình mới khởi tạo

    // Kiếm tra xem có phải tiến trình core của hệ thống không
    if (IsCoreSystemProcess(pid, CreateInfo->ImageFileName))
    {
        return;
    }

    BOOLEAN breakInherit = IsInheritanceBreaker(CreateInfo->ImageFileName);
    ULONG parentPid = HandleToULong(CreateInfo->ParentProcessId);
    PPROCESS_NODE newNode = (PPROCESS_NODE)ExAllocatePool2(
        POOL_FLAG_NON_PAGED,
        sizeof(PROCESS_NODE),
        PROC_POOL_TAG);
    if (newNode == NULL)
    {
        return;
    }

    // Khóa spinlock để tra cứu pid của cha và chèn node mới
    KeAcquireSpinLock(&gProcessLock, &oldIrql);

    // nếu mà còn node cũ ứng với pid đó thì xóa cái node cũ đi
    PPROCESS_NODE existing = FindProcessNodeLocked(pid);
    if (existing != NULL)
    {
        RemoveEntryList(&existing->ListEntry);
    }
    PPROCESS_NODE parentNode = FindProcessNodeLocked(parentPid);

    ULONG assignedGid;

    if (parentNode != NULL && !parentNode->BreakInheritance)
    { // kế thừa gid từ tiến trình cha
        assignedGid = parentNode->GroupId;
    }
    else
    {
        // chưa có tiến trình cha hoặc là các tiến trình chung như explorer , service -> cấp gid mới
        assignedGid = AllocateUniqueGidLocked();
    }

    newNode->ProcessId = pid;
    newNode->GroupId = assignedGid;
    newNode->BreakInheritance = breakInherit;

    InsertTailList(&gProcessListHead, &newNode->ListEntry);

    KeReleaseSpinLock(&gProcessLock, oldIrql);

    if (existing != NULL)
    {
        ExFreePoolWithTag(existing, PROC_POOL_TAG);
    }
}

// Lấy Gid từ Pid
ULONG ProcessManager_GetGidByPid(_In_ ULONG ProcessId)
{
    if (ProcessId == 0 || ProcessId == 4)
    {
        return GID_INVALID;
    }

    ULONG gid = GID_INVALID;
    KIRQL oldIrql;

    KeAcquireSpinLock(&gProcessLock, &oldIrql);

    PPROCESS_NODE node = FindProcessNodeLocked(ProcessId);
    if (node != NULL)
    {
        gid = node->GroupId;
    }

    KeReleaseSpinLock(&gProcessLock, oldIrql);
    return gid;
}

// Check xem gid đang ở trong blacklist ko
BOOLEAN ProcessManager_IsGidBlacklisted(_In_ ULONG GroupId)
{
    if (GroupId == GID_INVALID)
    {
        return FALSE;
    }

    BOOLEAN isBlocked = FALSE;
    KIRQL oldIrql;

    KeAcquireSpinLock(&gProcessLock, &oldIrql);
    if (FindBlackListNodeLocked(GroupId) != NULL)
    {
        isBlocked = TRUE;
    }

    KeReleaseSpinLock(&gProcessLock, oldIrql);
    return isBlocked;
}

// hàm thêm / gỡ blacklist node
NTSTATUS ProcessManager_SetBlacklistGID(
    _In_ ULONG GroupId,
    _In_ BOOLEAN Block)

{
    if (GroupId == GID_INVALID)
    {
        return STATUS_INVALID_PARAMETER;
    }

    KIRQL oldIrql;
    // thêm blacklist node
    if (Block)
    {
        PBLACKLIST_NODE newBlacklistNode = (PBLACKLIST_NODE)ExAllocatePool2(
            POOL_FLAG_NON_PAGED,
            sizeof(BLACKLIST_NODE),
            PROC_POOL_TAG);

        if (newBlacklistNode == NULL)
        {
            return STATUS_INSUFFICIENT_RESOURCES;
        }

        newBlacklistNode->GroupId = GroupId;
        // Nếu BlacklistNode đó chưa tồn tại
        KeAcquireSpinLock(&gProcessLock, &oldIrql);
        if (FindBlackListNodeLocked(GroupId) == NULL)
        {
            InsertTailList(&gBlacklistHead, &newBlacklistNode->ListEntry);
            newBlacklistNode = NULL;
        }
        KeReleaseSpinLock(&gProcessLock, oldIrql);

        // Nếu GID đã có sẵn trong BlackListNode từ trước -> giải phóng node thừa

        if (newBlacklistNode != NULL)
        {
            ExFreePoolWithTag(newBlacklistNode, PROC_POOL_TAG);
        }
    }
    else
    {
        PBLACKLIST_NODE target = NULL;

        KeAcquireSpinLock(&gProcessLock, &oldIrql);
        target = FindBlackListNodeLocked(GroupId);
        if (target != NULL)
        {
            RemoveEntryList(&target->ListEntry);
        }
        KeReleaseSpinLock(&gProcessLock, oldIrql);

        if (target != NULL)
        {
            ExFreePoolWithTag(target, PROC_POOL_TAG);
        }
    }
    return STATUS_SUCCESS;
}
