<!-- frontend/src/components/HelpModal.vue -->
<template>
  <Teleport to="body">
    <div v-if="helpOpen" class="help-overlay" @click.self="closeHelp" @keydown.esc="closeHelp">
      <div class="help-modal" role="dialog" aria-modal="true">

        <!-- Header -->
        <div class="help-header">
          <span class="help-title">{{ $t('help.modalTitle') }}</span>
          <button class="help-close" @click="closeHelp">✕</button>
        </div>

        <!-- Body -->
        <div class="help-body">

          <!-- Sidebar -->
          <nav class="help-sidebar">
            <button
              v-for="sec in SECTIONS"
              :key="sec"
              class="sidebar-item"
              :class="{ active: helpSection === sec }"
              @click="helpSection = sec"
            >
              {{ $t('help.sections.' + sec) }}
            </button>
          </nav>

          <!-- Content -->
          <div class="help-content" ref="contentEl">
            <template v-if="currentSection">
              <h2 class="section-title">{{ currentSection.title }}</h2>
              <div v-for="(block, i) in currentSection.body" :key="i" class="block">

                <p v-if="block.type === 'p'" class="block-p">{{ block.text }}</p>

                <h3 v-else-if="block.type === 'h3'" class="block-h3">{{ block.text }}</h3>

                <ul v-else-if="block.type === 'list'" class="block-list">
                  <li v-for="(item, j) in block.items" :key="j">{{ item }}</li>
                </ul>

                <div v-else-if="block.type === 'table'" class="block-table-wrap">
                  <table class="block-table">
                    <thead>
                      <tr>
                        <th v-for="h in block.headers" :key="h">{{ h }}</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr v-for="(row, ri) in block.rows" :key="ri">
                        <td v-for="(cell, ci) in row" :key="ci">{{ cell }}</td>
                      </tr>
                    </tbody>
                  </table>
                </div>

                <div v-else-if="block.type === 'learnMore'" class="block-learn-more">
                  <span class="learn-more-label">{{ $t('help.learnMore') }}</span>
                  <a
                    v-for="link in block.links"
                    :key="link.url"
                    :href="link.url"
                    target="_blank"
                    rel="noopener noreferrer"
                    class="learn-more-link"
                  >{{ link.label }} ↗</a>
                </div>

              </div>
            </template>
          </div>

        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useHelp } from '../composables/useHelp'
import { helpContent, SECTIONS } from '../data/helpContent'

const { helpOpen, helpSection, closeHelp } = useHelp()
const { locale } = useI18n()
const contentEl = ref(null)

const currentSection = computed(() => {
  const lang = helpContent[locale.value] || helpContent['en']
  return lang[helpSection.value] || null
})

watch(helpSection, () => {
  if (contentEl.value) contentEl.value.scrollTop = 0
})
</script>

<style scoped>
.help-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
}

.help-modal {
  background: #fff;
  width: 840px;
  max-width: 95vw;
  height: 580px;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  font-family: 'Space Grotesk', system-ui, sans-serif;
}

.help-header {
  height: 48px;
  border-bottom: 1px solid #eaeaea;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  flex-shrink: 0;
}

.help-title {
  font-family: 'JetBrains Mono', monospace;
  font-weight: 800;
  font-size: 14px;
  letter-spacing: 1px;
}

.help-close {
  background: none;
  border: none;
  font-size: 16px;
  cursor: pointer;
  color: #999;
  padding: 4px 8px;
  transition: color 0.15s;
}
.help-close:hover { color: #000; }

.help-body {
  flex: 1;
  display: flex;
  overflow: hidden;
}

.help-sidebar {
  width: 188px;
  flex-shrink: 0;
  border-right: 1px solid #eaeaea;
  padding: 12px 0;
  overflow-y: auto;
}

.sidebar-item {
  display: block;
  width: 100%;
  text-align: left;
  background: none;
  border: none;
  padding: 8px 20px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  color: #666;
  cursor: pointer;
  transition: background 0.1s, color 0.1s;
  line-height: 1.4;
}
.sidebar-item:hover { background: #f5f5f5; color: #000; }
.sidebar-item.active { background: #f5f5f5; color: #000; font-weight: 700; border-left: 2px solid #ff4500; }

.help-content {
  flex: 1;
  overflow-y: auto;
  padding: 24px 28px;
}

.section-title {
  font-size: 18px;
  font-weight: 700;
  margin-bottom: 20px;
  color: #000;
}

.block { margin-bottom: 16px; }

.block-p {
  font-size: 13px;
  line-height: 1.65;
  color: #333;
}

.block-h3 {
  font-size: 13px;
  font-weight: 700;
  margin-top: 20px;
  margin-bottom: 8px;
  color: #000;
  font-family: 'JetBrains Mono', monospace;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.block-list {
  padding-left: 20px;
  font-size: 13px;
  line-height: 1.7;
  color: #333;
}
.block-list li { margin-bottom: 4px; }

.block-table-wrap {
  overflow-x: auto;
  margin-bottom: 4px;
}

.block-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
  font-family: 'JetBrains Mono', monospace;
}
.block-table th {
  background: #f5f5f5;
  text-align: left;
  padding: 6px 10px;
  font-weight: 700;
  border-bottom: 1px solid #ddd;
  color: #000;
}
.block-table td {
  padding: 5px 10px;
  border-bottom: 1px solid #f0f0f0;
  vertical-align: top;
  color: #333;
  line-height: 1.5;
}
.block-table tr:last-child td { border-bottom: none; }

.block-learn-more {
  margin-top: 24px;
  padding: 16px;
  border: 1px solid #eaeaea;
  background: #fafafa;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.learn-more-label {
  font-family: 'JetBrains Mono', monospace;
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 1px;
  color: #999;
}

.learn-more-link {
  font-size: 12px;
  color: #ff4500;
  text-decoration: none;
  font-family: 'JetBrains Mono', monospace;
}
.learn-more-link:hover { text-decoration: underline; }
</style>
