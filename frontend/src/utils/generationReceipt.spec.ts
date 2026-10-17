import { describe, expect, it } from 'vitest'
import { receiptForVersion } from './generationReceipt'

describe('generation receipts stay attached to their manuscript', () => {
  it('rejects explicit cross-version receipts', () => {
    expect(receiptForVersion({ version_id: 17, status: 'recorded' }, 18)).toBeNull()
  })
  it('keeps exact-version receipts and absent historical receipts unknown', () => {
    const receipt = { version_id: 17, status: 'recorded' }
    expect(receiptForVersion(receipt, 17)).toBe(receipt)
    expect(receiptForVersion(null, 17)).toBeNull()
  })
})
