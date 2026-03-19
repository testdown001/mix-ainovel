<!-- AIMETA P=LLM设置_模型配置界面|R=LLM配置表单|NR=不含模型调用|E=component:LLMSettings|X=internal|A=设置组件|D=vue|S=dom,net|RD=./README.ai -->
<template>
  <div class="bg-bg-surface border border-border rounded-2xl p-8">
    <h2 class="text-xl font-bold text-text-primary mb-2">核心驱动配置</h2>
    <p class="text-text-secondary text-sm mb-6">设置 Arboris Novel 使用的大语言模型 API。支持 OpenAI 兼容格式。</p>
    <form @submit.prevent="handleSave" class="space-y-6">
      <div>
        <label for="url" class="block text-sm font-medium text-text-secondary mb-2">API 接口地址</label>
        <div class="relative">
          <input
            type="text"
            id="url"
            v-model="config.llm_provider_url"
            class="block w-full h-12 px-4 pr-10 bg-bg-elevated border border-border rounded-xl text-text-primary placeholder:text-text-muted focus:border-border-focus focus:outline-none focus:ring-3 focus:ring-primary/10 transition-all duration-150 text-sm"
            placeholder="https://api.openai.com/v1"
          >
          <button
            type="button"
            @click="clearApiUrl"
            class="absolute inset-y-0 right-2 flex items-center px-2 text-text-muted hover:text-text-secondary cursor-pointer"
            aria-label="清空 API URL"
          >
            <svg class="w-5 h-5" viewBox="0 0 20 20" fill="currentColor">
              <path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd" />
            </svg>
          </button>
        </div>
      </div>
      <div>
        <label for="key" class="block text-sm font-medium text-text-secondary mb-2">API Key</label>
        <div class="relative">
          <input
            :type="showApiKey ? 'text' : 'password'"
            id="key"
            v-model="config.llm_provider_api_key"
            class="block w-full h-12 px-4 pr-24 bg-bg-elevated border border-border rounded-xl text-text-primary placeholder:text-text-muted focus:border-border-focus focus:outline-none focus:ring-3 focus:ring-primary/10 transition-all duration-150 text-sm"
            placeholder="留空则使用默认Key"
          >
          <button
            type="button"
            @click="clearApiKey"
            class="absolute inset-y-0 right-2 flex items-center px-2 text-text-muted hover:text-text-secondary cursor-pointer"
            aria-label="清空 API Key"
          >
            <svg class="w-5 h-5" viewBox="0 0 20 20" fill="currentColor">
              <path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd" />
            </svg>
          </button>
          <button
            type="button"
            @click="toggleApiKeyVisibility"
            class="absolute inset-y-0 right-10 flex items-center px-2 text-text-muted hover:text-text-secondary cursor-pointer"
            :aria-label="showApiKey ? '隐藏 API Key' : '显示 API Key'"
          >
            <svg v-if="showApiKey" class="w-5 h-5" viewBox="0 0 20 20" fill="currentColor">
              <path d="M10 5c-4.478 0-8.268 2.943-9.542 7C1.732 16.057 5.522 19 10 19s8.268-2.943 9.542-7C18.268 7.943 14.478 5 10 5zm0 10a5 5 0 110-10 5 5 0 010 10z" fill-opacity="0.2" />
              <path d="M10 7a3 3 0 100 6 3 3 0 000-6z" />
            </svg>
            <svg v-else class="w-5 h-5" viewBox="0 0 20 20" fill="currentColor">
              <path fill-rule="evenodd" d="M.458 10C1.732 5.943 5.522 3 10 3s8.268 2.943 9.542 7c-1.274 4.057-5.064 7-9.542 7S1.732 14.057.458 10zm13.707 0a4.167 4.167 0 11-8.334 0 4.167 4.167 0 018.334 0z" clip-rule="evenodd" />
              <path d="M10 8a2 2 0 100 4 2 2 0 000-4z" />
            </svg>
          </button>
        </div>
        <p class="mt-1.5 text-xs text-text-muted">您的密钥将安全地存储在本地，不会上传至我们的服务器。</p>
      </div>
      <div>
        <label for="model" class="block text-sm font-medium text-text-secondary mb-2">默认推理模型</label>
        <div class="flex gap-3">
          <div class="relative flex-1">
            <input
              type="text"
              id="model"
              v-model="config.llm_provider_model"
              @focus="showModelDropdown = true"
              @blur="hideDropdown"
              class="block w-full h-12 px-4 pr-10 bg-bg-elevated border border-border rounded-xl text-text-primary placeholder:text-text-muted focus:border-border-focus focus:outline-none focus:ring-3 focus:ring-primary/10 transition-all duration-150 text-sm"
              placeholder="留空则使用默认模型"
            >
            <button
              type="button"
              @click="clearApiModel"
              class="absolute inset-y-0 right-2 flex items-center px-2 text-text-muted hover:text-text-secondary cursor-pointer"
              aria-label="清空模型名称"
            >
              <svg class="w-5 h-5" viewBox="0 0 20 20" fill="currentColor">
                <path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd" />
              </svg>
            </button>
            <div
              v-if="showModelDropdown && availableModels.length > 0"
              class="absolute z-10 w-full mt-1 bg-bg-elevated border border-border rounded-xl max-h-60 overflow-auto"
            >
              <div
                v-for="model in filteredModels"
                :key="model"
                @mousedown="selectModel(model)"
                class="px-4 py-2.5 cursor-pointer hover:bg-primary-muted hover:text-primary text-sm text-text-secondary"
              >
                {{ model }}
              </div>
              <div v-if="filteredModels.length === 0" class="px-4 py-2.5 text-sm text-text-muted">
                无匹配的模型
              </div>
            </div>
          </div>
          <button
            type="button"
            @click="loadModels"
            :disabled="isLoadingModels"
            class="h-12 px-5 bg-bg-elevated border border-border rounded-xl text-text-primary text-sm font-medium hover:border-[rgba(255,255,255,0.2)] transition-all duration-150 disabled:opacity-40 disabled:cursor-not-allowed flex items-center gap-2 cursor-pointer"
          >
            <svg v-if="isLoadingModels" class="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            <span>{{ isLoadingModels ? '加载中...' : '获取模型' }}</span>
          </button>
        </div>
      </div>
      <div>
        <label for="api-format" class="block text-sm font-medium text-text-secondary mb-2">API 类型</label>
        <select
          id="api-format"
          v-model="config.llm_provider_api_format"
          class="block w-full h-12 px-4 bg-bg-elevated border border-border rounded-xl text-text-primary focus:border-border-focus focus:outline-none focus:ring-3 focus:ring-primary/10 transition-all duration-150 text-sm appearance-none cursor-pointer"
        >
          <option :value="null">auto（自动识别）</option>
          <option value="openai">OpenAI（兼容格式）</option>
          <option value="anthropic">Anthropic（原生 API）</option>
          <option value="anyrouter">AnyRouter（Claude Code 兼容代理）</option>
          <option value="gemini">Gemini（Google 原生 API）</option>
          <option value="openai-responses">OpenAI Responses（/v1/responses）</option>
        </select>
        <p class="mt-1.5 text-xs text-text-muted">选择 API 请求格式。Google Gemini 选 Gemini，Claude Code 中转站选 AnyRouter，官方 Anthropic API 选 Anthropic，其他选 OpenAI 或 auto。</p>
      </div>
      <div class="flex justify-end gap-3 pt-4">
        <button type="button" @click="handleDelete" class="h-10 px-5 bg-bg-elevated border border-border rounded-full text-text-secondary text-sm font-medium hover:border-error hover:text-error transition-all duration-150 cursor-pointer">删除配置</button>
        <button type="submit" class="h-10 px-6 bg-primary hover:bg-primary-hover text-on-primary rounded-full text-sm font-semibold transition-all duration-150 cursor-pointer">保存配置</button>
      </div>
    </form>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue';
import { getLLMConfig, createOrUpdateLLMConfig, deleteLLMConfig, getAvailableModels, type LLMConfigCreate } from '@/api/llm';

const config = ref<LLMConfigCreate>({
  llm_provider_url: '',
  llm_provider_api_key: '',
  llm_provider_model: '',
  llm_provider_api_format: null,
});

const showApiKey = ref(false);
const availableModels = ref<string[]>([]);
const isLoadingModels = ref(false);
const showModelDropdown = ref(false);

// 根据输入过滤模型列表
const filteredModels = computed(() => {
  if (!config.value.llm_provider_model) {
    return availableModels.value;
  }
  const searchTerm = config.value.llm_provider_model.toLowerCase();
  return availableModels.value.filter(model =>
    model.toLowerCase().includes(searchTerm)
  );
});

onMounted(async () => {
  const existingConfig = await getLLMConfig();
  if (existingConfig) {
    config.value = {
      llm_provider_url: existingConfig.llm_provider_url || '',
      llm_provider_api_key: existingConfig.llm_provider_api_key || '',
      llm_provider_model: existingConfig.llm_provider_model || '',
      llm_provider_api_format: existingConfig.llm_provider_api_format || null,
    };
  }
});

const handleSave = async () => {
  const payload: LLMConfigCreate = {
    ...config.value,
    llm_provider_url: config.value.llm_provider_url || null,
    llm_provider_api_key: config.value.llm_provider_api_key || null,
    llm_provider_model: config.value.llm_provider_model || null,
    llm_provider_api_format: config.value.llm_provider_api_format || null,
  };
  await createOrUpdateLLMConfig(payload);
  alert('设置已保存！');
};

const handleDelete = async () => {
  if (confirm('确定要删除您的自定义LLM配置吗？删除后将恢复为默认配置。')) {
    await deleteLLMConfig();
    config.value = {
      llm_provider_url: '',
      llm_provider_api_key: '',
      llm_provider_model: '',
      llm_provider_api_format: null,
    };
    alert('配置已删除！');
  }
};

const toggleApiKeyVisibility = () => {
  showApiKey.value = !showApiKey.value;
};

const clearApiKey = () => {
  config.value.llm_provider_api_key = '';
};

const clearApiUrl = () => {
  config.value.llm_provider_url = '';
};

const clearApiModel = () => {
  config.value.llm_provider_model = '';
};

const loadModels = async () => {
  // 验证表单
  if (!config.value.llm_provider_api_key) {
    alert('请先填写 API Key');
    return;
  }

  isLoadingModels.value = true;
  try {
    const models = await getAvailableModels({
      llm_provider_api_key: config.value.llm_provider_api_key,
      llm_provider_url: config.value.llm_provider_url || undefined,
      llm_provider_api_format: config.value.llm_provider_api_format,
    });
    availableModels.value = models;
    if (models.length > 0) {
      showModelDropdown.value = true;
    } else {
      alert('未获取到模型列表，请检查API配置是否正确');
    }
  } catch (error) {
    console.error('Failed to load models:', error);
    alert('获取模型列表失败，请检查网络连接和API配置');
  } finally {
    isLoadingModels.value = false;
  }
};

const selectModel = (model: string) => {
  config.value.llm_provider_model = model;
  showModelDropdown.value = false;
};

const hideDropdown = () => {
  // 延迟隐藏，确保点击事件能触发
  setTimeout(() => {
    showModelDropdown.value = false;
  }, 200);
};
</script>
