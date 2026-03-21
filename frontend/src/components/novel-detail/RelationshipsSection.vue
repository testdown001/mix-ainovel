<!-- AIMETA P=关系区_角色关系展示|R=关系图谱|NR=不含编辑功能|E=component:RelationshipsSection|X=ui|A=关系组件|D=vue|S=dom|RD=./README.ai -->
<template>
  <div class="space-y-5">
    <div class="flex items-center justify-between">
      <div>
        <h2 class="text-xl font-bold text-white">人物关系</h2>
        <p class="text-sm text-[#666] mt-0.5">角色之间的纽带与冲突</p>
      </div>
      <div class="flex items-center gap-2">
        <!-- 视图切换 -->
        <div class="flex rounded-lg overflow-hidden border border-[#2A2A2A]">
          <button
            class="px-3 py-1.5 text-sm font-medium transition-colors"
            :class="viewMode === 'list' ? 'bg-[#FFE500] text-black' : 'bg-[#141414] text-[#666] hover:bg-[#1C1C1C]'"
            @click="viewMode = 'list'"
          >
            📋 列表
          </button>
          <button
            class="px-3 py-1.5 text-sm font-medium transition-colors"
            :class="viewMode === 'graph' ? 'bg-[#FFE500] text-black' : 'bg-[#141414] text-[#666] hover:bg-[#1C1C1C]'"
            @click="viewMode = 'graph'"
          >
            🔗 图谱
          </button>
        </div>
        <button
          v-if="editable"
          type="button"
          class="text-[#555] hover:text-[#FFE500] transition-colors"
          @click="emitEdit('relationships', '人物关系', data?.relationships)">
          <svg class="h-6 w-6" viewBox="0 0 20 20" fill="currentColor">
            <path d="M17.414 2.586a2 2 0 00-2.828 0L7 10.172V13h2.828l7.586-7.586a2 2 0 000-2.828z" />
            <path fill-rule="evenodd" d="M2 6a2 2 0 012-2h4a1 1 0 010 2H4v10h10v-4a1 1 0 112 0v4a2 2 0 01-2 2H4a2 2 0 01-2-2V6z" clip-rule="evenodd" />
          </svg>
        </button>
      </div>
    </div>

    <!-- 列表视图 -->
    <template v-if="viewMode === 'list'">
      <div class="grid grid-cols-1 md:grid-cols-2 gap-5">
        <div
          v-for="(relation, index) in relationships"
          :key="index"
          class="bg-[#141414] rounded-2xl border border-[#2A2A2A] p-6">
          <div class="flex items-center justify-between">
            <div class="flex items-center space-x-3">
              <div class="w-10 h-10 rounded-full bg-[#1C1C1C] border border-[#2A2A2A] flex items-center justify-center text-[#FFE500] font-semibold text-sm">
                {{ relation.character_from?.slice(0, 1) || '角' }}
              </div>
              <span class="font-semibold text-white truncate text-sm">{{ relation.character_from || '未知角色' }}</span>
            </div>
            <svg class="text-[#444] flex-shrink-0" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14"/><path d="m12 5 7 7-7 7"/></svg>
            <div class="flex items-center space-x-3">
              <span class="font-semibold text-white truncate text-sm">{{ relation.character_to || '未知角色' }}</span>
              <div class="w-10 h-10 rounded-full bg-[rgba(46,213,115,0.1)] border border-[rgba(46,213,115,0.2)] flex items-center justify-center text-[#2ED573] font-semibold text-sm">
                {{ relation.character_to?.slice(0, 1) || '角' }}
              </div>
            </div>
          </div>
          <div class="mt-4 bg-[#1C1C1C] border border-[#2A2A2A] rounded-xl p-4 text-center">
            <p class="text-sm font-semibold text-white">{{ relation.relationship_type || '关系' }}</p>
            <p class="text-xs text-[#888] leading-5 mt-1">{{ relation.description || '暂无描述' }}</p>
          </div>
        </div>
        <div v-if="!relationships.length" class="bg-[#141414] rounded-2xl border border-dashed border-[#2A2A2A] p-10 text-center text-[#555]">
          暂无人际关系信息
        </div>
      </div>
    </template>

    <!-- 图谱视图 -->
    <template v-else>
      <RelationshipGraph
        :characters="characters"
        :relationships="graphRelationships"
      />
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import RelationshipGraph from './RelationshipGraph.vue'

interface RelationshipItem {
  character_from?: string
  character_to?: string
  relationship_type?: string
  description?: string
}

interface CharacterItem {
  name: string
  identity?: string
}

const props = defineProps<{
  data: { relationships?: RelationshipItem[]; characters?: CharacterItem[] } | null
  editable?: boolean
}>()

const viewMode = ref<'list' | 'graph'>('list')

const emit = defineEmits<{
  (e: 'edit', payload: { field: string; title: string; value: any }): void
}>()

const relationships = computed(() => props.data?.relationships || [])
const characters = computed(() => props.data?.characters || [])

const graphRelationships = computed(() =>
  relationships.value
    .filter((r): r is RelationshipItem & { character_from: string; character_to: string } =>
      !!r.character_from && !!r.character_to
    )
)

const emitEdit = (field: string, title: string, value: any) => {
  if (!props.editable) return
  emit('edit', { field, title, value })
}
</script>

<script lang="ts">
import { defineComponent } from 'vue'

export default defineComponent({
  name: 'RelationshipsSection'
})
</script>
