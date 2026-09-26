/* SPDX-License-Identifier: Apache-2.0 */
/* The caller provides distinct bounded storage for values and pointer slots.
 * These slots are image data, not compiler-generated call-frame saves. */
int main(long *values, long **slots)
{
    long i;
    for (i = 0; i < 14; i++) {
        values[i] = hello_char(i);
        slots[i] = &values[i];
    }
    for (i = 0; i < 14; i++) {
        long *p = slots[i];
        if (*p != hello_char(i))
            return 1;
        *p = *p + 0;
    }
    return 0;
}
