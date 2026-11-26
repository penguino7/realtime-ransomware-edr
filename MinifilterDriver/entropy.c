#include "entropy.h"

// tính xấp xỉ log2(x) cho số thực dương bằng tách bit IEEE-754 + đa thức
// với IEEE-754 , số thực x được biểu diễn dưới dạng x = m x 2 mũ E ( ví dụ 83.75 = 1.30859375 x 2 mũ 6)( m thuộc [1;2))
// từ công thức x = m x 2 mũ E => log2(x) = E + log2(m)
// đặt y = ( m - 1) / ( m + 1) => theo đa thức hội tụ có log2(m) ~ 2 x 1.44269504 x (y + ( y^3 /3)+(y^5 / 5) + (y^7 / 7))
static float FastLog2(_In_ float x)

{
    if (x <= 0.0f)
    {
        return 0.0f;
    }
    union
    {
        float f;
        ULONG u;
    } val;

    val.f = x;

    // tách số mũ E ( 8 bits)
    int E = (int)((val.u >> 23) & 0xFF) - 127;

    // ép phần lẻ m về đoạn [1;2) bằng cách đặt lại e thành 127
    val.u = (val.u & 0x007FFFFF) | 0x3F800000;
    float m = val.f;

    // Tính log2(m) = (1 / ln(2)) * 2 * (y + y^3/3 + y^5/5 + y^7/7), với y = (m-1)/(m+1)
    float y = (m - 1.0f) / (m + 1.0f);
    float y2 = y * y;
    float ln_m = 2.0f * y * (1.0f + y2 * (1.0f / 3.0f + y2 * (1.0f / 5.0f + y2 / 7.0f)));
    float log2_m = ln_m * 1.44269504f; // 1.44269504 ≈ 1 / ln(2)

    return (float)E + log2_m;
}

float CalculateShannonEntropy(
    _In_reads_bytes_(Length) PUCHAR Buffer,
    _In_ ULONG Length)
{

    if (Buffer == NULL || Length == 0)
    {
        return 0.0f;
    }

    if (Length > ENTROPY_SIZE)
    {
        Length = ENTROPY_SIZE;
    }

    ULONG ByteCounts[256] = {0};

    for (ULONG i = 0; i < Length; i++)
    {
        ByteCounts[Buffer[i]]++;
    }

    KFLOATING_SAVE floatSave;

    if (!NT_SUCCESS(KeSaveFloatingPointState(&floatSave)))
    {
        return 0.0f;
    }
    // công thức tính entropy H = -Tổng(p(i) . log2(pi)) <-> log2(N) -1/N * Tổng (ci * log2(ci)) ( với ci là tần suất xuất hiện của byte i)
    float sum = 0.0f;
    for (ULONG i = 0; i < 256; i++)
    {
        if (ByteCounts[i] > 0)
        {
            float count = (float)ByteCounts[i];
            sum += count * FastLog2(count);
        }
    }
    float n = (float)Length;
    float entropy = FastLog2(n) - (sum / n);

    KeRestoreFloatingPointState(&floatSave);

    if (entropy < 0.0f)
    {
        entropy = 0.0f;
    }
    if (entropy > 8.0f)
    {
        entropy = 8.0f;
    }
    return entropy;
}