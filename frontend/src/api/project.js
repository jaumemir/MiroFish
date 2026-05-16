import service from './index.js'

export async function getProjectDetail(projectId) {
  const res = await service.get(`/api/graph/project/${projectId}/detail`)
  return res.data
}

export async function downloadProjectSource(projectId, filename) {
  const res = await service.get(`/api/graph/project/${projectId}/download/source`, {
    responseType: 'blob',
  })
  const url = URL.createObjectURL(res.data)
  const a = document.createElement('a')
  a.href = url
  a.download = filename || 'source'
  a.click()
  URL.revokeObjectURL(url)
}

export async function downloadProjectOntology(projectId, version) {
  const res = await service.get(`/api/graph/project/${projectId}/ontology/download`, {
    responseType: 'blob',
  })
  const url = URL.createObjectURL(res.data)
  const a = document.createElement('a')
  a.href = url
  a.download = `ontology_v${version || 1}.json`
  a.click()
  URL.revokeObjectURL(url)
}

export async function uploadOntology(projectId, file) {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('project_id', projectId)
  const res = await service.post('/api/graph/ontology/import', formData)
  return res.data
}

export async function forceRebuildGraph(projectId) {
  const res = await service.post('/api/graph/build', { project_id: projectId, force: true })
  return res.data
}

export async function deleteSimulation(simulationId) {
  const res = await service.delete(`/api/simulation/${simulationId}`)
  return res.data
}

export async function downloadReportMd(reportId) {
  const res = await service.get(`/api/report/${reportId}/download`, {
    params: { format: 'md' },
    responseType: 'blob',
  })
  const url = URL.createObjectURL(res.data)
  const a = document.createElement('a')
  a.href = url
  a.download = `report_${reportId}.md`
  a.click()
  URL.revokeObjectURL(url)
}

export async function downloadReportPdf(reportId) {
  const res = await service.get(`/api/report/${reportId}/download`, {
    params: { format: 'pdf' },
    responseType: 'blob',
  })
  const url = URL.createObjectURL(res.data)
  const a = document.createElement('a')
  a.href = url
  a.download = `report_${reportId}.pdf`
  a.click()
  URL.revokeObjectURL(url)
}

export async function downloadSimulationLog(simulationId) {
  const res = await service.get(`/api/simulation/${simulationId}/download/log`, {
    responseType: 'blob',
  })
  const url = URL.createObjectURL(res.data)
  const a = document.createElement('a')
  a.href = url
  a.download = `simulation_${simulationId}_log.json`
  a.click()
  URL.revokeObjectURL(url)
}

export async function getSimulationDetail(simulationId) {
  const res = await service.get(`/api/simulation/${simulationId}/detail`)
  return res.data
}
