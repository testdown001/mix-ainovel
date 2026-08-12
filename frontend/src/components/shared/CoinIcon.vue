<!-- AIMETA P=积分金币图标|R=替代🪙emoji的统一SVG图标|E=component:CoinIcon|X=ui|A=图标|D=vue|S=dom -->
<template>
  <svg
    :style="{ width: size + 'px', height: size + 'px' }"
    class="inline-block flex-shrink-0"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="2"
    aria-hidden="true"
  >
    <circle cx="12" cy="12" r="9" />
    <path stroke-linecap="round" stroke-linejoin="round" d="M9 8.5l3 4 3-4M12 12.5V17M9.5 14.5h5" />
  </svg>
</template>

<script setup lang="ts">
withDefaults(defineProps<{ size?: number }>(), { size: 16 })
</script>
