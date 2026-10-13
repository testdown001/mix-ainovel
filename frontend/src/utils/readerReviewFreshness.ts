export async function chapterContentHash(content: string): Promise<string | null> {
  try {
    const digest = await globalThis.crypto.subtle.digest('SHA-256', new TextEncoder().encode(content))
    return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, '0')).join('')
  } catch {
    // Older or insecure browser contexts must not present unverified feedback as current.
    return null
  }
}

export function readerReviewMatchesContent(report: unknown, contentHash: string | null): boolean {
  if (!report || typeof report !== 'object' || !contentHash) return false
  const data = report as Record<string, unknown>
  return (data.status === 'completed' || data.status === 'partial')
    && typeof data.source_sha256 === 'string'
    && /^[a-f0-9]{64}$/.test(data.source_sha256)
    && data.source_sha256 === contentHash
}
