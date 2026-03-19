<template>
  <aside class="neon-sidebar">
    <div class="neon-sidebar-header" v-if="projectName || subtitle">
      <div class="neon-sidebar-project" v-if="projectName">{{ projectName }}</div>
      <div class="neon-sidebar-subtitle" v-if="subtitle">{{ subtitle }}</div>
    </div>

    <nav class="neon-sidebar-nav">
      <button
        v-for="item in items"
        :key="item.key"
        class="neon-sidebar-item"
        :class="{ 'neon-sidebar-item--active': item.key === activeKey }"
        @click="$emit('select', item.key)"
      >
        <component :is="item.icon" v-if="item.icon" class="neon-sidebar-icon" />
        <span>{{ item.label }}</span>
      </button>
    </nav>

    <div class="neon-sidebar-bottom">
      <slot name="cta">
        <button
          v-if="ctaLabel"
          class="neon-sidebar-cta"
          @click="$emit('cta-click')"
        >
          <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4" />
          </svg>
          {{ ctaLabel }}
        </button>
      </slot>

      <slot name="footer">
        <button
          v-for="footer in footerItems"
          :key="footer.key"
          class="neon-sidebar-footer-item"
          @click="$emit('footer-click', footer.key)"
        >
          <component :is="footer.icon" v-if="footer.icon" class="neon-sidebar-icon" />
          <span>{{ footer.label }}</span>
        </button>
      </slot>
    </div>
  </aside>
</template>

<script setup lang="ts">
import type { Component } from 'vue'

interface SidebarItem {
  key: string
  label: string
  icon?: Component
}

defineProps<{
  projectName?: string
  subtitle?: string
  items: SidebarItem[]
  activeKey: string
  ctaLabel?: string
  footerItems?: SidebarItem[]
}>()

defineEmits<{
  select: [key: string]
  'cta-click': []
  'footer-click': [key: string]
}>()
</script>

<style scoped>
.neon-sidebar {
  width: 200px;
  min-height: 100%;
  background-color: var(--ar-bg-surface);
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  padding: 16px 0;
}

.neon-sidebar-header {
  padding: 0 20px 16px;
}

.neon-sidebar-project {
  font-family: var(--ar-font-display);
  font-size: 15px;
  font-weight: 700;
  color: var(--ar-primary);
  line-height: 1.3;
}

.neon-sidebar-subtitle {
  font-family: var(--ar-font-ui);
  font-size: 11px;
  font-weight: 500;
  color: var(--ar-text-muted);
  letter-spacing: 0.05em;
  text-transform: uppercase;
  margin-top: 2px;
}

.neon-sidebar-nav {
  flex: 1;
  padding: 0 8px;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.neon-sidebar-item {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  height: 40px;
  padding: 0 12px;
  border: none;
  border-radius: 4px;
  background: transparent;
  color: var(--ar-text-secondary);
  font-family: var(--ar-font-ui);
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s;
  text-align: left;
  position: relative;
}

.neon-sidebar-item:hover {
  background: rgba(255, 255, 255, 0.04);
  color: var(--ar-text-primary);
}

.neon-sidebar-item--active {
  background: var(--ar-primary-muted);
  color: var(--ar-primary);
}

.neon-sidebar-item--active::before {
  content: '';
  position: absolute;
  left: 0;
  top: 6px;
  bottom: 6px;
  width: 3px;
  background: var(--ar-primary);
  border-radius: 0 2px 2px 0;
}

.neon-sidebar-icon {
  width: 18px;
  height: 18px;
  flex-shrink: 0;
}

.neon-sidebar-bottom {
  padding: 12px 8px 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.neon-sidebar-cta {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  width: 100%;
  height: 40px;
  margin-bottom: 12px;
  border: none;
  border-radius: 4px;
  background: var(--ar-primary);
  color: var(--ar-on-primary);
  font-family: var(--ar-font-ui);
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s;
}

.neon-sidebar-cta:hover {
  box-shadow: 0 0 20px rgba(250, 204, 21, 0.3);
}

.neon-sidebar-footer-item {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  height: 36px;
  padding: 0 12px;
  border: none;
  border-radius: 4px;
  background: transparent;
  color: var(--ar-text-muted);
  font-family: var(--ar-font-ui);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s;
  text-align: left;
}

.neon-sidebar-footer-item:hover {
  color: var(--ar-text-secondary);
}
</style>
