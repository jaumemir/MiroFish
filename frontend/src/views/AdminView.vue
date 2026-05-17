<template>
  <div class="admin-container">
    <nav class="navbar">
      <div class="nav-brand">MIROFISH</div>
      <div class="nav-right">
        <router-link to="/" class="back-link">← {{ $t('common.back') }}</router-link>
        <LanguageSwitcher />
      </div>
    </nav>

    <div class="content">
      <div class="tabs">
        <router-link to="/admin/users"      class="tab" :class="{ active: tab === 'users' }">
          {{ $t('admin.users') }}
        </router-link>
        <router-link to="/admin/projects"   class="tab" :class="{ active: tab === 'projects' }">
          {{ $t('admin.projects') }}
        </router-link>
        <router-link to="/admin/config"     class="tab" :class="{ active: tab === 'config' }">
          {{ $t('admin.config') }}
        </router-link>
        <router-link to="/admin/executions" class="tab" :class="{ active: tab === 'executions' }">
          {{ $t('admin.executions') }}
        </router-link>
      </div>

      <!-- Tab: Usuaris -->
      <div v-if="tab === 'users'" class="tab-content">
        <div class="tab-header">
          <h2 class="section-title">{{ $t('admin.users') }}</h2>
          <button class="new-btn" @click="showInviteForm = !showInviteForm">
            + {{ $t('admin.inviteUser') }}
          </button>
        </div>

        <div v-if="showInviteForm" class="invite-form">
          <div class="form-row">
            <input v-model="invite.name" class="field-input" :placeholder="$t('admin.name')" />
            <input v-model="invite.email" type="email" class="field-input" :placeholder="$t('admin.email')" />
            <select v-model="invite.role" class="field-select">
              <option value="user">User</option>
              <option value="admin">Admin</option>
            </select>
            <button class="start-btn" @click="submitInvite" :disabled="!invite.email || !invite.name">
              {{ $t('admin.send') }} →
            </button>
          </div>
          <div v-if="inviteSuccess" class="success-msg">{{ $t('admin.inviteSent') }}</div>
          <div v-if="inviteError" class="error-msg">{{ inviteError }}</div>
        </div>

        <table class="data-table" v-if="users.length">
          <thead>
            <tr>
              <th>{{ $t('admin.email') }}</th>
              <th>{{ $t('admin.name') }}</th>
              <th>{{ $t('admin.role') }}</th>
              <th>{{ $t('admin.status') }}</th>
              <th>{{ $t('admin.created') }}</th>
              <th>{{ $t('admin.actions') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="user in users" :key="user.id">
              <td class="mono">{{ user.email }}</td>
              <td>{{ user.name }}</td>
              <td>
                <select class="role-select" :value="user.role" @change="changeRole(user, $event.target.value)">
                  <option value="user">user</option>
                  <option value="admin">admin</option>
                </select>
              </td>
              <td><span class="status-badge" :class="user.status">{{ user.status }}</span></td>
              <td class="mono">{{ formatDate(user.created_at) }}</td>
              <td class="actions-cell">
                <button v-if="user.status === 'pending'" class="action-btn" @click="reinvite(user)" :title="$t('admin.reinvite')">✉</button>
                <button v-if="user.status !== 'disabled'" class="action-btn danger" @click="disableUser(user)" :title="$t('admin.disable')">✕</button>
                <button v-if="user.status === 'disabled'" class="action-btn" @click="enableUser(user)" :title="$t('admin.enableUser')">✓</button>
                <button v-if="user.status === 'disabled'" class="action-btn danger" @click="openDeleteModal(user)" :title="$t('admin.deleteUser')">🗑</button>
              </td>
            </tr>
          </tbody>
        </table>
        <div v-else class="empty-state">{{ $t('admin.noUsers') }}</div>
        <div v-if="deleteSuccess" class="success-msg">{{ $t('admin.deleteUserSuccess') }}</div>
      </div>

      <!-- Tab: Projectes -->
      <div v-if="tab === 'projects'" class="tab-content">
        <div class="tab-header">
          <h2 class="section-title">{{ $t('admin.projects') }}</h2>
        </div>
        <table class="data-table" v-if="projects.length">
          <thead>
            <tr>
              <th>{{ $t('admin.project') }}</th>
              <th>{{ $t('admin.owner') }}</th>
              <th>{{ $t('admin.simulations') }}</th>
              <th>{{ $t('admin.status') }}</th>
              <th>{{ $t('admin.created') }}</th>
              <th>{{ $t('admin.actions') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="proj in projects" :key="proj.project_id">
              <td>{{ proj.name }}</td>
              <td class="mono">{{ proj.owner_email || '—' }}</td>
              <td class="mono">{{ proj.simulation_count }}</td>
              <td><span class="status-badge" :class="proj.status">{{ proj.status }}</span></td>
              <td class="mono">{{ formatDate(proj.created_at) }}</td>
              <td>
                <button class="action-btn" @click="openProjectDetail(proj.project_id)">
                  {{ $t('admin.detail') }}
                </button>
              </td>
            </tr>
          </tbody>
        </table>
        <div v-else class="empty-state">{{ $t('admin.noProjects') }}</div>
      </div>

      <!-- Tab: Configuració -->
      <div v-if="tab === 'config'" class="tab-content">
        <div class="tab-header">
          <h2 class="section-title">{{ $t('admin.config') }}</h2>
          <button class="start-btn" @click="saveConfig">{{ $t('common.save') }}</button>
        </div>
        <div v-if="configEntries.length" class="config-form">
          <div v-for="entry in configEntries" :key="entry.key" class="config-row">
            <label class="config-label">
              <span class="config-key mono">{{ entry.key }}</span>
              <span class="config-desc">{{ entry.label }}</span>
            </label>
            <input
              v-model="configValues[entry.key]"
              :type="entry.is_secret ? 'password' : 'text'"
              class="field-input"
              :placeholder="entry.is_secret ? '●●●●' : entry.value"
            />
          </div>
        </div>
        <div v-else class="empty-state">{{ $t('admin.noConfig') }}</div>
        <div v-if="configSaved" class="success-msg">{{ $t('admin.configSaved') }}</div>
      </div>

      <!-- Tab: Historial -->
      <div v-if="tab === 'executions'" class="tab-content">
        <div class="tab-header">
          <h2 class="section-title">{{ $t('admin.executions') }}</h2>
        </div>
        <table class="data-table" v-if="executions.length">
          <thead>
            <tr>
              <th>{{ $t('admin.user') }}</th>
              <th>{{ $t('admin.project') }}</th>
              <th>{{ $t('admin.platform') }}</th>
              <th>{{ $t('admin.status') }}</th>
              <th>{{ $t('admin.rounds') }}</th>
              <th>{{ $t('admin.created') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="ex in executions" :key="ex.simulation_id">
              <td class="mono">{{ ex.user_email || '—' }}</td>
              <td>{{ ex.project_name }}</td>
              <td class="mono">{{ ex.platform }}</td>
              <td><span class="status-badge" :class="ex.status">{{ ex.status }}</span></td>
              <td class="mono">{{ ex.rounds_completed }}/{{ ex.rounds_total || '?' }}</td>
              <td class="mono">{{ formatDate(ex.created_at) }}</td>
            </tr>
          </tbody>
        </table>
        <div v-else class="empty-state">{{ $t('admin.noExecutions') }}</div>
      </div>
    </div>
  </div>

<!-- Modal de detall de projecte (admin) -->
<div v-if="showProjectModal" class="modal-overlay">
  <div class="modal-box project-detail-modal">
    <div class="modal-header">
      <h3 class="modal-title">{{ $t('admin.projectDetail') }}</h3>
      <button class="modal-close-btn" @click="showProjectModal = false">×</button>
    </div>

    <div v-if="projectDetailLoading" class="empty-state">{{ $t('common.loading') }}</div>
    <div v-else-if="projectDetailError" class="error-msg">{{ projectDetailError }}</div>
    <template v-else-if="projectDetail">
      <!-- Capçalera projecte -->
      <div class="detail-section">
        <div class="detail-row">
          <span class="detail-label">{{ $t('admin.projectId') }}</span>
          <span class="mono detail-value">{{ projectDetail.project_id }}</span>
        </div>
        <div class="detail-row">
          <span class="detail-label">{{ $t('admin.owner') }}</span>
          <span class="mono detail-value">{{ projectDetail.owner_email || '—' }}</span>
        </div>
        <div class="detail-row">
          <span class="detail-label">{{ $t('admin.status') }}</span>
          <span class="status-badge" :class="projectDetail.status">{{ projectDetail.status }}</span>
        </div>
      </div>

      <!-- Grafs -->
      <div class="detail-section">
        <h4 class="detail-section-title">{{ $t('admin.graphs') }}</h4>
        <table class="data-table" v-if="projectDetail.graphs.length">
          <thead>
            <tr>
              <th>{{ $t('admin.graphId') }}</th>
              <th>{{ $t('admin.externalId') }}</th>
              <th>{{ $t('admin.backend') }}</th>
              <th>{{ $t('admin.status') }}</th>
              <th>{{ $t('admin.nodeCount') }}</th>
              <th>{{ $t('admin.edgeCount') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="g in projectDetail.graphs" :key="g.graph_id">
              <td class="mono">{{ g.graph_id }}</td>
              <td class="mono">{{ g.external_id || '—' }}</td>
              <td class="mono">{{ g.backend }}</td>
              <td><span class="status-badge" :class="g.status">{{ g.status }}</span></td>
              <td class="mono">{{ g.node_count ?? '—' }}</td>
              <td class="mono">{{ g.edge_count ?? '—' }}</td>
            </tr>
          </tbody>
        </table>
        <div v-else class="empty-state-sm">—</div>
      </div>

      <!-- Simulacions -->
      <div class="detail-section">
        <h4 class="detail-section-title">{{ $t('admin.simulations') }}</h4>
        <div v-if="simDeleteSuccess" class="success-msg">{{ $t('admin.deleteSimulationSuccess') }}</div>
        <table class="data-table" v-if="projectDetail.simulations.length">
          <thead>
            <tr>
              <th>{{ $t('admin.simulationId') }}</th>
              <th>{{ $t('admin.graphId') }}</th>
              <th>{{ $t('admin.status') }}</th>
              <th>{{ $t('admin.platform') }}</th>
              <th>{{ $t('admin.rounds') }}</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="s in projectDetail.simulations" :key="s.simulation_id">
              <td class="mono">{{ s.simulation_id }}</td>
              <td class="mono">{{ s.graph_id || '—' }}</td>
              <td><span class="status-badge" :class="s.status">{{ s.status }}</span></td>
              <td class="mono">{{ s.platform }}</td>
              <td class="mono">{{ s.rounds_completed }}/{{ s.rounds_total || '?' }}</td>
              <td>
                <template v-if="simDeleteConfirm === s.simulation_id">
                  <span class="confirm-inline">
                    {{ $t('admin.deleteSimulationConfirm') }}
                    <button class="action-btn danger" @click="deleteSimulation(s.simulation_id)">
                      {{ $t('admin.confirmYes') }}
                    </button>
                    <button class="action-btn" @click="simDeleteConfirm = null">
                      {{ $t('admin.confirmNo') }}
                    </button>
                  </span>
                </template>
                <button v-else class="action-btn danger"
                        @click="simDeleteConfirm = s.simulation_id">
                  {{ $t('admin.deleteSimulation') }}
                </button>
              </td>
            </tr>
          </tbody>
        </table>
        <div v-else class="empty-state-sm">—</div>
      </div>

      <!-- Eliminar projecte -->
      <div class="detail-section danger-zone">
        <h4 class="detail-section-title danger-title">{{ $t('admin.deleteProject') }}</h4>
        <p class="danger-hint">{{ $t('admin.deleteProjectConfirmLabel') }}: <strong>{{ projectDetail.name }}</strong></p>
        <div class="form-row">
          <input v-model="projectDeleteConfirmInput" class="field-input"
                 :placeholder="projectDetail.name" />
          <button class="start-btn danger"
                  :disabled="projectDeleteConfirmInput !== projectDetail.name || projectDeleteLoading"
                  @click="deleteAdminProject">
            {{ projectDeleteLoading ? $t('common.loading') : $t('admin.deleteProject') }}
          </button>
        </div>
        <div v-if="projectDeleteError" class="error-msg">{{ projectDeleteError }}</div>
      </div>
    </template>
  </div>
</div>

<div v-if="projectDeleteSuccess" class="toast-success">{{ $t('admin.deleteProjectSuccess') }}</div>

<!-- Modal d'esborrament d'usuari -->
<div v-if="deleteModal.open" class="modal-overlay">
  <div class="modal-box">
    <h3 class="modal-title">{{ $t('admin.deleteUserTitle') }}</h3>
    <p class="modal-warning">
      {{ $t('admin.deleteUserWarning', { name: deleteModal.user?.name, email: deleteModal.user?.email }) }}
    </p>
    <input
      v-model="deleteModal.confirmEmail"
      type="email"
      class="field-input"
      :placeholder="$t('admin.deleteUserConfirmPlaceholder')"
    />
    <div v-if="deleteModal.error" class="error-msg">{{ deleteModal.error }}</div>
    <div class="modal-actions">
      <button class="action-btn" @click="closeDeleteModal">{{ $t('common.cancel') }}</button>
      <button
        class="start-btn danger"
        :disabled="deleteModal.confirmEmail !== deleteModal.user?.email || deleteModal.loading"
        @click="confirmDelete"
      >
        {{ deleteModal.loading ? $t('common.loading') : $t('admin.deleteUserConfirm') }}
      </button>
    </div>
  </div>
</div>
</template>

<script setup>
import { ref, watch, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import LanguageSwitcher from '../components/LanguageSwitcher.vue'
import service from '../api/index'

const props = defineProps({ tab: { type: String, default: 'users' } })
const { t } = useI18n()

const users = ref([])
const showInviteForm = ref(false)
const invite = ref({ name: '', email: '', role: 'user' })
const inviteSuccess = ref(false)
const inviteError = ref('')
const deleteSuccess = ref(false)

const deleteModal = ref({
  open: false,
  user: null,
  confirmEmail: '',
  loading: false,
  error: ''
})

const configEntries = ref([])
const configValues = ref({})
const configSaved = ref(false)

const executions = ref([])

const projects = ref([])
const projectDetail = ref(null)
const projectDetailLoading = ref(false)
const projectDetailError = ref('')
const showProjectModal = ref(false)

const simDeleteConfirm = ref(null)   // simulation_id waiting for confirmation
const simDeleteSuccess = ref('')
const projectDeleteConfirmInput = ref('')
const projectDeleteSuccess = ref(false)
const projectDeleteError = ref('')
const projectDeleteLoading = ref(false)

onMounted(loadTab)
watch(() => props.tab, loadTab)

async function loadTab() {
  if (props.tab === 'users') await loadUsers()
  if (props.tab === 'projects') await loadProjects()
  if (props.tab === 'config') await loadConfig()
  if (props.tab === 'executions') await loadExecutions()
}

async function loadUsers() {
  try {
    const res = await service.get('/api/users/')
    users.value = res.data || []
  } catch { /* silent */ }
}

async function loadConfig() {
  try {
    const res = await service.get('/api/admin/config')
    configEntries.value = res.data || []
    configValues.value = Object.fromEntries(
      configEntries.value.filter(e => !e.is_secret).map(e => [e.key, e.value])
    )
  } catch { /* silent */ }
}

async function loadExecutions() {
  try {
    const res = await service.get('/api/admin/executions')
    executions.value = res.data || []
  } catch { /* silent */ }
}

async function loadProjects() {
  try {
    const res = await service.get('/api/admin/projects')
    projects.value = res.data?.data || []
  } catch { /* silent */ }
}

async function deleteSimulation(simulationId) {
  try {
    await service.delete(`/api/admin/simulations/${simulationId}`)
    simDeleteConfirm.value = null
    simDeleteSuccess.value = simulationId
    setTimeout(() => { simDeleteSuccess.value = '' }, 2000)
    const res = await service.get(`/api/admin/projects/${projectDetail.value.project_id}`)
    projectDetail.value = res.data?.data || projectDetail.value
  } catch { /* silent */ }
}

async function deleteAdminProject() {
  if (projectDeleteConfirmInput.value !== projectDetail.value?.name) return
  projectDeleteLoading.value = true
  projectDeleteError.value = ''
  try {
    await service.delete(`/api/admin/projects/${projectDetail.value.project_id}`)
    showProjectModal.value = false
    projectDetail.value = null
    projectDeleteConfirmInput.value = ''
    projectDeleteSuccess.value = true
    setTimeout(() => { projectDeleteSuccess.value = false }, 3000)
    await loadProjects()
  } catch (e) {
    projectDeleteError.value = e.response?.data?.error || t('common.unknownError')
  } finally {
    projectDeleteLoading.value = false
  }
}

async function openProjectDetail(projectId) {
  projectDetail.value = null
  projectDetailError.value = ''
  projectDetailLoading.value = true
  showProjectModal.value = true
  projectDeleteConfirmInput.value = ''
  simDeleteConfirm.value = null
  try {
    const res = await service.get(`/api/admin/projects/${projectId}`)
    projectDetail.value = res.data?.data || null
  } catch {
    projectDetailError.value = t('common.unknownError')
  } finally {
    projectDetailLoading.value = false
  }
}

async function submitInvite() {
  inviteSuccess.value = false; inviteError.value = ''
  try {
    await service.post('/api/users/', invite.value)
    inviteSuccess.value = true
    invite.value = { name: '', email: '', role: 'user' }
    await loadUsers()
  } catch (e) {
    inviteError.value = e.response?.data?.error || t('common.unknownError')
  }
}

async function changeRole(user, newRole) {
  await service.patch(`/api/users/${user.id}`, { role: newRole })
  await loadUsers()
}

async function disableUser(user) {
  await service.delete(`/api/users/${user.id}`)
  await loadUsers()
}

async function enableUser(user) {
  await service.patch(`/api/users/${user.id}`, { status: 'active' })
  await loadUsers()
}

function openDeleteModal(user) {
  deleteModal.value = { open: true, user, confirmEmail: '', loading: false, error: '' }
}

function closeDeleteModal() {
  deleteModal.value.open = false
}

async function confirmDelete() {
  deleteModal.value.loading = true
  deleteModal.value.error = ''
  try {
    await service.delete(`/api/users/${deleteModal.value.user.id}/purge`)
    deleteModal.value.open = false
    await loadUsers()
    deleteSuccess.value = true
    setTimeout(() => { deleteSuccess.value = false }, 3000)
  } catch (e) {
    deleteModal.value.error = e?.response?.data?.error || t('common.unknownError')
  } finally {
    deleteModal.value.loading = false
  }
}

async function reinvite(user) {
  await service.post(`/api/users/${user.id}/reinvite`)
}

async function saveConfig() {
  const payload = {}
  for (const [k, v] of Object.entries(configValues.value)) {
    if (v !== '' && !configEntries.value.find(e => e.key === k)?.is_secret) {
      payload[k] = v
    }
  }
  await service.patch('/api/admin/config', payload)
  configSaved.value = true
  setTimeout(() => { configSaved.value = false }, 2000)
}

function formatDate(iso) {
  return iso ? new Date(iso).toLocaleDateString() : '—'
}
</script>

<style scoped>
.admin-container { min-height: 100vh; background: #fff; font-family: 'Space Grotesk', system-ui, sans-serif; color: #000; }
.navbar { height: 60px; background: #000; color: #fff; display: flex; justify-content: space-between; align-items: center; padding: 0 40px; }
.nav-brand { font-family: 'JetBrains Mono', monospace; font-weight: 800; letter-spacing: 1px; font-size: 1.2rem; }
.nav-right { display: flex; align-items: center; gap: 16px; }
.back-link { color: #aaa; font-family: 'JetBrains Mono', monospace; font-size: 0.8rem; text-decoration: none; }
.back-link:hover { color: #fff; }
.content { max-width: 1100px; margin: 0 auto; padding: 40px; }
.tabs { display: flex; gap: 0; border-bottom: 1px solid #e5e5e5; margin-bottom: 32px; }
.tab { padding: 12px 24px; font-family: 'JetBrains Mono', monospace; font-size: 0.85rem; font-weight: 700; text-decoration: none; color: #666; border-bottom: 2px solid transparent; transition: all 0.15s; }
.tab:hover { color: #000; }
.tab.active { color: #000; border-bottom-color: #ff4500; }
.tab-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; }
.section-title { font-size: 1.2rem; font-weight: 500; margin: 0; }
.new-btn, .start-btn { background: #000; color: #fff; border: none; padding: 8px 18px; font-family: 'JetBrains Mono', monospace; font-size: 0.8rem; font-weight: 700; cursor: pointer; transition: background 0.15s; }
.new-btn:hover, .start-btn:hover:not(:disabled) { background: #ff4500; }
.start-btn:disabled { background: #e5e5e5; color: #999; cursor: not-allowed; }
.invite-form { border: 1px solid #e5e5e5; padding: 20px; margin-bottom: 24px; background: #fafafa; }
.form-row { display: flex; gap: 12px; flex-wrap: wrap; }
.field-input { border: 1px solid #e5e5e5; background: #fff; padding: 8px 12px; font-family: 'JetBrains Mono', monospace; font-size: 0.85rem; outline: none; flex: 1; min-width: 160px; }
.field-input:focus { border-color: #000; }
.field-select { border: 1px solid #e5e5e5; background: #fff; padding: 8px 12px; font-family: 'JetBrains Mono', monospace; font-size: 0.85rem; cursor: pointer; }
.data-table { width: 100%; border-collapse: collapse; font-size: 0.9rem; }
.data-table th { font-family: 'JetBrains Mono', monospace; font-size: 0.72rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; color: #666; padding: 10px 12px; text-align: left; border-bottom: 1px solid #e5e5e5; }
.data-table td { padding: 12px; border-bottom: 1px solid #f0f0f0; }
.mono { font-family: 'JetBrains Mono', monospace; font-size: 0.85rem; }
.status-badge { display: inline-block; font-family: 'JetBrains Mono', monospace; font-size: 0.72rem; font-weight: 700; padding: 2px 8px; }
.status-badge.active { background: #dcfce7; color: #166534; }
.status-badge.pending { background: #fef9c3; color: #854d0e; }
.status-badge.disabled { background: #f1f5f9; color: #64748b; }
.status-badge.completed { background: #dcfce7; color: #166534; }
.status-badge.failed { background: #fee2e2; color: #991b1b; }
.role-select { border: 1px solid #e5e5e5; background: #fff; padding: 4px 8px; font-family: 'JetBrains Mono', monospace; font-size: 0.8rem; cursor: pointer; }
.actions-cell { display: flex; gap: 6px; }
.action-btn { background: none; border: 1px solid #e5e5e5; padding: 4px 8px; font-size: 0.85rem; cursor: pointer; }
.action-btn:hover { border-color: #000; }
.action-btn.danger { border-color: #fca5a5; color: #dc2626; }
.action-btn.danger:hover { border-color: #ef4444; color: #ef4444; }
.config-form { display: flex; flex-direction: column; gap: 16px; }
.config-row { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; align-items: center; padding: 12px 0; border-bottom: 1px solid #f0f0f0; }
.config-label { display: flex; flex-direction: column; gap: 2px; }
.config-key { font-size: 0.8rem; color: #000; }
.config-desc { font-size: 0.8rem; color: #666; }
.empty-state { padding: 48px 0; text-align: center; font-family: 'JetBrains Mono', monospace; font-size: 0.85rem; color: #999; }
.success-msg { font-family: 'JetBrains Mono', monospace; font-size: 0.8rem; color: #22c55e; border-left: 3px solid #22c55e; padding-left: 10px; margin-top: 8px; }
.error-msg { font-family: 'JetBrains Mono', monospace; font-size: 0.8rem; color: #ff4500; border-left: 3px solid #ff4500; padding-left: 10px; margin-top: 8px; }
.modal-overlay {
  position: fixed; inset: 0; background: rgba(0,0,0,0.4);
  display: flex; align-items: center; justify-content: center; z-index: 100;
}
.modal-box {
  background: #fff; padding: 32px; max-width: 480px; width: 90%;
  border: 1px solid #e5e5e5; display: flex; flex-direction: column; gap: 16px;
}
.modal-title { font-size: 1.1rem; font-weight: 700; margin: 0; }
.modal-warning {
  background: #fee2e2; color: #991b1b; padding: 12px 16px;
  font-size: 0.85rem; line-height: 1.5;
}
.modal-actions { display: flex; gap: 12px; justify-content: flex-end; }
.start-btn.danger { background: #dc2626; }
.start-btn.danger:hover:not(:disabled) { background: #b91c1c; }
.project-detail-modal { max-width: 860px; width: 95%; max-height: 90vh; overflow-y: auto; gap: 0; padding: 0; }
.modal-header { display: flex; justify-content: space-between; align-items: center; padding: 24px 32px 16px; border-bottom: 1px solid #e5e5e5; }
.modal-close-btn { background: none; border: none; font-size: 1.4rem; cursor: pointer; color: #666; padding: 0 4px; line-height: 1; }
.modal-close-btn:hover { color: #000; }
.detail-section { padding: 20px 32px; border-bottom: 1px solid #f0f0f0; }
.detail-section:last-child { border-bottom: none; }
.detail-section-title { font-family: 'JetBrains Mono', monospace; font-size: 0.75rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; color: #666; margin: 0 0 12px; }
.detail-row { display: flex; gap: 16px; align-items: center; margin-bottom: 8px; }
.detail-label { font-family: 'JetBrains Mono', monospace; font-size: 0.75rem; color: #666; min-width: 110px; }
.detail-value { font-size: 0.85rem; }
.empty-state-sm { font-family: 'JetBrains Mono', monospace; font-size: 0.8rem; color: #bbb; padding: 8px 0; }
.danger-zone { background: #fafafa; }
.danger-title { color: #dc2626; }
.danger-hint { font-size: 0.85rem; color: #666; margin: 0 0 12px; }
.confirm-inline { display: flex; align-items: center; gap: 6px; font-family: 'JetBrains Mono', monospace; font-size: 0.78rem; }
.toast-success { position: fixed; bottom: 24px; right: 24px; background: #22c55e; color: #fff; padding: 10px 20px; font-family: 'JetBrains Mono', monospace; font-size: 0.85rem; z-index: 200; }
</style>
