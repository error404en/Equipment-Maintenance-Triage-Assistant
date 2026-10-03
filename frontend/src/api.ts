export interface EquipmentResponse {
  id: number
  identifier: string
  type: string
  latest_reports: { id: number, timestamp: string, description: string }[]
}
export interface RuleResult {
  rule_id: string
  status: 'ok' | 'warn' | 'critical' | 'missing' | 'conflict'
  message: string
  reason: string
  evidence: { event_index?: number; reading_key?: string }[]
  severity: number
}
export interface Citation {
  chunk_id?: string
  event_index?: number
}
export interface AIFinding {
  kind: 'observation' | 'possible_cause' | 'confirmed'
  description: string
  citations: Citation[]
}
export interface AICitedItem {
  description: string
  citations: Citation[]
}
export interface AnalysisData {
  report_id: number
  equipment_id: number
  rule_results: RuleResult[]
  ai_status: 'ok' | 'degraded' | 'unavailable'
  ai_error_code?: string
  ai_findings: AIFinding[]
  ai_questions?: AICitedItem[]
  ai_steps?: AICitedItem[]
  ai_priority_reason?: AICitedItem
  final_priority: number
  detail?: string
}
export interface WorkOrderHistory {
  id: number
  status: 'draft' | 'approved' | 'rejected'
  priority: number
  proposed_steps: string | null
  reviewed_by: string | null
  reviewed_at: string | null
}
export interface ReportHistory {
  id: number
  reported_by: string
  description: string
  timestamp: string
  work_order: WorkOrderHistory | null
}
export interface EquipmentHistoryResponse {
  equipment_id: number
  equipment_identifier: string
  reports: ReportHistory[]
}
export interface ReportEventResponse {
  event_index: number
  readings: Record<string, any>
}
export interface IssueReportDetailResponse {
  id: number
  equipment_id: number
  reported_by: string
  description: string
  timestamp: string
  events: ReportEventResponse[]
}

export const api = {
  getEquipment: async (): Promise<EquipmentResponse[]> => {
    const res = await fetch('/api/equipment')
    if (!res.ok) throw new Error('Failed to fetch equipment')
    return res.json()
  },
  createReport: async (data: any): Promise<{ id: number }> => {
    const res = await fetch('/api/reports', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    })
    if (!res.ok) {
      const err = await res.json()
      throw new Error(err.detail || 'Failed to create report')
    }
    return res.json()
  },
  getReport: async (id: number): Promise<IssueReportDetailResponse> => {
    const res = await fetch(`/api/reports/${id}`)
    if (!res.ok) throw new Error('Failed to fetch report')
    return res.json()
  },
  analyzeReport: async (id: number): Promise<AnalysisData> => {
    const res = await fetch(`/api/reports/${id}/analyze`, { method: 'POST' })
    if (!res.ok) {
      const err = await res.json()
      throw new Error(err.detail || 'Analysis failed')
    }
    return res.json()
  },
  getEquipmentHistory: async (id: number): Promise<EquipmentHistoryResponse> => {
    const res = await fetch(`/api/equipment/${id}/history`)
    if (!res.ok) throw new Error('Failed to fetch equipment history')
    return res.json()
  },
  createDraftWorkOrder: async (id: number): Promise<WorkOrderHistory> => {
    const res = await fetch(`/api/reports/${id}/draft-work-order`, { method: 'POST' })
    if (!res.ok) {
      const err = await res.json()
      throw new Error(err.detail || 'Failed to draft work order')
    }
    return res.json()
  },
  reviewWorkOrder: async (id: number, action: 'approve'|'reject', actor: string): Promise<WorkOrderHistory> => {
    const res = await fetch(`/api/work-orders/${id}/${action}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ actor })
    })
    if (!res.ok) {
      const err = await res.json()
      throw new Error(err.detail || 'Failed to review work order')
    }
    return res.json()
  }
}
