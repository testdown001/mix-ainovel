import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createRenderer, nextTick, reactive, ssrContextKey } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import InspirationMode from './InspirationMode.vue'
import { NovelAPI } from '@/api/novel'
import { useNovelStore } from '@/stores/novel'

const navigation = vi.hoisted(() => ({ route: null as any, replace: vi.fn(), push: vi.fn() }))
vi.mock('vue-router', () => ({ useRoute: () => navigation.route, useRouter: () => navigation }))
vi.mock('@/router', () => ({ default: navigation }))
vi.mock('@/api/novel', () => ({ NovelAPI: {
  createNovel: vi.fn(), getNovel: vi.fn(), converseConcept: vi.fn(),
  listProjectReferenceNovels: vi.fn(), listMusePersonas: vi.fn(),
} }))
vi.mock('@/composables/useAlert', () => ({ globalAlert: { showError: vi.fn(), showConfirm: vi.fn() } }))
vi.mock('@/components/ChatBubble.vue', () => ({ default: {} }))
vi.mock('@/components/ConversationInput.vue', () => ({ default: {} }))
vi.mock('@/components/InlineProgress.vue', () => ({ default: {} }))
vi.mock('@/components/BlueprintConfirmation.vue', () => ({ default: {} }))
vi.mock('@/components/BlueprintDisplay.vue', () => ({ default: {} }))
vi.mock('@/components/InspirationLoading.vue', () => ({ default: {} }))
vi.mock('@/components/ReferenceNovelInput.vue', () => ({ default: {} }))
vi.mock('@/components/UpgradePrompt.vue', () => ({ default: {} }))

// 执行真实页面的 setup、watch 和 onMounted；无需浏览器即可回归异步失败后的页面状态。
const renderer = createRenderer<any, any>({
  createElement: () => ({}), createText: () => ({}), createComment: () => ({}),
  insert: () => {}, remove: () => {}, setText: () => {}, setElementText: () => {},
  parentNode: () => null, nextSibling: () => null, patchProp: () => {},
})
let app: ReturnType<typeof renderer.createApp> | undefined
const project = (history: any[] = []) => ({ id: 'existing-idea', title: '未命名灵感',
  initial_prompt: '守墓人的故事', chapters: [], conversation_history: history })
const answer = { ai_message: '你希望他守住什么？', ui_control: { type: 'text_input' },
  conversation_state: { stage: 'exploring' }, is_complete: false }
async function flush() {
  for (let i = 0; i < 8; i++) { await Promise.resolve(); await nextTick() }
}
async function mount() {
  app = renderer.createApp({ ...InspirationMode, render: () => null })
  app.provide(ssrContextKey, { modules: new Set() })
  app.mount({})
  await flush()
  return (app as any)._instance.setupState
}

beforeEach(() => {
  vi.resetAllMocks()
  setActivePinia(createPinia())
  navigation.route = reactive({ path: '/inspiration', query: {} })
  navigation.replace.mockImplementation(async (route) => { navigation.route.query = route.query })
  vi.mocked(NovelAPI.createNovel).mockResolvedValue(project())
  vi.mocked(NovelAPI.getNovel).mockResolvedValue(project())
  vi.mocked(NovelAPI.listMusePersonas).mockResolvedValue({ personas: [], tier: 'free', features: {} } as any)
  vi.mocked(NovelAPI.listProjectReferenceNovels).mockResolvedValue([])
  vi.mocked(NovelAPI.converseConcept).mockResolvedValue(answer as any)
  vi.spyOn(console, 'error').mockImplementation(() => {})
})
afterEach(() => { app?.unmount(); vi.restoreAllMocks() })

describe('灵感模式通信失败恢复', () => {
  it('项目创建本身失败时保留故事种子，重试创建仍可正常开始', async () => {
    const vm = await mount()
    vm.initialIdea = '故事种子'
    vi.mocked(NovelAPI.createNovel).mockRejectedValueOnce(new Error('create failed'))
    await vm.startConversation()
    expect(vm.conversationStarted).toBe(false)
    expect(vm.initialIdea).toBe('故事种子')
    expect(useNovelStore().currentProject).toBeNull()
    await vm.startConversation()
    expect(vm.conversationStarted).toBe(true)
    expect(useNovelStore().currentProject?.id).toBe('existing-idea')
  })

  it('首轮无输入连续失败也始终留在同一构思，重试入口保持可用', async () => {
    const vm = await mount()
    vi.mocked(NovelAPI.converseConcept).mockRejectedValue(new Error('timeout'))
    await vm.startConversation()
    await vm.retryConversation()
    expect(vm.conversationStarted).toBe(true)
    expect(vm.pendingConversation.input).toBeNull()
    expect(vm.currentUIControl.type).toBe('text_input')
    expect(vm.currentTurn).toBe(0)
    expect(vm.chatMessages).toHaveLength(0)
    expect(NovelAPI.createNovel).toHaveBeenCalledTimes(1)
    expect(navigation.route.query.project_id).toBe('existing-idea')
  })

  it('首轮 500 后保留原项目、输入和地址，重试不新建项目或重复显示用户消息', async () => {
    const vm = await mount()
    vm.initialIdea = '守墓人的故事'
    vm.exclusions = '不用系统'
    vi.mocked(NovelAPI.converseConcept).mockRejectedValueOnce(new Error('500 invalid JSON'))
    await vm.startConversation()
    expect(vm.conversationStarted).toBe(true)
    expect(vm.isInitialLoading).toBe(false)
    expect(vm.exclusions).toBe('不用系统')
    expect(vm.chatMessages).toEqual([{ type: 'user', content: '守墓人的故事' }])
    expect(useNovelStore().currentProject?.id).toBe('existing-idea')
    expect(navigation.route.query.project_id).toBe('existing-idea')
    expect(vm.currentUIControl.type).toBe('text_input')
    expect(vm.conversationError).toContain('已保留')
    await vm.retryConversation()
    expect(NovelAPI.createNovel).toHaveBeenCalledTimes(1)
    expect(vi.mocked(NovelAPI.converseConcept).mock.calls.map(args => args[0])).toEqual(['existing-idea', 'existing-idea'])
    expect(vm.chatMessages.filter((m: any) => m.type === 'user')).toHaveLength(1)
    expect(vm.currentTurn).toBe(1)
    expect(vm.conversationError).toBe('')
  })

  it('中途失败保留已有对话、选项、轮次和状态，随后仍能继续', async () => {
    const vm = await mount()
    await vm.startConversation()
    vm.currentUIControl = { type: 'single_choice', options: [{ id: 'a', label: '守住家人' }] }
    vi.mocked(NovelAPI.converseConcept).mockRejectedValueOnce(new Error('network failed'))
    await vm.handleUserInput({ id: 'a', value: '守住家人' })
    expect(vm.currentTurn).toBe(1)
    expect(vm.currentUIControl.options[0].label).toBe('守住家人')
    expect(vm.chatMessages[0].content).toBe(answer.ai_message)
    expect(useNovelStore().currentConversationState).toEqual(answer.conversation_state)
    await vm.retryConversation()
    expect(vm.currentTurn).toBe(2)
    expect(NovelAPI.createNovel).toHaveBeenCalledTimes(1)
  })

  it('恢复已有构思失败时保留恢复页，重试加载不创建新构思', async () => {
    navigation.route.query.project_id = 'existing-idea'
    vi.mocked(NovelAPI.getNovel).mockRejectedValueOnce(new Error('offline'))
    const vm = await mount()
    expect(vm.restoreFailed).toBe(true)
    expect(vm.conversationStarted).toBe(true)
    expect(vm.isRestoringConversation).toBe(false)
    await vm.retryConversation()
    expect(vm.restoreFailed).toBe(false)
    expect(vm.pendingConversation.input.value).toBe('守墓人的故事')
    await vm.retryConversation()
    expect(NovelAPI.createNovel).not.toHaveBeenCalled()
    expect(NovelAPI.converseConcept).toHaveBeenCalledWith('existing-idea', expect.anything(), {}, expect.anything())
  })

  it('恢复时还原对话状态，旧的非 JSON 消息也不触发清空', async () => {
    navigation.route.query.project_id = 'existing-idea'
    vi.mocked(NovelAPI.getNovel).mockResolvedValue(project([
      { role: 'assistant', content: JSON.stringify(answer) },
    ]))
    const vm = await mount()
    expect(useNovelStore().currentConversationState).toEqual(answer.conversation_state)
    vi.mocked(NovelAPI.getNovel).mockResolvedValue(project([{ role: 'assistant', content: '早期的回复' }]))
    await vm.restoreConversation('existing-idea')
    expect(vm.chatMessages[0].content).toBe('早期的回复')
    expect(vm.restoreFailed).toBe(false)
    expect(vm.currentUIControl.type).toBe('text_input')
    expect(NovelAPI.createNovel).not.toHaveBeenCalled()
  })
})
