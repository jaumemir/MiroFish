<template>
  <div class="project-detail-layout">
    <!-- NAV -->
    <div class="pd-navbar">
      <span class="pd-logo">🐟 MiroFish</span>
      <button class="pd-back-btn" @click="router.push({ name: 'Home' })">
        ← {{ t('projectDetail.backToHome') }}
      </button>
      <div class="pd-nav-right">
        <LanguageSwitcher />
      </div>
    </div>

    <div class="pd-body" v-if="detail">
      <!-- COLUMNA ESQUERRA -->
      <aside class="pd-sidebar">
        <!-- Nom projecte -->
        <div class="pd-card">
          <div class="pd-card-label">{{ t('projectDetail.project') }}</div>
          <div class="pd-project-name">{{ detail.project.name }}</div>
          <div class="pd-meta">{{ formatDate(detail.project.created_at) }}</div>
        </div>

        <!-- Pregunta simulació -->
        <div class="pd-card" v-if="detail.project.simulation_requirement">
          <div class="pd-card-label">{{ t('projectDetail.simulationQuestion') }}</div>
          <div class="pd-question">{{ detail.project.simulation_requirement }}</div>
        </div>

        <!-- Fitxer inicial -->
        <div class="pd-card" v-if="detail.files && detail.files.length">
          <div class="pd-card-label">{{ t('projectDetail.sourceFile') }}</div>
          <div class="pd-file-row" v-for="file in detail.files" :key="file.id">
            <span class="pd-filename">📄 {{ file.original_name }}</span>
            <button class="pd-btn-sm" @click="handleDownloadSource(file)">↓</button>
          </div>
        </div>

        <!-- Ontologia -->
        <div class="pd-card">
          <div class="pd-card-label">{{ t('projectDetail.ontology') }}</div>
          <div v-if="detail.ontology" class="pd-file-row">
            <span class="pd-filename">📋 ontology_v{{ detail.ontology.version }}.json</span>
            <button class="pd-btn-sm" @click="handleDownloadOntology">↓</button>
          </div>
          <div v-else class="pd-empty">{{ t('projectDetail.noOntology') }}</div>
          <label class="pd-btn pd-btn-upload">
            ⬆ {{ t('projectDetail.uploadNewOntology') }}
            <input type="file" accept=".json" style="display:none" @change="handleUploadOntology" />
          </label>
        </div>

        <!-- Graph base -->
        <div class="pd-card">
          <div class="pd-card-header">
            <div class="pd-card-label">{{ t('projectDetail.graphBase') }}</div>
            <span v-if="detail.graph" :class="['pd-badge', `pd-badge--${detail.graph.status}`]">
              {{ t(`projectDetail.graphStatus.${detail.graph.status}`) }}
            </span>
          </div>
          <template v-if="detail.graph">
            <div class="pd-meta">
              ID: {{ detail.graph.id.slice(0, 8) }}… · {{ detail.graph.node_count ?? '?' }} {{ t('projectDetail.entities') }}
            </div>
            <div class="pd-graph-actions">
              <button class="pd-btn" @click="handleViewGraph">👁 {{ t('projectDetail.viewGraph') }}</button>
              <button
                v-if="detail.graph.status === 'ready'"
                class="pd-btn pd-btn-danger"
                @click="handleForceRebuild"
              >↺ {{ t('projectDetail.forceRebuild') }}</button>
              <button
                v-if="detail.graph.status === 'failed'"
                class="pd-btn"
                @click="handleForceRebuild"
              >↺ {{ t('projectDetail.retry') }}</button>
            </div>
            <div v-if="detail.graph.status === 'building'" class="pd-progress">
              ⟳ {{ t('projectDetail.graphBuilding') }}
            </div>
          </template>
          <div v-else class="pd-empty">{{ t('projectDetail.noGraph') }}</div>
        </div>

        <!-- Mini-preview graph (si hi ha espai i el graph està llest) -->
        <div class="pd-graph-preview" v-if="detail.graph && detail.graph.status === 'ready' && graphData">
          <GraphPanel
            :graphData="graphData"
            :loading="graphLoading"
            :currentPhase="3"
            :isSimulating="false"
          />
        </div>
      </aside>

      <!-- COLUMNA DRETA -->
      <main class="pd-main">
        <div class="pd-sim-header">
          <h2 class="pd-sim-title">
            {{ t('projectDetail.simulations') }}
            <span class="pd-sim-count">({{ detail.simulations.length }})</span>
          </h2>
          <button class="pd-btn pd-btn-primary" @click="handleNewSimulation">
            + {{ t('projectDetail.newSimulation') }}
          </button>
        </div>

        <div v-if="!detail.simulations.length" class="pd-sim-empty">
          {{ t('projectDetail.noSimulations') }}
        </div>

        <div
          v-for="sim in detail.simulations"
          :key="sim.id"
          :class="['pd-sim-card', `pd-sim-card--${sim.status}`]"
        >
          <div class="pd-sim-card-header">
            <div class="pd-sim-card-title">
              {{ t('projectDetail.simulation') }} #{{ sim.ordinal }}
              <span :class="['pd-badge', statusBadgeClass(sim.status)]">
                {{ t(`projectDetail.status${capitalize(sim.status)}`) }}
              </span>
            </div>
            <div class="pd-sim-card-meta">
              {{ formatDate(sim.created_at) }} ·
              {{ sim.platform }} ·
              {{ sim.rounds_completed }}/{{ sim.rounds_total ?? '?' }} {{ t('projectDetail.rounds') }} ·
              Graph: {{ sim.graph_id ? sim.graph_id.slice(0, 8) + '…' : '—' }}
            </div>
          </div>

          <div class="pd-sim-card-actions">
            <!-- Completada / profiles_ready / config_ready -->
            <template v-if="['completed', 'profiles_ready', 'config_ready'].includes(sim.status)">
              <button class="pd-btn-sm" @click="handleAdjust(sim)">✏️ {{ t('projectDetail.adjust') }}</button>
              <button class="pd-btn-sm" @click="handleRegenerateReport(sim)">↺ {{ t('projectDetail.regenerateReport') }}</button>
              <button v-if="sim.report_id" class="pd-btn-sm pd-btn-interaction" @click="handleInteraction(sim)">
                💬 {{ t('projectDetail.interaction') }}
              </button>
              <button v-if="sim.report_id" class="pd-btn-sm" @click="handleDownloadMd(sim)">{{ t('projectDetail.downloadMd') }}</button>
              <button v-if="sim.report_id" class="pd-btn-sm" @click="handleDownloadPdf(sim)">{{ t('projectDetail.downloadPdf') }}</button>
              <button class="pd-btn-sm" @click="handleDownloadLog(sim)">{{ t('projectDetail.downloadLog') }}</button>
            </template>

            <!-- En curs -->
            <template v-else-if="sim.status === 'running'">
              <span class="pd-running-indicator">⟳ {{ sim.rounds_completed }}/{{ sim.rounds_total }}</span>
            </template>

            <!-- Error / failed -->
            <template v-else-if="['error', 'failed'].includes(sim.status)">
              <button class="pd-btn-sm" @click="handleAdjust(sim)">✏️ {{ t('projectDetail.adjust') }}</button>
            </template>

            <!-- Prepared -->
            <template v-else-if="sim.status === 'prepared'">
              <button class="pd-btn-sm" @click="handleAdjust(sim)">✏️ {{ t('projectDetail.adjust') }}</button>
            </template>

            <button class="pd-btn-sm pd-btn-danger" @click="handleDeleteSimulation(sim)">
              🗑 {{ t('projectDetail.delete') }}
            </button>
          </div>
        </div>
      </main>
    </div>

    <div v-else-if="loading" class="pd-loading">{{ t('common.loading') }}</div>
    <div v-else-if="error" class="pd-error">{{ error }}</div>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import LanguageSwitcher from '@/components/LanguageSwitcher.vue'
import GraphPanel from '@/components/GraphPanel.vue'
import { getGraphData } from '@/api/graph'
import {
  getProjectDetail,
  downloadProjectSource,
  downloadProjectOntology,
  uploadOntology,
  forceRebuildGraph,
  deleteSimulation,
  downloadReportMd,
  downloadReportPdf,
  downloadSimulationLog,
} from '@/api/project.js'

const props = defineProps({ projectId: String })
const router = useRouter()
const { t } = useI18n()

const detail = ref(null)
const loading = ref(true)
const error = ref(null)
const graphData = ref(null)
const graphLoading = ref(false)

async function loadDetail() {
  loading.value = true
  error.value = null
  try {
    detail.value = await getProjectDetail(props.projectId)
    if (detail.value?.graph?.status === 'ready' && detail.value.graph.id) {
      await loadGraphPreview(detail.value.graph.id)
    }
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

async function loadGraphPreview(graphId) {
  graphLoading.value = true
  try {
    const response = await getGraphData(graphId)
    if (response.success) {
      graphData.value = response.data
    }
  } catch (e) {
    console.warn('Graph preview load failed:', e)
  } finally {
    graphLoading.value = false
  }
}

function formatDate(iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleDateString()
}

async function handleDownloadSource(file) {
  try {
    await downloadProjectSource(props.projectId, file.original_name)
  } catch (e) {
    console.error('Download source failed:', e)
  }
}

async function handleDownloadOntology() {
  try {
    await downloadProjectOntology(props.projectId, detail.value.ontology?.version)
  } catch (e) {
    console.error('Download ontology failed:', e)
  }
}

async function handleUploadOntology(event) {
  const file = event.target.files[0]
  if (!file) return
  try {
    await uploadOntology(props.projectId, file)
    await loadDetail()
  } catch (e) {
    console.error('Upload ontology failed:', e)
  }
}

function handleViewGraph() {
  router.push({
    name: 'Process',
    params: { projectId: props.projectId },
    query: { step: '1', view: 'graph' },
    state: { backTo: `/project/${props.projectId}` },
  })
}

async function handleForceRebuild() {
  if (!confirm(t('projectDetail.confirmForceRebuild'))) return
  try {
    await forceRebuildGraph(props.projectId)
    graphData.value = null
    await loadDetail()
  } catch (e) {
    console.error('Force rebuild failed:', e)
  }
}

function handleNewSimulation() {
  router.push({
    name: 'Process',
    params: { projectId: props.projectId },
    query: { step: '2' },
    state: { backTo: `/project/${props.projectId}` },
  })
}

function handleAdjust(sim) {
  router.push({
    name: 'Process',
    params: { projectId: props.projectId },
    query: { mode: 'adjust', simulationId: sim.id },
    state: { backTo: `/project/${props.projectId}` },
  })
}

function handleRegenerateReport(sim) {
  router.push({
    name: 'Report',
    params: { reportId: sim.report_id || sim.id },
    query: { simulationId: sim.id },
    state: { backTo: `/project/${props.projectId}` },
  })
}

function handleInteraction(sim) {
  router.push({
    name: 'Interaction',
    params: { reportId: sim.report_id },
    state: { backTo: `/project/${props.projectId}` },
  })
}

async function handleDeleteSimulation(sim) {
  if (!confirm(t('projectDetail.confirmDelete'))) return
  try {
    await deleteSimulation(sim.id)
    await loadDetail()
  } catch (e) {
    console.error('Delete simulation failed:', e)
  }
}

async function handleDownloadMd(sim) {
  try {
    await downloadReportMd(sim.report_id)
  } catch (e) {
    console.error('Download MD failed:', e)
  }
}

async function handleDownloadPdf(sim) {
  try {
    await downloadReportPdf(sim.report_id)
  } catch (e) {
    console.error('Download PDF failed:', e)
  }
}

async function handleDownloadLog(sim) {
  try {
    await downloadSimulationLog(sim.id)
  } catch (e) {
    console.error('Download log failed:', e)
  }
}

function statusBadgeClass(status) {
  const map = {
    completed: 'pd-badge--ready',
    profiles_ready: 'pd-badge--ready',
    config_ready: 'pd-badge--ready',
    running: 'pd-badge--building',
    error: 'pd-badge--failed',
    failed: 'pd-badge--failed',
    prepared: 'pd-badge--prepared',
  }
  return map[status] || ''
}

function capitalize(str) {
  if (!str) return ''
  return str.charAt(0).toUpperCase() + str.slice(1)
}

onMounted(loadDetail)
</script>

<style scoped>
.project-detail-layout { display: flex; flex-direction: column; height: 100vh; background: #0f0f1e; color: #e0e0ff; font-family: 'JetBrains Mono', monospace; }
.pd-navbar { display: flex; align-items: center; justify-content: space-between; padding: 0.5rem 1rem; background: #1a1a2e; border-bottom: 1px solid #2a2a4a; flex-shrink: 0; }
.pd-navbar :deep(.switcher-trigger) { color: #ffffff; border-color: #555; }
.pd-logo { font-weight: bold; }
.pd-back-btn { background: transparent; border: none; color: #8080c0; cursor: pointer; font-size: 0.85rem; }
.pd-back-btn:hover { color: #c0c0ff; }
.pd-nav-right { display: flex; align-items: center; gap: 0.75rem; }
.pd-body { display: flex; flex: 1; overflow: hidden; }
.pd-sidebar { width: 340px; min-width: 280px; border-right: 1px solid #2a2a4a; overflow-y: auto; padding: 1rem; display: flex; flex-direction: column; gap: 0.75rem; }
.pd-main { flex: 1; overflow-y: auto; padding: 1rem; }
.pd-card { background: #1e1e30; border: 1px solid #2a2a4a; border-radius: 6px; padding: 0.75rem; }
.pd-card-label { font-size: 0.68rem; text-transform: uppercase; opacity: 0.5; margin-bottom: 0.35rem; letter-spacing: 0.05em; }
.pd-card-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.35rem; }
.pd-project-name { font-size: 1.05rem; font-weight: bold; }
.pd-question { font-size: 0.82rem; color: #b0b0d0; font-style: italic; }
.pd-meta { font-size: 0.72rem; opacity: 0.45; margin-top: 0.2rem; }
.pd-file-row { display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.35rem; }
.pd-filename { font-size: 0.8rem; color: #80c0ff; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 220px; }
.pd-empty { font-size: 0.75rem; opacity: 0.4; font-style: italic; margin-bottom: 0.35rem; }
.pd-btn { background: #1e2e3e; border: 1px solid #3a5a7a; color: #80c0ff; border-radius: 4px; padding: 0.3rem 0.7rem; cursor: pointer; font-size: 0.78rem; font-family: inherit; margin-top: 0.35rem; display: inline-block; }
.pd-btn:hover { background: #2a3e50; }
.pd-btn-sm { background: #1e2e3e; border: 1px solid #3a5a7a; color: #80c0ff; border-radius: 4px; padding: 0.15rem 0.4rem; cursor: pointer; font-size: 0.75rem; font-family: inherit; }
.pd-btn-upload { display: block; width: 100%; text-align: center; box-sizing: border-box; cursor: pointer; margin-top: 0.35rem; }
.pd-btn-danger { background: #2a1a1a; border-color: #7a3a3a; color: #ff8080; }
.pd-btn-danger:hover { background: #3a1a1a; }
.pd-graph-actions { display: flex; gap: 0.4rem; flex-wrap: wrap; margin-top: 0.4rem; }
.pd-progress { font-size: 0.75rem; color: #ffd080; margin-top: 0.4rem; }
.pd-badge { font-size: 0.68rem; padding: 0.1rem 0.4rem; border-radius: 10px; }
.pd-badge--ready { background: #1a3a1a; color: #80ff80; }
.pd-badge--building { background: #3a3a00; color: #ffd080; }
.pd-badge--failed { background: #3a1a1a; color: #ff8080; }
.pd-graph-preview { flex: 1; min-height: 150px; border: 1px solid #2a2a4a; border-radius: 6px; overflow: hidden; }
.pd-loading, .pd-error { padding: 2rem; text-align: center; opacity: 0.6; }
.pd-sim-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 1rem; }
.pd-sim-title { margin: 0; font-size: 1rem; color: #e0e0ff; }
.pd-sim-count { opacity: 0.4; font-weight: normal; font-size: 0.85rem; }
.pd-btn-primary { background: #1a3a6a; border-color: #4080c0; color: #80c0ff; }
.pd-btn-primary:hover { background: #2a4a7a; }
.pd-sim-empty { color: #6060a0; font-size: 0.85rem; text-align: center; padding: 2rem; }
.pd-sim-card { border: 1px solid #2a2a4a; border-radius: 8px; padding: 0.9rem; margin-bottom: 0.75rem; background: #111120; }
.pd-sim-card--completed, .pd-sim-card--profiles_ready, .pd-sim-card--config_ready { border-color: #2a5a2a; background: #0f1a0f; }
.pd-sim-card--running { border-color: #5a4a00; background: #1a1500; }
.pd-sim-card--error, .pd-sim-card--failed { border-color: #5a1a1a; background: #1a0f0f; }
.pd-sim-card-header { margin-bottom: 0.6rem; }
.pd-sim-card-title { font-size: 0.88rem; font-weight: bold; display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap; }
.pd-sim-card-meta { font-size: 0.72rem; opacity: 0.45; margin-top: 0.2rem; }
.pd-sim-card-actions { display: flex; gap: 0.35rem; flex-wrap: wrap; align-items: center; }
.pd-badge--prepared { background: #2a2a4a; color: #a0a0ff; }
.pd-btn-interaction { color: #ff80ff; border-color: #7a3a7a; }
.pd-running-indicator { font-size: 0.75rem; color: #ffd080; }
</style>
