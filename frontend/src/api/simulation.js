import service, { requestWithRetry } from './index'

/**
 * Create a simulation
 * @param {Object} data - { project_id, graph_id?, enable_twitter?, enable_reddit? }
 */
export const createSimulation = (data) => {
  return requestWithRetry(() => service.post('/api/simulation/create', data), 3, 1000)
}

/**
 * Prepare simulation environment (async task)
 * @param {Object} data - { simulation_id, entity_types?, use_llm_for_profiles?, parallel_profile_count?, force_regenerate? }
 */
export const prepareSimulation = (data) => {
  return requestWithRetry(() => service.post('/api/simulation/prepare', data), 3, 1000)
}

/**
 * Query preparation task progress
 * @param {Object} data - { task_id?, simulation_id? }
 */
export const getPrepareStatus = (data) => {
  return service.post('/api/simulation/prepare/status', data)
}

/**
 * Get simulation status
 * @param {string} simulationId
 */
export const getSimulation = (simulationId) => {
  return service.get(`/api/simulation/${simulationId}`)
}

/**
 * Get Agent Profiles for a simulation
 * @param {string} simulationId
 * @param {string} platform - 'reddit' | 'twitter'
 */
export const getSimulationProfiles = (simulationId, platform = 'reddit') => {
  return service.get(`/api/simulation/${simulationId}/profiles`, { params: { platform } })
}

/**
 * Get Agent Profiles being generated in real time
 * @param {string} simulationId
 * @param {string} platform - 'reddit' | 'twitter'
 */
export const getSimulationProfilesRealtime = (simulationId, platform = 'reddit') => {
  return service.get(`/api/simulation/${simulationId}/profiles/realtime`, { params: { platform } })
}

/**
 * Get simulation configuration
 * @param {string} simulationId
 */
export const getSimulationConfig = (simulationId) => {
  return service.get(`/api/simulation/${simulationId}/config`)
}

/**
 * Get simulation configuration being generated in real time
 * @param {string} simulationId
 * @returns {Promise} Returns configuration including metadata and config content
 */
export const getSimulationConfigRealtime = (simulationId) => {
  return service.get(`/api/simulation/${simulationId}/config/realtime`)
}

/**
 * List all simulations
 * @param {string} projectId - optional, filter by project ID
 */
export const listSimulations = (projectId) => {
  const params = projectId ? { project_id: projectId } : {}
  return service.get('/api/simulation/list', { params })
}

/**
 * Start simulation
 * @param {Object} data - { simulation_id, platform?, max_rounds?, enable_graph_memory_update? }
 */
export const startSimulation = (data) => {
  return requestWithRetry(() => service.post('/api/simulation/start', data), 3, 1000)
}

/**
 * Stop simulation
 * @param {Object} data - { simulation_id }
 */
export const stopSimulation = (data) => {
  return service.post('/api/simulation/stop', data)
}

/**
 * Get simulation run real-time status
 * @param {string} simulationId
 */
export const getRunStatus = (simulationId) => {
  return service.get(`/api/simulation/${simulationId}/run-status`)
}

/**
 * Get detailed simulation run status (includes recent actions)
 * @param {string} simulationId
 */
export const getRunStatusDetail = (simulationId) => {
  return service.get(`/api/simulation/${simulationId}/run-status/detail`)
}

/**
 * Get posts from a simulation
 * @param {string} simulationId
 * @param {string} platform - 'reddit' | 'twitter'
 * @param {number} limit - number of results to return
 * @param {number} offset - pagination offset
 */
export const getSimulationPosts = (simulationId, platform = 'reddit', limit = 50, offset = 0) => {
  return service.get(`/api/simulation/${simulationId}/posts`, {
    params: { platform, limit, offset }
  })
}

/**
 * Get simulation timeline (summarised by round)
 * @param {string} simulationId
 * @param {number} startRound - starting round
 * @param {number} endRound - ending round
 */
export const getSimulationTimeline = (simulationId, startRound = 0, endRound = null) => {
  const params = { start_round: startRound }
  if (endRound !== null) {
    params.end_round = endRound
  }
  return service.get(`/api/simulation/${simulationId}/timeline`, { params })
}

/**
 * Get Agent statistics
 * @param {string} simulationId
 */
export const getAgentStats = (simulationId) => {
  return service.get(`/api/simulation/${simulationId}/agent-stats`)
}

/**
 * Get simulation action history
 * @param {string} simulationId
 * @param {Object} params - { limit, offset, platform, agent_id, round_num }
 */
export const getSimulationActions = (simulationId, params = {}) => {
  return service.get(`/api/simulation/${simulationId}/actions`, { params })
}

/**
 * Close simulation environment (graceful shutdown)
 * @param {Object} data - { simulation_id, timeout? }
 */
export const closeSimulationEnv = (data) => {
  return service.post('/api/simulation/close-env', data)
}

/**
 * Get simulation environment status
 * @param {Object} data - { simulation_id }
 */
export const getEnvStatus = (data) => {
  return service.post('/api/simulation/env-status', data)
}

/**
 * Batch interview Agents
 * @param {Object} data - { simulation_id, interviews: [{ agent_id, prompt }] }
 */
export const interviewAgents = (data) => {
  return requestWithRetry(() => service.post('/api/simulation/interview/batch', data), 3, 1000)
}

/**
 * Get list of historical simulations (with project details)
 * Used for the homepage historical projects view
 * @param {number} limit - result count limit
 */
export const getSimulationHistory = (limit = 20) => {
  return service.get('/api/simulation/history', { params: { limit } })
}

/**
 * Update an agent's profile fields (Fase A/B)
 * @param {string} simulationId
 * @param {number} userId
 * @param {Object} fields - partial profile fields to update
 */
export const patchAgent = (simulationId, userId, fields) => {
  return service.patch(`/api/simulation/${simulationId}/agent/${userId}`, fields)
}

/**
 * Delete an agent from a simulation
 * @param {string} simulationId
 * @param {number} userId
 */
export const deleteAgent = (simulationId, userId) => {
  return service.delete(`/api/simulation/${simulationId}/agent/${userId}`)
}

/**
 * Create a new agent from an existing graph entity
 * @param {string} simulationId
 * @param {Object} data - { source_entity_uuid, extra_instructions? }
 */
export const createAgent = (simulationId, data) => {
  return requestWithRetry(() => service.post(`/api/simulation/${simulationId}/agent`, data), 3, 1000)
}

/**
 * Regenerate an agent's personality profile
 * @param {string} simulationId
 * @param {number} userId
 * @param {Object} data - { extra_instructions? }
 */
export const regenerateAgent = (simulationId, userId, data = {}) => {
  return requestWithRetry(() => service.post(`/api/simulation/${simulationId}/agent/${userId}/regenerate`, data), 3, 1000)
}

/**
 * Generic task status poll (for regenerate_agent and other async tasks)
 * @param {string} taskId
 */
export const getTaskStatus = (taskId) => {
  return requestWithRetry(() => service.get(`/api/simulation/task/${taskId}`), 3, 1000)
}

/**
 * Trigger Fase A → Fase B transition (generate behavior config)
 * @param {string} simulationId
 */
export const generateConfig = (simulationId) => {
  return requestWithRetry(() => service.post(`/api/simulation/${simulationId}/generate-config`, {}), 3, 1000)
}

/**
 * Update simulation global config parameters (Fase B)
 * @param {string} simulationId
 * @param {Object} fields - partial config fields
 */
export const patchSimulationConfig = (simulationId, fields) => {
  return service.patch(`/api/simulation/${simulationId}/config`, fields)
}

/**
 * Clone a simulation (copy agent profiles, set status=profiles_ready)
 * @param {string} simulationId - source simulation ID
 * @param {string} projectId
 */
export const cloneSimulation = (simulationId, projectId) => {
  return requestWithRetry(() => service.post(`/api/simulation/${simulationId}/clone`, { project_id: projectId }), 3, 1000)
}

/**
 * Get the count of available entities for a graph (fast endpoint, no entity data returned)
 * @param {string} graphId
 */
export const getGraphEntityCount = (graphId) => {
  return service.get(`/api/simulation/entities/${graphId}/count`)
}
