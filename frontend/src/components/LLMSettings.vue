<!-- AIMETA P=LLM设置_模型配置界面|R=LLM配置表单|NR=不含模型调用|E=component:LLMSettings|X=internal|A=设置组件|D=vue|S=dom,net|RD=./README.ai -->
<template>
  <div>
    <h2 class="text-base font-bold text-white mb-1">LLM 配置</h2>
    <p class="text-xs mb-6" style="color:#888888;">建议接入自己的中转 API 和 Key 以获得最佳效果</p>

    <form @submit.prevent="handleSave" class="space-y-5">
      <!-- API URL -->
      <div>
        <label for="url" class="block text-xs font-medium mb-1.5" style="color:#888888;">API URL</label>
        <div class="relative">
          <input type="text" id="url" v-model="config.llm_provider_url"
            class="block w-full px-3 py-2.5 pr-9 rounded-lg text-sm transition-colors"
            style="background:#141414; border:1px solid #2A2A2A; color:#FFFFFF; outline:none;"
            placeholder="https://api.example.com/v1"
            @focus="($event.target as HTMLInputElement).style.borderColor='#FFE500'"
            @blur="($event.target as HTMLInputElement).style.borderColor='#2A2A2A'"
          />
          <button type="button" @click="clearApiUrl"
            class="absolute inset-y-0 right-2 flex items-center px-1.5 transition-colors"
            style="color:#555;" @mouseenter="($event.target as HTMLElement).style.color='#888'"
            @mouseleave="($event.target as HTMLElement).style.color='#555'">
            <svg class="w-4 h-4" viewBox="0 0 20 20" fill="currentColor">
              <path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd"/>
            </svg>
          </button>
        </div>
      </div>

      <!-- API Key -->
      <div>
        <label for="key" class="block text-xs font-medium mb-1.5" style="color:#888888;">API Key</label>
        <div class="relative">
          <input :type="showApiKey ? 'text' : 'password'" id="key" v-model="config.llm_provider_api_key"
            class="block w-full px-3 py-2.5 pr-20 rounded-lg text-sm transition-colors"
            style="background:#141414; border:1px solid #2A2A2A; color:#FFFFFF; outline:none;"
            placeholder="留空则使用默认 Key"
            @focus="($event.target as HTMLInputElement).style.borderColor='#FFE500'"
            @blur="($event.target as HTMLInputElement).style.borderColor='#2A2A2A'"
          />
          <div class="absolute inset-y-0 right-1 flex items-center gap-0.5">
            <button type="button" @click="toggleApiKeyVisibility"
              class="p-1.5 transition-colors rounded" style="color:#555;">
              <svg class="w-4 h-4" viewBox="0 0 20 20" fill="currentColor">
                <path v-if="showApiKey" fill-rule="evenodd" d="M.458 10C1.732 5.943 5.522 3 10 3s8.268 2.943 9.542 7c-1.274 4.057-5.064 7-9.542 7S1.732 14.057.458 10zM14 10a4 4 0 11-8 0 4 4 0 018 0z" clip-rule="evenodd"/>
                <path v-else d="M2.28 3L1 4.27l2.47 2.46A10.08 10.08 0 001 10c1.274 4.057 5.064 7 9.542 7a9.98 9.98 0 005.1-1.37L18.73 19 20 17.73 2.28 3zM10 15a5 5 0 01-4.905-4.042L7.3 13.16A3 3 0 0010 15zm7.44-2.47A9.07 9.07 0 0019.083 10c-1.274-4.057-5.064-7-9.542-7a9.92 9.92 0 00-3.84.77l1.57 1.57A5 5 0 0115 10a4.98 4.98 0 01-.74 2.62l2.18 2.18-.001-.001z"/>
              </svg>
            </button>
            <button type="button" @click="clearApiKey"
              class="p-1.5 transition-colors rounded" style="color:#555;">
              <svg class="w-4 h-4" viewBox="0 0 20 20" fill="currentColor">
                <path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd"/>
              </svg>
            </button>
          </div>
        </div>
      </div>

      <!-- Model -->
      <div>
        <label for="model" class="block text-xs font-medium mb-1.5" style="color:#888888;">模型名称</label>
        <div class="flex gap-2">
          <div class="relative flex-1">
            <input type="text" id="model" v-model="config.llm_provider_model"
              @focus="showModelDropdown = true" @blur="hideDropdown"
              class="block w-full px-3 py-2.5 pr-9 rounded-lg text-sm transition-colors"
              style="background:#141414; border:1px solid #2A2A2A; color:#FFFFFF; outline:none;"
              placeholder="留空则使用默认模型"
              @focusin="($event.target as HTMLInputElement).style.borderColor='#FFE500'"
              @focusout="($event.target as HTMLInputElement).style.borderColor='#2A2A2A'"
            />
            <button type="button" @click="clearApiModel"
              class="absolute inset-y-0 right-2 flex items-center px-1 transition-colors"
              style="color:#555;">
              <svg class="w-4 h-4" viewBox="0 0 20 20" fill="currentColor">
                <path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd"/>
              </svg>
            </button>
            <div v-if="showModelDropdown && availableModels.length > 0"
              class="absolute z-10 w-full mt-1 rounded-lg overflow-hidden shadow-xl"
              style="background:#1C1C1C; border:1px solid #2A2A2A; max-height:200px; overflow-y:auto;">
              <div v-for="model in filteredModels" :key="model"
                @mousedown="selectModel(model)"
                class="px-3 py-2 cursor-pointer text-sm transition-colors text-white"
                style="border-bottom:1px solid #2A2A2A;"
                @mouseenter="($event.target as HTMLElement).style.backgroundColor='#2A2A2A'"
                @mouseleave="($event.target as HTMLElement).style.backgroundColor='transparent'">
                {{ model }}
              </div>
              <div v-if="filteredModels.length === 0" class="px-3 py-2 text-sm" style="color:#888888;">
                无匹配模型
              </div>
            </div>
          </div>
          <button type="button" @click="loadModels" :disabled="isLoadingModels"
            class="px-4 py-2.5 rounded-lg text-sm font-medium transition-colors flex-shrink-0 flex items-center gap-1.5"
            style="background:#1C1C1C; border:1px solid #2A2A2A; color:#888888;">
            <svg v-if="isLoadingModels" class="animate-spin w-3.5 h-3.5" viewBox="0 0 24 24" fill="none">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"/>
            </svg>
            <span>{{ isLoadingModels ? '加载中...' : '获取模型' }}</span>
          </button>
        </div>
      </div>

      <!-- API Format -->
      <div>
        <label for="api-format" class="block text-xs font-medium mb-1.5" style="color:#888888;">API 类型</label>
        <select id="api-format" v-model="config.llm_provider_api_format"
          class="block w-full px-3 py-2.5 rounded-lg text-sm transition-colors"
          style="background:#141414; border:1px solid #2A2A2A; color:#FFFFFF; outline:none;">
          <option :value="null">auto（自动识别）</option>
          <option value="openai">OpenAI（兼容格式）</option>
          <option value="anthropic">Anthropic（原生 API）</option>
          <option value="anyrouter">AnyRouter（Claude Code 兼容代理）</option>
          <option value="gemini">Gemini（Google 原生 API）</option>
          <option value="openai-responses">OpenAI Responses（/v1/responses）</option>
        </select>
        <p class="mt-1.5 text-[11px]" style="color:#555555;">
          Google Gemini 选 Gemini，Claude Code 中转站选 AnyRouter，官方 Anthropic API 选 Anthropic，其他选 OpenAI 或 auto。
        </p>
      </div>

      <!-- Actions -->
      <div class="flex justify-end gap-3 pt-2">
        <button type="button" @click="handleDelete"
          class="px-4 py-2 rounded-lg text-sm font-medium transition-colors"
          style="background:transparent; border:1px solid #3D0A0A; color:#FF4757;">
          删除配置
        </button>
        <button type="submit"
          class="px-5 py-2 rounded-lg text-sm font-semibold transition-colors"
          style="background:#FFE500; color:#000;">
          保存
        </button>
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

const filteredModels = computed(() => {
  if (!config.value.llm_provider_model) return availableModels.value;
  const s = config.value.llm_provider_model.toLowerCase();
  return availableModels.value.filter(m => m.toLowerCase().includes(s));
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
    config.value = { llm_provider_url: '', llm_provider_api_key: '', llm_provider_model: '', llm_provider_api_format: null };
    alert('配置已删除！');
  }
};

const toggleApiKeyVisibility = () => { showApiKey.value = !showApiKey.value; };
const clearApiKey = () => { config.value.llm_provider_api_key = ''; };
const clearApiUrl = () => { config.value.llm_provider_url = ''; };
const clearApiModel = () => { config.value.llm_provider_model = ''; };

const loadModels = async () => {
  if (!config.value.llm_provider_api_key) { alert('请先填写 API Key'); return; }
  isLoadingModels.value = true;
  try {
    const models = await getAvailableModels({
      llm_provider_api_key: config.value.llm_provider_api_key,
      llm_provider_url: config.value.llm_provider_url || undefined,
      llm_provider_api_format: config.value.llm_provider_api_format,
    });
    availableModels.value = models;
    if (models.length > 0) showModelDropdown.value = true;
    else alert('未获取到模型列表，请检查API配置是否正确');
  } catch {
    alert('获取模型列表失败，请检查网络连接和API配置');
  } finally {
    isLoadingModels.value = false;
  }
};

const selectModel = (model: string) => { config.value.llm_provider_model = model; showModelDropdown.value = false; };
const hideDropdown = () => { setTimeout(() => { showModelDropdown.value = false; }, 200); };
</script>
