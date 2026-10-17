/** An explicit mismatch is never displayed as evidence for a different manuscript. */
export function receiptForVersion(
  receipt: Record<string, unknown> | null | undefined,
  versionId: number | null | undefined,
): Record<string, unknown> | null {
  if (!receipt) return null
  if (receipt.version_id != null && versionId != null && receipt.version_id !== versionId) return null
  return receipt
}
