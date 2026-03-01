<!-- 可视化关系图谱 -->
<template>
  <div ref="graphContainer" class="w-full rounded-xl border" style="height: 500px; background: var(--md-surface-container-low);"></div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'

interface Character {
  name: string
  identity?: string
}

interface Relationship {
  character_from: string
  character_to: string
  description?: string
}

const props = defineProps<{
  characters: Character[]
  relationships: Relationship[]
}>()

const graphContainer = ref<HTMLElement | null>(null)
let network: any = null

const NODE_COLORS = [
  '#6366f1', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6',
  '#ec4899', '#14b8a6', '#f97316', '#06b6d4', '#84cc16'
]

const buildGraph = async () => {
  if (!graphContainer.value || !props.characters.length) return

  // Dynamic import to avoid SSR issues
  const vis = await import('vis-network/standalone')

  const nodes = new vis.DataSet(
    props.characters.map((char, i) => ({
      id: char.name,
      label: char.name + (char.identity ? `\n(${char.identity})` : ''),
      color: {
        background: NODE_COLORS[i % NODE_COLORS.length],
        border: NODE_COLORS[i % NODE_COLORS.length],
        highlight: { background: NODE_COLORS[i % NODE_COLORS.length] + 'cc', border: '#fff' },
        hover: { background: NODE_COLORS[i % NODE_COLORS.length] + 'ee', border: '#fff' }
      },
      font: { color: '#ffffff', size: 14, face: 'system-ui', bold: { color: '#ffffff' } },
      shape: 'dot',
      size: i === 0 ? 30 : 20,
      borderWidth: 2,
      shadow: true,
    }))
  )

  const edges = new vis.DataSet(
    props.relationships.map((rel, i) => ({
      id: i,
      from: rel.character_from,
      to: rel.character_to,
      label: rel.description || '',
      font: { size: 11, color: '#666', strokeWidth: 2, strokeColor: '#fff' },
      color: { color: '#94a3b8', highlight: '#6366f1', hover: '#818cf8' },
      width: 1.5,
      smooth: { enabled: true, type: 'curvedCW', roundness: 0.2 },
      arrows: { to: { enabled: false } },
    }))
  )

  const options = {
    physics: {
      solver: 'forceAtlas2Based',
      forceAtlas2Based: {
        gravitationalConstant: -80,
        centralGravity: 0.01,
        springLength: 150,
        springConstant: 0.08,
      },
      stabilization: { iterations: 150 },
    },
    interaction: {
      hover: true,
      tooltipDelay: 200,
      zoomView: true,
      dragView: true,
    },
    layout: { improvedLayout: true },
  }

  if (network) network.destroy()
  network = new vis.Network(graphContainer.value, { nodes, edges }, options)
}

watch(() => [props.characters, props.relationships], () => {
  nextTick(buildGraph)
}, { deep: true })

onMounted(() => {
  nextTick(buildGraph)
})

onBeforeUnmount(() => {
  if (network) {
    network.destroy()
    network = null
  }
})
</script>
