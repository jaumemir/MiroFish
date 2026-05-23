<template>
  <div class="main-view">
    <AppHeader
      :helpKey="currentStep === 1 ? 'step1' : 'step2'"
      :viewMode="viewMode"
      :stepNum="currentStep"
      :stepNameIndex="currentStep - 1"
      :statusClass="statusClass"
      :statusText="statusText"
      :backLabel="hasBackTo ? $t('projectDetail.backToProject') : null"
      @brand-click="navigateBack()"
      @back-click="navigateBack()"
      @update:viewMode="viewMode = $event"
    />

    <!-- Main Content Area -->
    <main class="content-area">
      <!-- Left Panel: Graph -->
      <div class="panel-wrapper left" :style="leftPanelStyle">
        <GraphPanel 
          :graphData="graphData"
          :loading="graphLoading"
          :currentPhase="currentPhase"
          @refresh="refreshGraph"
          @toggle-maximize="toggleMaximize('graph')"
        />
      </div>

      <!-- Right Panel: Step Components -->
      <div class="panel-wrapper right" :style="rightPanelStyle">
        <!-- Step 1: Graph Build -->
        <Step1GraphBuild
          v-if="currentStep === 1"
          :currentPhase="currentPhase"
          :ontologyReady="ontologyReady"
          :projectData="projectData"
          :ontologyProgress="ontologyProgress"
          :buildProgress="buildProgress"
          :graphData="graphData"
          :systemLogs="systemLogs"
          @next-step="handleNextStep"
          @proceed-to-graphrag="handleProceedToGraphRAG"
          @delete-ontology="handleDeleteOntology"
        />
        <!-- Step 2: Environment Setup -->
        <Step2EnvSetup
          v-else-if="currentStep === 2"
          :simulationId="isAdjustMode ? adjustSimulationId : null"
          :projectData="projectData"
          :graphData="graphData"
          :systemLogs="systemLogs"
          :adjustMode="isAdjustMode"
          :adjustProfiles="adjustData?.profiles ?? null"
          @go-back="handleGoBack"
          @next-step="handleNextStep"
          @add-log="addLog"
          @agents-updated="(agents) => { simulationAgents.value = agents }"
        />
        <!-- Step 3: Start Simulation (adjust mode) -->
        <Step3Simulation
          v-else-if="currentStep === 3"
          :simulationId="adjustSimulationId"
          :projectData="projectData"
          :graphData="graphData"
          :systemLogs="systemLogs"
          :adjustMode="isAdjustMode"
          :adjustConfig="adjustData?.config ?? null"
          :agents="simulationAgents"
          :maxRounds="simulationMaxRounds"
          @go-back="handleGoBack"
          @next-step="handleNextStep"
          @add-log="addLog"
        />
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import GraphPanel from '../components/GraphPanel.vue'
import Step1GraphBuild from '../components/Step1GraphBuild.vue'
import Step2EnvSetup from '../components/Step2EnvSetup.vue'
import Step3Simulation from '../components/Step3Simulation.vue'
import AppHeader from '../components/AppHeader.vue'
import { generateOntology, importOntology, getProject, buildGraph, getTaskStatus, getGraphData, deleteProject } from '../api/graph'
import { getPendingUpload, clearPendingUpload } from '../store/pendingUpload'
import { useBackTo } from '../composables/useBackTo.js'
import { getSimulationDetail } from '../api/project.js'

const route = useRoute()
const router = useRouter()
const { t, tm } = useI18n()
const { navigateBack } = useBackTo('Home')
const hasBackTo = ref(false)

// Layout State
const viewMode = ref('split') // graph | split | workbench

// Step State
const currentStep = ref(1) // 1: graph build, 2: env setup, 3: simulation, 4: report, 5: interaction
const stepNames = computed(() => tm('main.stepNames'))

// Data State
const currentProjectId = ref(route.params.projectId)
const loading = ref(false)
const graphLoading = ref(false)
const error = ref('')
const projectData = ref(null)
const graphData = ref(null)
const currentPhase = ref(-1) // -1: Upload, 0: Ontology, 1: Build, 2: Complete
const ontologyReady = ref(false) // true = ontology done but GraphRAG not yet started
const ontologyProgress = ref(null)
const buildProgress = ref(null)
const systemLogs = ref([])

// Polling timers
let pollTimer = null
let graphPollTimer = null

// Adjust mode
const isAdjustMode = computed(() => route.query.mode === 'adjust')
const adjustSimulationId = computed(() => route.query.simulationId)
const adjustData = ref(null)
const simulationMaxRounds = ref(null)

// Shared agent list: updated by Step2 so Step3 stays in sync (adjust mode)
const simulationAgents = ref([])

// --- Computed Layout Styles ---
const leftPanelStyle = computed(() => {
  if (viewMode.value === 'graph') return { width: '100%', opacity: 1, transform: 'translateX(0)' }
  if (viewMode.value === 'workbench') return { width: '0%', opacity: 0, transform: 'translateX(-20px)' }
  return { width: '50%', opacity: 1, transform: 'translateX(0)' }
})

const rightPanelStyle = computed(() => {
  if (viewMode.value === 'workbench') return { width: '100%', opacity: 1, transform: 'translateX(0)' }
  if (viewMode.value === 'graph') return { width: '0%', opacity: 0, transform: 'translateX(20px)' }
  return { width: '50%', opacity: 1, transform: 'translateX(0)' }
})

// --- Status Computed ---
const statusClass = computed(() => {
  if (error.value) return 'error'
  if (currentPhase.value >= 2) return 'completed'
  return 'processing'
})

const statusText = computed(() => {
  if (error.value) return 'Error'
  if (currentPhase.value >= 2) return 'Ready'
  if (currentPhase.value === 1) return 'Building Graph'
  if (currentPhase.value === 0) return 'Generating Ontology'
  return 'Initializing'
})

// --- Helpers ---
const addLog = (msg) => {
  const time = new Date().toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' }) + '.' + new Date().getMilliseconds().toString().padStart(3, '0')
  systemLogs.value.push({ time, msg })
  // Keep last 100 logs
  if (systemLogs.value.length > 100) {
    systemLogs.value.shift()
  }
}

// --- Layout Methods ---
const toggleMaximize = (target) => {
  if (viewMode.value === target) {
    viewMode.value = 'split'
  } else {
    viewMode.value = target
  }
}

const handleNextStep = (params = {}) => {
  if (currentStep.value < 5) {
    currentStep.value++
    addLog(t('log.enterStep', { step: currentStep.value, name: stepNames.value[currentStep.value - 1] }))
    
    // If entering Step 3 from Step 2, record simulation round config
    if (currentStep.value === 3 && params.maxRounds) {
      simulationMaxRounds.value = params.maxRounds
      addLog(t('log.customSimRounds', { rounds: params.maxRounds }))
    }
  }
}

const handleGoBack = () => {
  if (currentStep.value > 1) {
    currentStep.value--
    addLog(t('log.returnToStep', { step: currentStep.value, name: stepNames.value[currentStep.value - 1] }))
  }
}

// --- Data Logic ---

const initProject = async () => {
  addLog('Project view initialized.')
  if (currentProjectId.value === 'new') {
    await handleNewProject()
  } else {
    await loadProject()
  }

  // Adjust mode: load simulation detail and jump to step 2
  if (isAdjustMode.value && adjustSimulationId.value) {
    try {
      adjustData.value = await getSimulationDetail(adjustSimulationId.value)
      currentStep.value = 2
      if (adjustData.value?.profiles) {
        simulationAgents.value = adjustData.value.profiles
      }
      addLog(`Adjust mode: loaded simulation ${adjustSimulationId.value}`)
    } catch (e) {
      console.error('Failed to load simulation detail:', e)
      addLog(`Adjust mode: failed to load simulation detail`)
    }
  }
}

const handleNewProject = async () => {
  const pending = getPendingUpload()

  if (!pending.isPending) {
    return  // not a new-project session
  }

  if (pending.files.length === 0) {
    error.value = t('error.filesLostAfterRefresh')
    addLog(t('error.filesLostAfterRefresh'))
    clearPendingUpload()
    setTimeout(() => router.push('/'), 3000)
    return
  }

  try {
    loading.value = true
    currentPhase.value = 0
    ontologyProgress.value = { message: t('step1.analyzingDocs') }

    const formData = new FormData()
    pending.files.forEach(f => formData.append('files', f))
    formData.append('simulation_requirement', pending.simulationRequirement)

    let res
    if (pending.importOntologyMode && pending.ontologyFile) {
      addLog('Importing ontology from JSON file...')
      const ontologyText = await pending.ontologyFile.text()
      formData.append('ontology', ontologyText)
      res = await importOntology(formData)
    } else {
      addLog('Starting ontology generation: Uploading files...')
      res = await generateOntology(formData)
    }

    if (res.success) {
      clearPendingUpload()
      currentProjectId.value = res.data.project_id
      projectData.value = res.data

      router.replace({ name: 'Process', params: { projectId: res.data.project_id } })
      ontologyProgress.value = null
      addLog(`Ontology ready for project ${res.data.project_id}. Waiting for confirmation to build GraphRAG.`)
      ontologyReady.value = true
      // Do NOT auto-start build — user must click "Proceed to GraphRAG"
    } else {
      error.value = res.error || 'Ontology step failed'
      addLog(`Error: ${error.value}`)
    }
  } catch (err) {
    error.value = err.message
    addLog(`Exception in handleNewProject: ${err.message}`)
  } finally {
    loading.value = false
  }
}

const loadProject = async () => {
  try {
    loading.value = true
    addLog(`Loading project ${currentProjectId.value}...`)
    const res = await getProject(currentProjectId.value)
    if (res.success) {
      projectData.value = res.data
      updatePhaseByStatus(res.data.status)
      if (res.data.ontology) ontologyReady.value = true
      addLog(`Project loaded. Status: ${res.data.status}`)
      
      const canRetryBuild = (
        (res.data.status === 'ontology_generated' && !res.data.graph_id) ||
        (res.data.status === 'failed' && res.data.ontology && !res.data.graph_id)
      )
      if (canRetryBuild) {
        await startBuildGraph()
      } else if (res.data.status === 'graph_building') {
        const taskId = res.data.active_task_id || res.data.graph_build_task_id
        if (taskId) {
          currentPhase.value = 1
          addLog(t('log.reconnectingToTask', { taskId }))
          startPollingTask(taskId)
          startGraphPolling()
        }
      } else if ((res.data.status === 'graph_completed' || res.data.status === 'failed') && res.data.graph_id) {
        currentPhase.value = 2
        await loadGraph(res.data.graph_id)
      }
    } else {
      error.value = res.error
      addLog(`Error loading project: ${res.error}`)
    }
  } catch (err) {
    error.value = err.message
    addLog(`Exception in loadProject: ${err.message}`)
  } finally {
    loading.value = false
  }
}

const updatePhaseByStatus = (status) => {
  switch (status) {
    case 'created':
    case 'ontology_generated': currentPhase.value = 0; break;
    case 'graph_building': currentPhase.value = 1; break;
    case 'graph_completed': currentPhase.value = 2; break;
    case 'failed': {
      const data = projectData.value
      if (data?.ontology && !data?.graph_id) {
        currentPhase.value = 0  // Recuperar a fase d'ontologia per reintentar
      } else if (data?.graph_id) {
        currentPhase.value = 2
      } else {
        currentPhase.value = 0
        error.value = 'Project failed'
      }
      break
    }
  }
}

const startBuildGraph = async () => {
  try {
    currentPhase.value = 1
    buildProgress.value = { progress: 0, message: 'Starting build...' }
    addLog('Initiating graph build...')
    
    const res = await buildGraph({ project_id: currentProjectId.value })
    if (res.success) {
      addLog(`Graph build task started. Task ID: ${res.data.task_id}`)
      startGraphPolling()
      startPollingTask(res.data.task_id)
    } else {
      error.value = res.error
      addLog(`Error starting build: ${res.error}`)
    }
  } catch (err) {
    error.value = err.message
    addLog(`Exception in startBuildGraph: ${err.message}`)
  }
}

const startGraphPolling = () => {
  addLog('Started polling for graph data...')
  fetchGraphData()
  graphPollTimer = setInterval(fetchGraphData, 10000)
}

const fetchGraphData = async () => {
  try {
    // Refresh project info to check for graph_id
    const projRes = await getProject(currentProjectId.value)
    if (projRes.success && projRes.data.graph_id) {
      const gRes = await getGraphData(projRes.data.graph_id)
      if (gRes.success) {
        graphData.value = gRes.data
        const nodeCount = gRes.data.node_count || gRes.data.nodes?.length || 0
        const edgeCount = gRes.data.edge_count || gRes.data.edges?.length || 0
        addLog(`Graph data refreshed. Nodes: ${nodeCount}, Edges: ${edgeCount}`)
      }
    }
  } catch (err) {
    console.warn('Graph fetch error:', err)
  }
}

const startPollingTask = (taskId) => {
  pollTaskStatus(taskId)
  pollTimer = setInterval(() => pollTaskStatus(taskId), 2000)
}

const pollTaskStatus = async (taskId) => {
  try {
    const res = await getTaskStatus(taskId)
    if (res.success) {
      const task = res.data
      
      // Log progress message if it changed
      if (task.message && task.message !== buildProgress.value?.message) {
        addLog(task.message)
      }
      
      buildProgress.value = { progress: task.progress || 0, message: task.message }
      
      if (task.status === 'completed') {
        addLog('Graph build task completed.')
        stopPolling()
        stopGraphPolling() // Stop polling, do final load
        currentPhase.value = 2
        
        // Final load
        const projRes = await getProject(currentProjectId.value)
        if (projRes.success && projRes.data.graph_id) {
            projectData.value = projRes.data
            await loadGraph(projRes.data.graph_id)
        }
      } else if (task.status === 'failed') {
        stopPolling()
        error.value = task.error
        addLog(`Graph build task failed: ${task.error}`)
      }
    }
  } catch (e) {
    console.error(e)
  }
}

const loadGraph = async (graphId) => {
  graphLoading.value = true
  addLog(`Loading full graph data: ${graphId}`)
  try {
    const res = await getGraphData(graphId)
    if (res.success) {
      graphData.value = res.data
      addLog('Graph data loaded successfully.')
    } else {
      addLog(`Failed to load graph data: ${res.error}`)
    }
  } catch (e) {
    addLog(`Exception loading graph: ${e.message}`)
  } finally {
    graphLoading.value = false
  }
}

const refreshGraph = () => {
  if (projectData.value?.graph_id) {
    addLog('Manual graph refresh triggered.')
    loadGraph(projectData.value.graph_id)
  }
}

const stopPolling = () => {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

const stopGraphPolling = () => {
  if (graphPollTimer) {
    clearInterval(graphPollTimer)
    graphPollTimer = null
    addLog('Graph polling stopped.')
  }
}

const handleProceedToGraphRAG = async () => {
  ontologyReady.value = false
  addLog('User confirmed: starting GraphRAG build...')
  await startBuildGraph()
}

const handleDeleteOntology = async () => {
  if (!currentProjectId.value || currentProjectId.value === 'new') return
  addLog(`Deleting project ${currentProjectId.value}...`)
  try {
    await deleteProject(currentProjectId.value)
    addLog('Project deleted. Returning to home.')
    router.push('/')
  } catch (err) {
    addLog(`Error deleting project: ${err.message}`)
  }
}

onMounted(() => {
  hasBackTo.value = !!history.state?.backTo
  initProject()
})

onUnmounted(() => {
  stopPolling()
  stopGraphPolling()
})
</script>

<style scoped>
.main-view {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: #FFF;
  overflow: hidden;
  font-family: 'Space Grotesk', 'Noto Sans SC', system-ui, sans-serif;
}

/* Content */
.content-area {
  flex: 1;
  display: flex;
  position: relative;
  overflow: hidden;
}

.panel-wrapper {
  height: 100%;
  overflow: hidden;
  transition: width 0.4s cubic-bezier(0.25, 0.8, 0.25, 1), opacity 0.3s ease, transform 0.3s ease;
  will-change: width, opacity, transform;
}

.panel-wrapper.left {
  border-right: 1px solid #EAEAEA;
}

</style>
