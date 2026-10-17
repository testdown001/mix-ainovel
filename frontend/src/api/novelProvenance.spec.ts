import { beforeEach, describe, expect, it, vi } from 'vitest'
vi.mock('@/stores/auth', () => ({ useAuthStore: () => ({ isAuthenticated: false }) }))
vi.mock('@/router', () => ({ default: { push: vi.fn() } }))
import { NovelAPI, diagnosticApi, narrativeStateApi } from './novel'

const fetchMock = vi.fn()
beforeEach(() => {
  fetchMock.mockReset()
  vi.stubGlobal('fetch', fetchMock)
  fetchMock.mockResolvedValue(new Response('{}', { status: 200, headers: { 'Content-Type': 'application/json' } }))
})
describe('author provenance API contracts', () => {
  it('sends the author-visible revision and stable version ID during selection', async () => {
    await NovelAPI.selectChapterVersion('p', 3, 0, { version_id: 17, expected_revision_id: 5, expected_content_hash: 'seen' })
    expect(JSON.parse(fetchMock.mock.calls[0]![1].body)).toEqual({
      chapter_number: 3, version_index: 0, version_id: 17, expected_revision_id: 5, expected_content_hash: 'seen',
    })
  })
  it('reads chapter-start canon without generating or repairing anything', async () => {
    await narrativeStateApi.get('p', 10)
    expect(fetchMock.mock.calls[0]![0]).toBe('/api/writer/novels/p/chapters/10/narrative-state')
    expect(fetchMock.mock.calls[0]![1].method).toBeUndefined()
  })
  it('pins diagnostics to an explicitly viewed version', async () => {
    await diagnosticApi.diagnoseChapter('p', 3, 17)
    expect(fetchMock.mock.calls[0]![0]).toContain('/3/diagnose?version_id=17')
  })
})
