// AIMETA P=M2本地章节草稿|R=IndexedDB缓存_延迟落盘|NR=不含远端保存_UI|E=useChapterDraft|X=internal|A=草稿读写_清理|D=vue_indexeddb|S=browser-storage|RD=./README.ai
import { ref } from 'vue'

export interface ChapterLocalDraft {
  key: string
  projectId: string
  chapterNumber: number
  content: string
  baseRevisionId: number
  baseContentHash: string
  updatedAt: number
}

const DB_NAME = 'arboris-novel'
const STORE_NAME = 'chapter-drafts'
const DB_VERSION = 1

let databasePromise: Promise<IDBDatabase> | null = null

const draftKey = (projectId: string, chapterNumber: number) => `${projectId}:${chapterNumber}`

const openDatabase = (): Promise<IDBDatabase> => {
  if (databasePromise) return databasePromise
  databasePromise = new Promise((resolve, reject) => {
    if (typeof indexedDB === 'undefined') {
      reject(new Error('当前浏览器不支持本地草稿存储'))
      return
    }
    const request = indexedDB.open(DB_NAME, DB_VERSION)
    request.onupgradeneeded = () => {
      const database = request.result
      if (!database.objectStoreNames.contains(STORE_NAME)) {
        database.createObjectStore(STORE_NAME, { keyPath: 'key' })
      }
    }
    request.onsuccess = () => resolve(request.result)
    request.onerror = () => reject(request.error || new Error('无法打开本地草稿库'))
  })
  return databasePromise
}

const runRequest = async <T>(
  mode: IDBTransactionMode,
  action: (store: IDBObjectStore) => IDBRequest<T>,
): Promise<T> => {
  const database = await openDatabase()
  return new Promise((resolve, reject) => {
    const transaction = database.transaction(STORE_NAME, mode)
    const request = action(transaction.objectStore(STORE_NAME))
    let requestCompleted = false
    let requestResult: T
    let settled = false
    const fail = (error: Error) => {
      if (settled) return
      settled = true
      reject(error)
    }

    // IDBRequest 成功只代表对象仓库操作完成；readwrite 事务仍可能在稍后提交失败。
    // 必须等 transaction.oncomplete 才能向调用方承诺“草稿已经落盘”。
    request.onsuccess = () => {
      requestResult = request.result
      requestCompleted = true
    }
    request.onerror = () => fail(request.error || new Error('本地草稿操作失败'))
    transaction.onabort = () => fail(transaction.error || new Error('本地草稿事务已中止'))
    transaction.onerror = () => fail(transaction.error || new Error('本地草稿事务失败'))
    transaction.oncomplete = () => {
      if (settled) return
      if (!requestCompleted) {
        fail(new Error('本地草稿事务结束但操作结果缺失'))
        return
      }
      settled = true
      resolve(requestResult)
    }
  })
}

export function useChapterDraft() {
  const isPersisting = ref(false)
  const storageError = ref<string | null>(null)
  let debounceTimer: number | null = null
  let queuedDraft: ChapterLocalDraft | null = null

  const persist = async (draft: ChapterLocalDraft) => {
    isPersisting.value = true
    try {
      await runRequest('readwrite', (store) => store.put(draft))
      storageError.value = null
    } catch (error) {
      storageError.value = error instanceof Error ? error.message : '本地草稿保存失败'
      throw error
    } finally {
      isPersisting.value = false
    }
  }

  const schedule = (draft: Omit<ChapterLocalDraft, 'key' | 'updatedAt'>) => {
    queuedDraft = {
      ...draft,
      key: draftKey(draft.projectId, draft.chapterNumber),
      updatedAt: Date.now(),
    }
    if (debounceTimer !== null) window.clearTimeout(debounceTimer)
    debounceTimer = window.setTimeout(() => {
      debounceTimer = null
      const next = queuedDraft
      queuedDraft = null
      if (next) void persist(next).catch(() => undefined)
    }, 500)
  }

  const flush = async () => {
    if (debounceTimer !== null) {
      window.clearTimeout(debounceTimer)
      debounceTimer = null
    }
    const next = queuedDraft
    queuedDraft = null
    if (next) await persist(next)
  }

  const load = async (projectId: string, chapterNumber: number): Promise<ChapterLocalDraft | null> => {
    const result = await runRequest<ChapterLocalDraft | undefined>(
      'readonly',
      (store) => store.get(draftKey(projectId, chapterNumber)),
    )
    return result || null
  }

  const remove = async (projectId: string, chapterNumber: number) => {
    await runRequest('readwrite', (store) => store.delete(draftKey(projectId, chapterNumber)))
  }

  const flushSafely = () => {
    void flush().catch(() => undefined)
  }

  return { isPersisting, storageError, schedule, flush, flushSafely, load, remove }
}
