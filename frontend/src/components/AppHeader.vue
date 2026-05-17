<template>
  <header class="app-header">
    <div class="header-left">
      <div class="brand" @click="$emit('brand-click')">MIROFISH</div>
      <button v-if="backLabel" class="header-back-btn" @click="$emit('back-click')">← {{ backLabel }}</button>
    </div>

    <div v-if="viewMode !== null" class="header-center">
      <div class="view-switcher">
        <button
          v-for="mode in ['graph', 'split', 'workbench']"
          :key="mode"
          class="switch-btn"
          :class="{ active: viewMode === mode }"
          @click="$emit('update:viewMode', mode)"
        >
          {{ { graph: $t('main.layoutGraph'), split: $t('main.layoutSplit'), workbench: $t('main.layoutWorkbench') }[mode] }}
        </button>
      </div>
    </div>

    <div class="header-right">
      <button class="help-btn" @click="openHelp(helpKey)" :title="$t('help.buttonTitle')">?</button>
      <LanguageSwitcher />
      <template v-if="stepNum !== null">
        <div class="step-divider"></div>
        <div class="workflow-step">
          <span class="step-num">{{ $t('main.step') }} {{ stepNum }}/{{ stepTotal }}</span>
          <span class="step-name">{{ $tm('main.stepNames')[stepNameIndex] }}</span>
        </div>
        <div class="step-divider"></div>
        <span class="status-indicator" :class="statusClass">
          <span class="dot"></span>
          {{ statusText }}
        </span>
      </template>
    </div>
  </header>
</template>

<script setup>
import LanguageSwitcher from './LanguageSwitcher.vue'
import { useHelp } from '../composables/useHelp'

const { openHelp } = useHelp()

defineProps({
  helpKey: { type: String, required: true },
  viewMode: { type: String, default: null },
  stepNum: { type: Number, default: null },
  stepTotal: { type: Number, default: 5 },
  stepNameIndex: { type: Number, default: null },
  statusClass: { type: String, default: '' },
  statusText: { type: String, default: '' },
  backLabel: { type: String, default: null },
})

defineEmits(['brand-click', 'back-click', 'update:viewMode'])
</script>

<style scoped>
.app-header {
  height: 60px;
  border-bottom: 1px solid #EAEAEA;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  background: #FFF;
  z-index: 100;
  position: relative;
  flex-shrink: 0;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.header-center {
  position: absolute;
  left: 50%;
  transform: translateX(-50%);
}

.header-right {
  display: flex;
  align-items: center;
  gap: 16px;
}

.brand {
  font-family: 'JetBrains Mono', monospace;
  font-weight: 800;
  font-size: 18px;
  letter-spacing: 1px;
  cursor: pointer;
  color: #000;
}

.header-back-btn {
  background: none;
  border: none;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.75rem;
  color: #999;
  cursor: pointer;
  padding: 0;
}
.header-back-btn:hover { color: #000; }

.view-switcher {
  display: flex;
  background: #F5F5F5;
  padding: 4px;
  border-radius: 6px;
  gap: 4px;
}

.switch-btn {
  border: none;
  background: transparent;
  padding: 6px 16px;
  font-size: 12px;
  font-weight: 600;
  color: #666;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s;
}
.switch-btn.active {
  background: #FFF;
  color: #000;
  box-shadow: 0 2px 4px rgba(0,0,0,0.05);
}

.workflow-step {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
}

.step-num {
  font-family: 'JetBrains Mono', monospace;
  font-weight: 700;
  color: #999;
}

.step-name {
  font-weight: 700;
  color: #000;
}

.step-divider {
  width: 1px;
  height: 14px;
  background-color: #E0E0E0;
}

.status-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #666;
  font-weight: 500;
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #CCC;
}

.status-indicator.processing .dot { background: #FF5722; animation: pulse 1s infinite; }
.status-indicator.completed .dot { background: #4CAF50; }
.status-indicator.error .dot { background: #F44336; }

@keyframes pulse { 50% { opacity: 0.5; } }

.help-btn {
  background: none;
  border: 1px solid #ccc;
  color: #333;
  width: 28px;
  height: 28px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 14px;
  font-weight: 700;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: border-color 0.15s;
}
.help-btn:hover { border-color: #000; }
</style>
