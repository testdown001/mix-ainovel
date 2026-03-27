<!-- AIMETA P=模板选择器_场景化写作模板|R=模板列表_参数填写_应用生成|NR=|E=TemplateSelector|X=internal|A=模板选择|D=vue|S=dom|RD=./README.ai -->
<template>
  <div class="template-selector" :class="{ 'params-open': selectedTemplate }">
    <!-- 顶部标题区 -->
    <header class="selector-header">
      <h2 class="selector-title">写作模板</h2>
      <p class="selector-subtitle">选择场景模板快速生成写作指令</p>
    </header>

    <!-- 分类标签 -->
    <div class="category-tabs">
      <button
        class="category-tab"
        :class="{ active: selectedCategory === null }"
        @click="selectedCategory = null"
      >
        全部
      </button>
      <button
        v-for="cat in categories"
        :key="cat.id"
        class="category-tab"
        :class="{ active: selectedCategory === cat.id }"
        @click="selectedCategory = cat.id"
      >
        {{ cat.icon }} {{ cat.name }}
      </button>
    </div>

    <!-- 搜索框 -->
    <div class="search-box">
      <input
        v-model="searchQuery"
        type="text"
        placeholder="搜索模板..."
        class="search-input"
      />
    </div>

    <!-- 模板列表 -->
    <div class="template-grid">
      <div
        v-for="tpl in filteredTemplates"
        :key="tpl.id"
        class="template-card"
        :class="{ selected: selectedTemplate?.id === tpl.id }"
        @click="selectTemplate(tpl)"
      >
        <div class="template-icon">{{ tpl.icon }}</div>
        <div class="template-info">
          <div class="template-name">{{ tpl.name }}</div>
          <div class="template-desc">{{ tpl.description }}</div>
          <div class="template-meta">
            <span class="category-tag">{{ tpl.category }}</span>
            <span class="use-count" v-if="tpl.use_count > 0">已使用 {{ tpl.use_count }} 次</span>
          </div>
        </div>
      </div>

      <!-- 无模板提示 -->
      <div v-if="filteredTemplates.length === 0" class="empty-state">
        <span>暂无模板</span>
      </div>
    </div>

    <!-- 参数填写面板：Teleport 到 body 避免被模态/overflow 裁切 -->
    <Teleport to="body">
      <div v-if="selectedTemplate" class="params-panel params-panel-fixed">
        <div class="params-header">
          <h4>{{ selectedTemplate.icon }} {{ selectedTemplate.name }}</h4>
          <button class="btn-close" @click="selectedTemplate = null">×</button>
        </div>

        <div class="params-form">
        <div
          v-for="param in selectedTemplate.parameters"
          :key="param.name"
          class="param-item"
        >
          <label :for="param.name">
            {{ param.label }}
            <span v-if="param.required" class="required">*</span>
          </label>

          <!-- 文本输入 -->
          <input
            v-if="param.type === 'text'"
            :id="param.name"
            v-model="paramValues[param.name]"
            type="text"
            :placeholder="param.description"
            class="param-input"
          />

          <!-- 数字输入 -->
          <input
            v-else-if="param.type === 'number'"
            :id="param.name"
            v-model.number="paramValues[param.name]"
            type="number"
            :placeholder="param.description"
            class="param-input"
          />

          <!-- 文本域 -->
          <textarea
            v-else-if="param.type === 'textarea'"
            :id="param.name"
            v-model="paramValues[param.name]"
            :placeholder="param.description"
            class="param-textarea"
            rows="3"
          ></textarea>

          <!-- 下拉选择 -->
          <select
            v-else-if="param.type === 'select'"
            :id="param.name"
            v-model="paramValues[param.name]"
            class="param-select"
          >
            <option
              v-for="opt in param.options"
              :key="opt"
              :value="opt"
            >
              {{ opt }}
            </option>
          </select>

          <div class="param-hint" v-if="param.description">
            {{ param.description }}
          </div>
        </div>
      </div>

      <div class="params-actions">
        <button class="btn-cancel" @click="selectedTemplate = null">取消</button>
        <button
          class="btn-infer"
          @click="handleInferParams"
          :disabled="inferring || !props.projectId || !props.chapterNumber"
        >
          {{ inferring ? '推演中...' : 'AI 推演' }}
        </button>
        <button class="btn-apply" @click="handleApply" :disabled="!canApply">
          应用模板
        </button>
      </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { listTemplates, getTemplateCategories, inferTemplateParams, type WritingTemplate, type TemplateCategory } from '@/api/writingTemplate'

interface Props {
  projectId?: string
  chapterNumber?: number
}

const props = withDefaults(defineProps<Props>(), {
  projectId: '',
  chapterNumber: 0,
})

const emit = defineEmits<{
  (e: 'apply', prompt: string): void
}>()

const templates = ref<WritingTemplate[]>([])
const categories = ref<TemplateCategory[]>([])
const selectedCategory = ref<string | null>(null)
const searchQuery = ref('')
const selectedTemplate = ref<WritingTemplate | null>(null)
const paramValues = ref<Record<string, any>>({})

// 加载数据
onMounted(async () => {
  try {
    const [templatesData, categoriesData] = await Promise.all([
      listTemplates(),
      getTemplateCategories()
    ])
    templates.value = templatesData
    categories.value = categoriesData
  } catch (e) {
    console.error('加载模板失败:', e)
  }
})

// 过滤模板
const filteredTemplates = computed(() => {
  let result = templates.value

  if (selectedCategory.value) {
    result = result.filter(t => t.category === selectedCategory.value)
  }

  if (searchQuery.value) {
    const query = searchQuery.value.toLowerCase()
    result = result.filter(t =>
      t.name.toLowerCase().includes(query) ||
      t.description?.toLowerCase().includes(query)
    )
  }

  return result
})

// 能否应用
const canApply = computed(() => {
  if (!selectedTemplate.value) return false

  // 检查必填参数
  for (const param of selectedTemplate.value.parameters) {
    if (param.required && !paramValues.value[param.name]) {
      return false
    }
  }
  return true
})

// 选择模板
function selectTemplate(tpl: WritingTemplate) {
  selectedTemplate.value = tpl

  // 设置默认值
  paramValues.value = {}
  for (const param of tpl.parameters) {
    paramValues.value[param.name] = param.default || ''
  }
}

// 应用模板
async function handleApply() {
  if (!selectedTemplate.value || !canApply.value) return

  try {
    // 构建写作指令
    let prompt = selectedTemplate.value.prompt_template

    // 替换模板中的参数
    for (const [key, value] of Object.entries(paramValues.value)) {
      prompt = prompt.replace(new RegExp(`\\{${key}\\}`, 'g'), value)
    }

    emit('apply', prompt)
    selectedTemplate.value = null
  } catch (e) {
    console.error('应用模板失败:', e)
  }
}

// AI 推演填入参数
const inferring = ref(false)

async function handleInferParams() {
  if (!selectedTemplate.value || !props.projectId || !props.chapterNumber) return

  inferring.value = true
  try {
    const inferred = await inferTemplateParams(
      selectedTemplate.value.id,
      props.projectId,
      props.chapterNumber
    )
    for (const [key, value] of Object.entries(inferred)) {
      const paramDef = selectedTemplate.value?.parameters.find(p => p.name === key)
      const currentVal = paramValues.value[key]
      // 只覆盖空值或默认值，尊重用户已手动填写的内容
      if (!currentVal || currentVal === (paramDef?.default || '')) {
        paramValues.value[key] = value
      }
    }
  } catch (e: any) {
    console.error('AI推演失败:', e)
  } finally {
    inferring.value = false
  }
}
</script>

<style scoped>
.template-selector {
  max-width: 800px;
  margin: 0 auto;
  overflow-x: hidden;
  position: relative;
  min-height: 200px;
  padding: 0 20px 20px;
}

.template-selector.params-open {
  min-height: min(70vh, 600px);
}

.selector-header {
  padding: 20px 0 16px;
  margin-bottom: 4px;
  border-bottom: 1px solid #2A2A2A;
}

.selector-title {
  margin: 0 0 4px 0;
  font-size: 1.25rem;
  font-weight: 600;
  color: #FFFFFF;
  letter-spacing: 0.02em;
}

.selector-subtitle {
  margin: 0;
  font-size: 0.8125rem;
  color: #888;
  line-height: 1.4;
}

.category-tabs {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 16px;
  padding: 4px 0 0;
  align-items: center;
}

.category-tab {
  padding: 8px 14px;
  border: 1px solid #2A2A2A;
  border-radius: 20px;
  background: #141414;
  color: #888;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
  flex-shrink: 0;
  line-height: 1.25;
}

.category-tab:hover {
  border-color: #FFE500;
  color: #FFE500;
}

.category-tab.active {
  background: #FFE500;
  color: #000;
  border-color: #FFE500;
  font-weight: 600;
}

.search-box {
  margin-bottom: 20px;
}

.search-input {
  width: 100%;
  padding: 10px 16px;
  border: 1px solid #2A2A2A;
  border-radius: 8px;
  font-size: 14px;
  background: #1C1C1C;
  color: #FFFFFF;
}

.search-input::placeholder {
  color: #555;
}

.search-input:focus {
  outline: none;
  border-color: #FFE500;
}

.template-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 12px;
  margin-bottom: 20px;
}

.template-card {
  padding: 16px;
  background: #141414;
  border: 1px solid #2A2A2A;
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.2s;
}

.template-card:hover {
  border-color: #FFE500;
  box-shadow: 0 2px 12px rgba(255, 229, 0, 0.06);
}

.template-card.selected {
  border-color: #FFE500;
  background: #2A2600;
}

.template-icon {
  font-size: 28px;
  margin-bottom: 8px;
}

.template-name {
  font-size: 15px;
  font-weight: 600;
  color: #FFFFFF;
  margin-bottom: 4px;
}

.template-desc {
  font-size: 12px;
  color: #888;
  margin-bottom: 8px;
  line-height: 1.4;
}

.template-meta {
  display: flex;
  gap: 8px;
  font-size: 11px;
}

.category-tag {
  background: #1C1C1C;
  color: #CCCCCC;
  padding: 2px 8px;
  border-radius: 4px;
  border: 1px solid #2A2A2A;
}

.use-count {
  color: #666;
}

.empty-state {
  grid-column: 1 / -1;
  text-align: center;
  padding: 40px;
  color: #666;
}

.params-panel.params-panel-fixed {
  position: fixed;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 90vw;
  max-width: 480px;
  max-height: 85vh;
  background: #141414;
  border: 1px solid #2A2A2A;
  border-radius: 16px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.6);
  overflow: hidden;
  z-index: 2001;
  display: flex;
  flex-direction: column;
}

.params-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid #2A2A2A;
}

.params-header h4 {
  margin: 0;
  font-size: 16px;
  color: #FFFFFF;
}

.btn-close {
  width: 32px;
  height: 32px;
  border: none;
  background: none;
  font-size: 24px;
  cursor: pointer;
  border-radius: 50%;
  color: #888;
}

.btn-close:hover {
  background: #1C1C1C;
  color: #FFFFFF;
}

.params-form {
  padding: 20px;
  flex: 1;
  min-height: 0;
  overflow-y: auto;
}

.param-item {
  margin-bottom: 16px;
}

.param-item label {
  display: block;
  font-size: 13px;
  font-weight: 500;
  margin-bottom: 6px;
  color: #CCCCCC;
}

.required {
  color: #FF4757;
}

.param-input,
.param-textarea,
.param-select {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid #2A2A2A;
  border-radius: 8px;
  font-size: 14px;
  background: #1C1C1C;
  color: #FFFFFF;
}

.param-input::placeholder,
.param-textarea::placeholder {
  color: #555;
}

.param-input:focus,
.param-textarea:focus,
.param-select:focus {
  outline: none;
  border-color: #FFE500;
}

.param-textarea {
  resize: vertical;
}

.param-select option {
  background: #1C1C1C;
  color: #FFFFFF;
}

.param-hint {
  font-size: 11px;
  color: #666;
  margin-top: 4px;
}

.params-actions {
  display: flex;
  gap: 12px;
  padding: 16px 20px;
  border-top: 1px solid #2A2A2A;
}

.btn-cancel,
.btn-apply {
  flex: 1;
  padding: 10px 16px;
  border-radius: 8px;
  font-size: 14px;
  cursor: pointer;
}

.btn-cancel {
  background: #1C1C1C;
  border: 1px solid #2A2A2A;
  color: #888;
}

.btn-cancel:hover {
  border-color: #444;
  color: #FFFFFF;
}

.btn-apply {
  background: #FFE500;
  color: #000;
  border: none;
  font-weight: 600;
}

.btn-apply:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.btn-apply:hover:not(:disabled) {
  background: #FFF062;
}

.btn-infer {
  flex: 1;
  padding: 10px 16px;
  border-radius: 8px;
  font-size: 14px;
  cursor: pointer;
  background: #2A2600;
  color: #FFE500;
  border: 1px solid rgba(255, 229, 0, 0.2);
}

.btn-infer:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.btn-infer:hover:not(:disabled) {
  background: #3A3400;
}
</style>
