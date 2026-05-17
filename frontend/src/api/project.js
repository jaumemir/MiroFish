import service from './index.js'

export async function getProjectDetail(projectId) {
  return await service.get(`/api/graph/project/${projectId}/detail`)
}

function triggerDownload(blob, filename) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

export async function downloadProjectSource(projectId, filename) {
  const res = await service.get(`/api/graph/project/${projectId}/download/source`, {
    responseType: 'blob',
  })
  triggerDownload(res, filename || 'source')
}

export async function downloadProjectOntology(projectId, version) {
  const res = await service.get(`/api/graph/project/${projectId}/ontology/download`, {
    responseType: 'blob',
  })
  triggerDownload(res, `ontology_v${version || 1}.json`)
}

export async function uploadOntology(projectId, file) {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('project_id', projectId)
  return await service.post('/api/graph/ontology/import', formData)
}

export async function forceRebuildGraph(projectId) {
  return await service.post('/api/graph/build', { project_id: projectId, force: true })
}

export async function deleteSimulation(simulationId) {
  return await service.delete(`/api/simulation/${simulationId}`)
}

export async function downloadReportMd(reportId) {
  const res = await service.get(`/api/report/${reportId}/download`, {
    params: { format: 'md' },
    responseType: 'blob',
  })
  triggerDownload(res, `report_${reportId}.md`)
}

export async function downloadReportPdf(reportId) {
  const res = await service.get(`/api/report/${reportId}/download`, {
    params: { format: 'pdf' },
    responseType: 'blob',
  })
  triggerDownload(res, `report_${reportId}.pdf`)
}

export async function downloadSimulationLog(simulationId) {
  const res = await service.get(`/api/simulation/${simulationId}/download/log`, {
    responseType: 'blob',
  })
  triggerDownload(res, `simulation_${simulationId}_log.json`)
}

export async function getSimulationDetail(simulationId) {
  return await service.get(`/api/simulation/${simulationId}/detail`)
}
