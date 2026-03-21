<!-- AIMETA P=角色区_角色信息展示|R=角色卡片|NR=不含编辑功能|E=component:CharactersSection|X=ui|A=角色组件|D=vue|S=dom|RD=./README.ai -->
<template>
  <div class="space-y-5">
    <div class="flex items-center justify-between">
      <div>
        <h2 class="text-xl font-bold text-white">主要角色</h2>
        <p class="text-sm text-[#666] mt-0.5">了解故事中核心人物的目标与个性</p>
      </div>
      <button
        v-if="editable"
        type="button"
        class="text-[#555] hover:text-[#FFE500] transition-colors"
        @click="emitEdit('characters', '主要角色', data?.characters)">
        <svg class="h-6 w-6" viewBox="0 0 20 20" fill="currentColor">
          <path d="M17.414 2.586a2 2 0 00-2.828 0L7 10.172V13h2.828l7.586-7.586a2 2 0 000-2.828z" />
          <path fill-rule="evenodd" d="M2 6a2 2 0 012-2h4a1 1 0 010 2H4v10h10v-4a1 1 0 112 0v4a2 2 0 01-2 2H4a2 2 0 01-2-2V6z" clip-rule="evenodd" />
        </svg>
      </button>
    </div>

    <div class="grid grid-cols-1 xl:grid-cols-2 gap-5">
      <article
        v-for="(character, index) in characters"
        :key="index"
        class="bg-[#141414] rounded-2xl border border-[#2A2A2A] hover:border-[#3A3A3A] transition-all duration-300">
        <div class="p-6">
          <div class="flex flex-col sm:flex-row sm:items-center gap-4 mb-4">
            <div class="w-14 h-14 rounded-full bg-[#1C1C1C] border border-[#2A2A2A] flex items-center justify-center text-[#FFE500] text-lg font-semibold flex-shrink-0">
              {{ character.name?.slice(0, 1) || '角' }}
            </div>
            <div>
              <h3 class="text-lg font-bold text-white">{{ character.name || '未命名角色' }}</h3>
              <p v-if="character.identity" class="text-sm text-[#FFE500] font-medium mt-0.5">{{ character.identity }}</p>
            </div>
          </div>
          <dl class="space-y-3 text-sm text-[#888]">
            <div v-if="character.personality">
              <dt class="font-semibold text-[#bbb] mb-1">性格</dt>
              <dd class="leading-6">{{ character.personality }}</dd>
            </div>
            <div v-if="character.goals">
              <dt class="font-semibold text-[#bbb] mb-1">目标</dt>
              <dd class="leading-6">{{ character.goals }}</dd>
            </div>
            <div v-if="character.abilities">
              <dt class="font-semibold text-[#bbb] mb-1">能力</dt>
              <dd class="leading-6">{{ character.abilities }}</dd>
            </div>
            <div v-if="character.relationship_to_protagonist">
              <dt class="font-semibold text-[#bbb] mb-1">与主角的关系</dt>
              <dd class="leading-6">{{ character.relationship_to_protagonist }}</dd>
            </div>
            <div v-if="character.power_system_id">
              <dt class="font-semibold text-[#bbb] mb-1">力量体系</dt>
              <dd class="leading-6 text-[#A855F7] font-medium">
                {{ getPowerSystemName(character.power_system_id) }}
                <span v-if="character.current_power_level_id" class="text-[#666] text-sm ml-1">
                  · {{ getPowerLevelName(character.power_system_id, character.current_power_level_id) }}
                </span>
              </dd>
            </div>
          </dl>
        </div>
      </article>
      <div v-if="!characters.length" class="bg-[#141414] rounded-2xl border border-dashed border-[#2A2A2A] p-10 text-center text-[#555]">
        暂无角色信息
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

interface CharacterItem {
  name?: string
  identity?: string
  personality?: string
  goals?: string
  abilities?: string
  relationship_to_protagonist?: string
  power_system_id?: number | null
  current_power_level_id?: number | null
}

const props = defineProps<{
  data: { characters?: CharacterItem[] } | null
  editable?: boolean
  powerSystems?: Array<{ id: number, name: string, levels: Array<{ id: number, name: string }> }>
}>()

const emit = defineEmits<{
  (e: 'edit', payload: { field: string; title: string; value: any }): void
}>()

const characters = computed(() => props.data?.characters || [])

const getPowerSystemName = (id: number) => {
  if (!props.powerSystems) return `System #${id}`
  const sys = props.powerSystems.find(p => p.id === id)
  return sys ? sys.name : `System #${id}`
}

const getPowerLevelName = (sysId: number, levelId: number) => {
  if (!props.powerSystems) return `Level #${levelId}`
  const sys = props.powerSystems.find(p => p.id === sysId)
  if (!sys) return `Level #${levelId}`
  const lvl = sys.levels?.find(l => l.id === levelId)
  return lvl ? lvl.name : `Level #${levelId}`
}

const emitEdit = (field: string, title: string, value: any) => {
  if (!props.editable) return
  emit('edit', { field, title, value })
}
</script>

<script lang="ts">
import { defineComponent } from 'vue'

export default defineComponent({
  name: 'CharactersSection'
})
</script>
