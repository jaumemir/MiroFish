import service, { requestWithRetry } from './index'

/**
 * Generate ontology (upload documents and simulation requirements)
 * @param {Object} data - includes files, simulation_requirement, project_name, etc.
 * @returns {Promise}
 */
export function generateOntology(formData) {
  return requestWithRetry(() => 
    service({
      url: '/api/graph/ontology/generate',
      method: 'post',
      data: formData,
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    })
  )
}

/**
 * Build knowledge graph
 * @param {Object} data - includes project_id, graph_name, etc.
 * @returns {Promise}
 */
export function buildGraph(data) {
  return requestWithRetry(() =>
    service({
      url: '/api/graph/build',
      method: 'post',
      data
    })
  )
}

/**
 * Query task status
 * @param {String} taskId - task ID
 * @returns {Promise}
 */
export function getTaskStatus(taskId) {
  return service({
    url: `/api/graph/task/${taskId}`,
    method: 'get'
  })
}

/**
 * Get graph data
 * @param {String} graphId - graph ID
 * @returns {Promise}
 */
export function getGraphData(graphId) {
  return service({
    url: `/api/graph/data/${graphId}`,
    method: 'get'
  })
}

/**
 * Get project info
 * @param {String} projectId - project ID
 * @returns {Promise}
 */
export function getProject(projectId) {
  return service({
    url: `/api/graph/project/${projectId}`,
    method: 'get'
  })
}

/**
 * Import a pre-existing ontology JSON (instead of generating one)
 * @param {FormData} formData - files, simulation_requirement, ontology (JSON string)
 * @returns {Promise}
 */
export function importOntology(formData) {
  return requestWithRetry(() =>
    service({
      url: '/api/graph/ontology/import',
      method: 'post',
      data: formData,
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    })
  )
}

/**
 * Delete a project
 * @param {String} projectId
 * @returns {Promise}
 */
export function deleteProject(projectId) {
  return service({
    url: `/api/graph/project/${projectId}`,
    method: 'delete'
  })
}

/**
 * Llista tots els projectes (per a la Recovery UI)
 * @param {Number} limit - Màxim de projectes a retornar (default 50)
 * @returns {Promise}
 */
export function listProjects(limit = 50) {
  return service({
    url: `/api/graph/project/list?limit=${limit}`,
    method: 'get'
  })
}

/**
 * Actualitza el nom d'un projecte
 * @param {String} projectId
 * @param {String} name
 * @returns {Promise}
 */
export function updateProjectName(projectId, name) {
  return service({
    url: `/api/graph/project/${projectId}`,
    method: 'patch',
    data: { name }
  })
}
