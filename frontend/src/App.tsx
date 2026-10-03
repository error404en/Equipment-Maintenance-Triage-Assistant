import { useCallback, useEffect, useRef, useState } from 'react'
import { AlertTriangle, Paperclip, ShieldCheck, X } from 'lucide-react'

interface HardcodedEvent {
  id: string
  time: string
  who: string
  text: string
}

interface HardcodedMeasurement {
  id: string
  label: string
  value: string
  unit: string
}

const hardcodedEvents: HardcodedEvent[] = [
  { id: 'E-04', time: '09:38', who: 'OPERATOR', text: 'Reported high-pitched spindle noise during rapid movement.' },
  { id: 'E-03', time: '09:21', who: 'TECHNICIAN', text: 'Coolant level checked — within normal range.' },
  { id: 'E-02', time: 'YESTERDAY · 16:10', who: 'TECHNICIAN', text: 'Routine spindle inspection completed.' },
  { id: 'E-01', time: 'MAY 14', who: 'SERVICE RECORD', text: 'Scheduled maintenance completed.' },
]

const hardcodedMeasurements: HardcodedMeasurement[] = [
  { id: 'M-01', label: 'SPINDLE SPEED', value: '1,240', unit: 'RPM' },
  { id: 'M-02', label: 'VIBRATION', value: '4.8', unit: 'mm/s' },
  { id: 'M-03', label: 'BEARING TEMP', value: '71', unit: '°C' },
  { id: 'M-04', label: 'HYDRAULIC PRESSURE', value: '151', unit: 'bar' },
]

interface RuleEvidence {
  event_index?: number | null
  reading_key?: string | null
  value?: unknown
}

interface RuleResult {
  rule_id: string
  status: 'ok' | 'warn' | 'critical' | 'missing' | 'conflict'
  message: string
  reason: string
  evidence: RuleEvidence[]
  severity: number
}

interface Citation {
  chunk_id?: string | null
  event_index?: number | null
}

interface AIFinding {
  kind: 'observation' | 'possible_cause'
  description: string
  citations: Citation[]
}

interface AnalysisData {
  report_id: number
  equipment_id: number
  rule_results: RuleResult[]
  ai_status: 'ok' | 'degraded' | 'unavailable'
  ai_error_code?: string | null
  ai_findings: AIFinding[]
  final_priority: number
  detail?: string
}

interface WorkOrderHistory {
  id: number
  status: 'draft' | 'approved' | 'rejected'
  priority: number
  proposed_steps: string | null
  reviewed_by: string | null
  reviewed_at: string | null
}

interface ReportHistory {
  id: number
  reported_by: string
  description: string
  timestamp: string
  work_order: WorkOrderHistory | null
}

interface EquipmentHistoryResponse {
  equipment_id: number
  equipment_identifier: string
  reports: ReportHistory[]
}

function SectionHeading({ number, children, meta }: { number: string; children: React.ReactNode; meta?: string }) {
  return (
    <div className="flex items-baseline justify-between border-b border-[#bdbdb3] pb-2">
      <h2 className="text-[11px] font-black uppercase tracking-[0.2em]">{number} — {children}</h2>
      {meta && <span className="font-mono text-[10px] text-[#777d74]">{meta}</span>}
    </div>
  )
}

function TriageRecord({
  number,
  kind,
  status,
  title,
  children,
  warning = false,
  assisted = false
}: {
  number: string
  kind: string
  status: string
  title: string
  children: React.ReactNode
  warning?: boolean
  assisted?: boolean
}) {
  return (
    <article className={`grid gap-3 border-b border-[#c9c8be] py-4 last:border-b-0 sm:grid-cols-[42px_145px_minmax(0,1fr)] ${assisted ? 'bg-[#efede4] px-2' : ''}`}>
      <div className="font-mono text-[11px] text-[#777d74]">{number}</div>
      <div>
        <div className={`text-[10px] font-black uppercase tracking-[0.15em] ${warning ? 'text-[#986f20]' : assisted ? 'text-[#687068]' : 'text-[#286044]'}`}>{kind}</div>
        <div className={`mt-1 text-[10px] font-bold uppercase tracking-[0.14em] ${warning ? 'text-[#986f20]' : assisted ? 'text-[#687068]' : 'text-[#286044]'}`}>{status}</div>
      </div>
      <div className="min-w-0">
        <h3 className="text-sm font-bold leading-5 text-[#2d332e]">{title}</h3>
        <div className="mt-2 text-[11px] leading-4 text-[#626a62]">{children}</div>
      </div>
    </article>
  )
}

function EvidenceRef({ id, onSelect }: { id: string; onSelect: (id: string) => void }) {
  return (
    <button
      type="button"
      onClick={() => onSelect(id)}
      className="inline-block font-mono font-bold text-[#1e4b3b] underline decoration-[#9aa99e] underline-offset-2 hover:text-[#986f20] hover:decoration-[#986f20]"
    >
      [{id}]
    </button>
  )
}

export default function App() {
  const [reportText, setReportText] = useState(
    'High-pitched spindle noise starts when the spindle accelerates above 1,200 RPM. Noise was not present during idle operation this morning. Coolant level was checked and appears normal.'
  )
  const [activeEvidence, setActiveEvidence] = useState<string | null>(null)
  const [attachedEvidence, setAttachedEvidence] = useState<string[]>(['E-04', 'M-01'])
  const [showAttachPanel, setShowAttachPanel] = useState(false)

  const [analysisData, setAnalysisData] = useState<AnalysisData | null>(null)
  const [isAnalyzing, setIsAnalyzing] = useState(true)
  const [isSaving, setIsSaving] = useState(false)
  const [isReviewing, setIsReviewing] = useState(false)

  const [workOrder, setWorkOrder] = useState<WorkOrderHistory | null>(null)
  const [equipmentHistory, setEquipmentHistory] = useState<EquipmentHistoryResponse | null>(null)
  const [workflowState, setWorkflowState] = useState<'Awaiting triage' | 'Investigation in progress' | 'Inspection hold' | 'Approved for maintenance' | 'Work order rejected'>('Awaiting triage')

  const [isSavingReport, setIsSavingReport] = useState(false)
  const [lastSavedTime, setLastSavedTime] = useState<string | null>(null)
  const [saveBanner, setSaveBanner] = useState<string | null>(null)
  const [selectedManualChunk, setSelectedManualChunk] = useState<string | null>(null)

  const evidenceRefs = useRef<Record<string, HTMLElement | null>>({})

  const reportId = new URLSearchParams(window.location.search).get('report_id') || '1'
  // Actor identity: read from ?actor= URL param; defaults to 'TECH-04' for demo.
  // Auth is documented as out of scope (AGENTS.md). This makes the actor transparent
  // and configurable without adding a login flow.
  const actorId = new URLSearchParams(window.location.search).get('actor') || 'TECH-04'

  // Equipment ID derived from the analysis response — NOT hardcoded.
  const [equipmentId, setEquipmentId] = useState<number | null>(null)
  const fetchEquipmentHistory = useCallback(() => {
    if (equipmentId == null) return
    fetch(`/api/equipment/${equipmentId}/history`)
      .then(res => res.json())
      .then((data: EquipmentHistoryResponse) => {
        setEquipmentHistory(data)
        const currentReport = data.reports?.find(r => r.id === parseInt(reportId, 10))
        if (currentReport?.work_order) {
          setWorkOrder(currentReport.work_order)
          if (currentReport.work_order.status === 'approved') {
            setWorkflowState('Approved for maintenance')
          } else if (currentReport.work_order.status === 'rejected') {
            setWorkflowState('Work order rejected')
          } else {
            setWorkflowState('Inspection hold')
          }
        }
      })
      .catch(err => console.error('Error fetching history:', err))
  }, [equipmentId, reportId])

  // Fetch analysis on mount. equipment_id comes from the response.
  useEffect(() => {
    fetch(`/api/reports/${reportId}/analyze`, { method: 'POST' })
      .then(res => res.json())
      .then(data => {
        setAnalysisData(data)
        if (data?.equipment_id) {
          setEquipmentId(data.equipment_id)
        }
      })
      .catch(err => console.error('Error analyzing report:', err))
      .finally(() => setIsAnalyzing(false))
  }, [reportId])

  // Fetch equipment history once we know the equipment_id from the analysis response.
  useEffect(() => {
    if (equipmentId != null) {
      fetchEquipmentHistory()
    }
  }, [equipmentId, fetchEquipmentHistory])

  const selectEvidence = (id: string) => {
    setActiveEvidence(id)
    const el = evidenceRefs.current[id]
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'center' })
    }
  }

  const handleToggleAttachEvidence = (id: string) => {
    if (attachedEvidence.includes(id)) {
      setAttachedEvidence(prev => prev.filter(x => x !== id))
    } else {
      setAttachedEvidence(prev => [...prev, id])
      if (!reportText.includes(`[${id}]`)) {
        setReportText(prev => `${prev.trim()} [${id}]`)
      }
    }
    selectEvidence(id)
  }

  const handleSaveReportDraft = () => {
    setIsSavingReport(true)
    setTimeout(() => {
      const timeStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
      setLastSavedTime(timeStr)
      setSaveBanner(`Observation draft recorded in engineering log at ${timeStr}.`)
      setIsSavingReport(false)
      setTimeout(() => setSaveBanner(null), 4000)
    }, 350)
  }

  const handleCreateWorkOrder = async (isConfirm: boolean) => {
    if (!analysisData || analysisData.detail) return
    setIsSaving(true)

    const findings = [
      ...(analysisData.rule_results || []).map(r => ({
        kind: r.status === 'ok' ? 'observation' : 'possible_cause',
        source: 'rules',
        description: `[${r.rule_id}] ${r.reason}`,
        citations: (r.evidence || [])
          .filter(ev => ev.event_index != null)
          .map(ev => ({ event_index: ev.event_index }))
      })),
      ...(analysisData.ai_findings || []).map(f => ({
        kind: f.kind,
        source: 'ai',
        description: f.description,
        citations: f.citations || []
      }))
    ]

    const proposedSteps = isConfirm
      ? 'Inspection required: Spindle bearing and drive assembly teardown check'
      : 'Continue investigation: Extended vibration spectrum logging & thermal test run'

    try {
      const res = await fetch(`/api/reports/${reportId}/work-orders`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          priority: analysisData.final_priority || 1,
          proposed_steps: proposedSteps,
          findings: findings
        })
      })

      if (res.ok) {
        const created: WorkOrderHistory = await res.json()
        setWorkOrder(created)
        setWorkflowState(isConfirm ? 'Inspection hold' : 'Investigation in progress')
        fetchEquipmentHistory()
      } else {
        const err = await res.json()
        alert(`Error creating work order: ${err.detail || err.message}`)
      }
    } catch (e) {
      console.error(e)
      alert('Failed to save work order')
    } finally {
      setIsSaving(false)
    }
  }

  const handleReviewWorkOrder = async (action: 'approve' | 'reject') => {
    if (!workOrder) return
    setIsReviewing(true)
    try {
      const res = await fetch(`/api/work-orders/${workOrder.id}/${action}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ actor: actorId })
      })

      if (res.ok) {
        const updated: WorkOrderHistory = await res.json()
        setWorkOrder(updated)
        setWorkflowState(action === 'approve' ? 'Approved for maintenance' : 'Work order rejected')
        fetchEquipmentHistory()
      } else {
        const err = await res.json()
        alert(`Error reviewing work order: ${err.detail || err.message}`)
      }
    } catch (e) {
      console.error(e)
      alert('Failed to review work order')
    } finally {
      setIsReviewing(false)
    }
  }

  const handleContinueInvestigation = () => {
    setWorkflowState('Investigation in progress')
    if (!workOrder) {
      handleCreateWorkOrder(false)
    }
  }

  const aiObservations = (analysisData?.ai_findings || []).filter(f => f.kind === 'observation')
  const aiPossibleCauses = (analysisData?.ai_findings || []).filter(f => f.kind === 'possible_cause')

  return (
    <main className="min-h-screen bg-[#f5f2ea] text-[#292d29]">
      {/* Header */}
      <header className="border-b border-[#292d29] px-5 py-4 sm:px-8 lg:px-12">
        <div className="mx-auto flex max-w-[1320px] items-center justify-between">
          <div className="text-sm font-black tracking-[0.14em]">AGGROSO</div>
          <div className="text-right font-mono text-[10px] uppercase tracking-[0.12em] text-[#777d74]">
            EQUIPMENT REPORT / ER-{reportId.padStart(4, '0')}
            <br />
            <span className={
              workflowState === 'Approved for maintenance' ? 'font-bold text-[#286044]' :
              workflowState === 'Investigation in progress' ? 'font-bold text-[#1e4b3b]' :
              workflowState === 'Work order rejected' ? 'font-bold text-[#626a62]' :
              'font-bold text-[#986f20]'
            }>
              STATUS: {workflowState.toUpperCase()}
            </span>
          </div>
        </div>
      </header>

      {/* Main Container */}
      <div className="mx-auto max-w-[1320px] px-5 pb-16 sm:px-8 lg:px-12">
        {/* Asset Identity Card */}
        <section className="border-b-2 border-[#292d29] py-8 sm:py-10">
          <div className="flex flex-col justify-between gap-5 sm:flex-row sm:items-end">
            <div>
              <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-[#777d74]">Asset identity</div>
              <h1 className="mt-3 text-4xl font-black uppercase tracking-[-0.05em] sm:text-6xl">
                CNC mill <span className="font-normal text-[#9b9d94]">/</span> M-204
              </h1>
              <p className="mt-3 text-xs font-bold uppercase tracking-[0.16em] text-[#626a62]">Bay 2 / Line A / CNC machining</p>
            </div>
            <div className="border-l-2 border-[#b58326] pl-4 text-[10px] uppercase tracking-[0.16em] text-[#777d74]">
              <span>Current operational state</span>
              <br />
              <span className="font-bold text-[#292d29]">
                {workflowState === 'Investigation in progress' ? 'Diagnostic run / RPM capped at 1,200' :
                 workflowState === 'Approved for maintenance' ? 'Maintenance approved / Locked out' :
                 workflowState === 'Work order rejected' ? 'Returned to production review' :
                 'Inspection hold'}
              </span>
              <div className="mt-3 normal-case tracking-normal">
                Last service
                <br />
                <span className="font-mono text-[#292d29]">14 May 2026 · 16:10</span>
              </div>
              <div className="mt-3 flex gap-3 font-mono text-[9px] tracking-[0.08em] text-[#626a62]">
                <span>ER-{reportId.padStart(4, '0')}</span>
                <span>{lastSavedTime ? `SAVED ${lastSavedTime}` : 'OPENED 09:42'}</span>
                <span>{lastSavedTime ? 'REV 02' : 'REV 01'}</span>
              </div>
            </div>
          </div>
        </section>

        {/* Feedback Alert Banner */}
        {saveBanner && (
          <div className="mt-4 flex items-center justify-between border border-[#286044] bg-[#edf4ef] px-4 py-2.5 text-xs text-[#286044]">
            <span className="font-mono font-bold">✓ {saveBanner}</span>
            <button type="button" onClick={() => setSaveBanner(null)} className="text-[#286044] hover:opacity-70">
              <X className="size-3.5" />
            </button>
          </div>
        )}

        {/* Two-column layout */}
        <div className="mt-6 grid gap-10 lg:grid-cols-[minmax(0,1fr)_minmax(380px,0.8fr)] lg:gap-16">
          {/* Left Column: Observation, Measurements, Evidence */}
          <div>
            {/* Section 01: Observation */}
            <section className="border-b border-[#bdbdb3] py-7">
              <SectionHeading number="01" meta={lastSavedTime ? `LAST SAVED ${lastSavedTime}` : 'RECORDED 09:42'}>
                Observation
              </SectionHeading>
              <textarea
                aria-label="Equipment observation"
                value={reportText}
                onChange={e => setReportText(e.target.value)}
                className="mt-5 min-h-36 w-full resize-y border-y border-[#8d9087] bg-transparent px-0 py-3 text-base leading-7 outline-none focus:border-[#1e4b3b]"
              />

              {/* Attached Evidence Chips */}
              {attachedEvidence.length > 0 && (
                <div className="mt-2.5 flex flex-wrap items-center gap-1.5 text-[10px]">
                  <span className="font-mono font-bold uppercase tracking-wider text-[#777d74]">Cited in observation:</span>
                  {attachedEvidence.map(id => (
                    <span
                      key={id}
                      className="inline-flex items-center gap-1.5 border border-[#1e4b3b] bg-[#e5eadf] px-2 py-0.5 font-mono text-[10px] font-bold text-[#1e4b3b]"
                    >
                      <EvidenceRef id={id} onSelect={selectEvidence} />
                      <button
                        type="button"
                        onClick={() => handleToggleAttachEvidence(id)}
                        className="text-[#777d74] hover:text-[#986f20]"
                        title="Remove citation"
                      >
                        ×
                      </button>
                    </span>
                  ))}
                </div>
              )}

              <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
                <span className="text-[10px] text-[#777d74]">
                  Describe symptoms, operating conditions, and checks already performed.
                  {' '}
                  <EvidenceRef id="E-04" onSelect={selectEvidence} />
                  {' '}
                  <EvidenceRef id="M-01" onSelect={selectEvidence} />
                </span>
                <button
                  type="button"
                  onClick={() => setShowAttachPanel(!showAttachPanel)}
                  className="flex items-center gap-2 border border-[#8f9188] px-3 py-2 text-[10px] font-bold uppercase tracking-[0.1em] hover:bg-[#ebe9e1]"
                >
                  <Paperclip className="size-3.5" />
                  {showAttachPanel ? 'Hide evidence list' : 'Attach evidence'}
                </button>
              </div>

              {/* Functional Attach Evidence Selection UI */}
              {showAttachPanel && (
                <div className="mt-4 border border-[#8f9188] bg-[#ebe8dd] p-4 text-xs">
                  <div className="flex items-center justify-between border-b border-[#bdbdb3] pb-2">
                    <span className="text-[10px] font-black uppercase tracking-[0.14em] text-[#292d29]">
                      Select Evidence Sources to Cite
                    </span>
                    <button
                      type="button"
                      onClick={() => setShowAttachPanel(false)}
                      className="text-[#777d74] hover:text-[#292d29]"
                    >
                      <X className="size-4" />
                    </button>
                  </div>
                  <div className="mt-3 grid gap-4 sm:grid-cols-2">
                    <div>
                      <div className="text-[10px] font-bold uppercase tracking-wider text-[#777d74]">Sensor Measurements</div>
                      <div className="mt-2 space-y-1.5">
                        {hardcodedMeasurements.map(m => {
                          const isAttached = attachedEvidence.includes(m.id)
                          return (
                            <button
                              key={m.id}
                              type="button"
                              onClick={() => handleToggleAttachEvidence(m.id)}
                              className={`flex w-full items-center justify-between border px-2.5 py-1.5 text-left font-mono text-[11px] transition-colors ${
                                isAttached
                                  ? 'border-[#1e4b3b] bg-[#e5eadf] text-[#1e4b3b]'
                                  : 'border-[#bdbdb3] bg-[#f5f2ea] text-[#292d29] hover:bg-[#eae6db]'
                              }`}
                            >
                              <span><b>[{m.id}]</b> {m.label} ({m.value} {m.unit})</span>
                              {isAttached && <span className="text-[10px] font-bold text-[#1e4b3b]">✓ Attached</span>}
                            </button>
                          )
                        })}
                      </div>
                    </div>
                    <div>
                      <div className="text-[10px] font-bold uppercase tracking-wider text-[#777d74]">Log Events & Reports</div>
                      <div className="mt-2 space-y-1.5">
                        {hardcodedEvents.map(e => {
                          const isAttached = attachedEvidence.includes(e.id)
                          return (
                            <button
                              key={e.id}
                              type="button"
                              onClick={() => handleToggleAttachEvidence(e.id)}
                              className={`flex w-full items-center justify-between border px-2.5 py-1.5 text-left font-mono text-[11px] transition-colors ${
                                isAttached
                                  ? 'border-[#1e4b3b] bg-[#e5eadf] text-[#1e4b3b]'
                                  : 'border-[#bdbdb3] bg-[#f5f2ea] text-[#292d29] hover:bg-[#eae6db]'
                              }`}
                            >
                              <span className="truncate pr-2"><b>[{e.id}]</b> {e.who}: {e.text}</span>
                              {isAttached && <span className="shrink-0 text-[10px] font-bold text-[#1e4b3b]">✓ Attached</span>}
                            </button>
                          )
                        })}
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </section>

            {/* Section 02: Measurements */}
            <section className="border-b border-[#bdbdb3] py-7">
              <SectionHeading number="02" meta="MOST RECENT VALUES">Measurements</SectionHeading>
              <div className="mt-5 grid grid-cols-2 border-y border-[#8f9188] sm:grid-cols-4">
                {hardcodedMeasurements.map(({ id, label, value, unit }) => {
                  const isHighlighted = activeEvidence === id
                  return (
                    <div
                      key={id}
                      ref={node => { evidenceRefs.current[id] = node }}
                      className={`border-b border-[#c9c8be] px-3 py-4 transition-all duration-300 sm:border-b-0 sm:border-r last:border-r-0 ${
                        isHighlighted ? 'bg-[#e5eadf] ring-2 ring-[#1e4b3b]' : ''
                      }`}
                    >
                      <div className="flex items-center justify-between text-[10px] font-bold tracking-[0.1em] text-[#777d74]">
                        <span>{label}</span>
                        <EvidenceRef id={id} onSelect={selectEvidence} />
                      </div>
                      <div className="mt-3 font-mono text-xl font-bold">
                        {value}<span className="ml-1 text-[10px] font-sans font-bold text-[#777d74]">{unit}</span>
                      </div>
                    </div>
                  )
                })}
              </div>
            </section>

            {/* Section 03: Recent Evidence */}
            <section className="py-7">
              <SectionHeading number="03" meta="OLDEST → MOST RECENT">Recent evidence</SectionHeading>
              <div className="mt-5 border-l border-[#8f9188]">
                {[...hardcodedEvents].reverse().map(({ id, time, who, text }) => {
                  const isHighlighted = activeEvidence === id
                  return (
                    <div
                      key={id}
                      ref={node => { evidenceRefs.current[id] = node }}
                      className={`relative ml-5 border-b border-[#dedcd3] pb-5 pl-5 pt-1 transition-all duration-300 last:border-b-0 ${
                        isHighlighted ? 'bg-[#e5eadf] ring-2 ring-[#1e4b3b]' : ''
                      }`}
                    >
                      <span className="absolute -left-[5px] top-1 size-2 border border-[#1e4b3b] bg-[#f5f2ea]" />
                      <div className="flex items-center gap-2 font-mono text-[10px] font-bold text-[#777d74]">
                        <EvidenceRef id={id} onSelect={selectEvidence} />
                        <span>{time}</span>
                        <span className="text-[#b1b3aa]">/</span>
                        <span className="font-sans tracking-[0.12em]">{who}</span>
                      </div>
                      <p className="mt-2 text-sm leading-5 text-[#424842]">{text}</p>
                    </div>
                  )
                })}
              </div>
            </section>
          </div>

          {/* Right Column: Triage record & Technician review */}
          <div>
            {/* Section 04: Triage Record */}
            <section className="border-t-2 border-[#292d29] pt-4">
              <SectionHeading number="04" meta="EVALUATED LATEST">Triage record</SectionHeading>

              {/* Prominent AI Engine Status Bar */}
              {analysisData && (
                <div className="mt-4 border border-[#8f9188] bg-[#f3efe4] p-3 text-xs">
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-[10px] font-black uppercase tracking-wider text-[#777d74]">
                      AI Advisory Engine
                    </span>
                    {analysisData.ai_status === 'ok' ? (
                      <span className="border border-[#286044] bg-[#edf4ef] px-2 py-0.5 font-mono text-[9px] font-black uppercase text-[#286044]">
                        ● OK / ONLINE
                      </span>
                    ) : analysisData.ai_status === 'degraded' ? (
                      <span className="border border-[#b58326] bg-[#fdfaf2] px-2 py-0.5 font-mono text-[9px] font-black uppercase text-[#986f20]">
                        ▲ DEGRADED
                      </span>
                    ) : (
                      <span className="border border-[#8f9188] bg-[#eceae1] px-2 py-0.5 font-mono text-[9px] font-black uppercase text-[#626a62]">
                        ○ UNAVAILABLE ({analysisData.ai_error_code || 'STANDBY'})
                      </span>
                    )}
                  </div>
                  <p className="mt-2 text-[11px] leading-4 text-[#525752]">
                    {analysisData.ai_status === 'ok'
                      ? 'Advisory engine active. Output schema and manual citations verified against local knowledge base.'
                      : analysisData.ai_status === 'degraded'
                      ? `Degraded state (${analysisData.ai_error_code}). Deterministic threshold rules remain authoritative.`
                      : 'Running in rules-only mode. Deterministic sensor checks are fully authoritative. No generative hallucinations.'}
                  </p>
                  <div className="mt-2 font-mono text-[10px] text-[#777d74]">
                    Authority: <span className="font-bold text-[#1e4b3b]">Deterministic Rules (P{analysisData.final_priority})</span>
                  </div>
                </div>
              )}

              {isAnalyzing ? (
                <div className="mt-5 py-4 text-sm text-[#777d74]">Analyzing report...</div>
              ) : analysisData?.detail ? (
                <div className="mt-5 py-4 text-sm text-[#986f20]">Error: {analysisData.detail}</div>
              ) : analysisData ? (
                <>
                  {/* Subsection 04-A: Deterministic Rules */}
                  <div className="mt-5 border-b border-[#8f9188] pb-2 text-[10px] font-black uppercase tracking-[0.18em] text-[#286044]">
                    Deterministic rule results (Authoritative)
                  </div>
                  {analysisData.rule_results?.map((r, idx) => (
                    <TriageRecord
                      key={`rule-${idx}`}
                      number={`R-${(idx + 1).toString().padStart(2, '0')}`}
                      kind="Rule check"
                      status={r.status === 'ok' ? 'Normal' : r.status === 'warn' ? 'Warning' : 'Critical'}
                      title={r.reason}
                      warning={r.status !== 'ok'}
                    >
                      <div className="space-y-1.5">
                        <p><b>Rule ID</b> — <span className="font-mono">{r.rule_id}</span> · Severity P{r.severity}</p>
                        {r.evidence && r.evidence.length > 0 && (
                          <div className="flex flex-wrap items-center gap-1.5 font-sans">
                            <b className="font-bold text-[#292d29]">Citations:</b>
                            {r.evidence.map((ev, evIdx) => {
                              if (ev.event_index) {
                                const evId = `E-0${ev.event_index}`
                                return <EvidenceRef key={evIdx} id={evId} onSelect={selectEvidence} />
                              }
                              if (ev.reading_key) {
                                return <span key={evIdx} className="font-mono text-[#1e4b3b]">[{ev.reading_key}]</span>
                              }
                              return null
                            })}
                          </div>
                        )}
                      </div>
                    </TriageRecord>
                  ))}

                  {/* Subsection 04-B: AI Observations (Distinct Section) */}
                  {aiObservations.length > 0 && (
                    <>
                      <div className="mt-6 border-b border-[#8f9188] pb-2 text-[10px] font-black uppercase tracking-[0.18em] text-[#687068]">
                        Assisted observations (AI · Non-Binding)
                      </div>
                      {aiObservations.map((f, idx) => (
                        <TriageRecord
                          key={`ai-obs-${idx}`}
                          number={`AO-${(idx + 1).toString().padStart(2, '0')}`}
                          kind="Assisted observation"
                          status="Observation"
                          title={f.description}
                          assisted
                        >
                          {f.citations && f.citations.length > 0 && (
                            <div className="flex flex-wrap items-center gap-1.5 font-sans">
                              <b className="font-bold text-[#292d29]">Citations:</b>
                              {f.citations.map((c, cIdx) => (
                                c.event_index ? (
                                  <EvidenceRef key={cIdx} id={`E-0${c.event_index}`} onSelect={selectEvidence} />
                                ) : c.chunk_id ? (
                                  <button
                                    key={cIdx}
                                    type="button"
                                    onClick={() => setSelectedManualChunk(c.chunk_id || null)}
                                    className="font-mono text-[10px] font-bold text-[#1e4b3b] underline decoration-[#9aa99e] underline-offset-2 hover:text-[#986f20]"
                                  >
                                    [KB: {c.chunk_id}]
                                  </button>
                                ) : null
                              ))}
                            </div>
                          )}
                        </TriageRecord>
                      ))}
                    </>
                  )}

                  {/* Subsection 04-C: AI Possible Causes (Distinct Section) */}
                  {aiPossibleCauses.length > 0 && (
                    <>
                      <div className="mt-6 border-b border-[#8f9188] pb-2 text-[10px] font-black uppercase tracking-[0.18em] text-[#986f20]">
                        Hypothesized causes (AI · Advisory Only)
                      </div>
                      {aiPossibleCauses.map((f, idx) => (
                        <TriageRecord
                          key={`ai-cause-${idx}`}
                          number={`PC-${(idx + 1).toString().padStart(2, '0')}`}
                          kind="Possible cause"
                          status="Hypothesis"
                          title={f.description}
                          warning
                          assisted
                        >
                          {f.citations && f.citations.length > 0 && (
                            <div className="flex flex-wrap items-center gap-1.5 font-sans">
                              <b className="font-bold text-[#292d29]">Citations:</b>
                              {f.citations.map((c, cIdx) => (
                                c.event_index ? (
                                  <EvidenceRef key={cIdx} id={`E-0${c.event_index}`} onSelect={selectEvidence} />
                                ) : c.chunk_id ? (
                                  <button
                                    key={cIdx}
                                    type="button"
                                    onClick={() => setSelectedManualChunk(c.chunk_id || null)}
                                    className="font-mono text-[10px] font-bold text-[#1e4b3b] underline decoration-[#9aa99e] underline-offset-2 hover:text-[#986f20]"
                                  >
                                    [KB: {c.chunk_id}]
                                  </button>
                                ) : null
                              ))}
                            </div>
                          )}
                        </TriageRecord>
                      ))}
                    </>
                  )}
                </>
              ) : (
                <div className="mt-5 py-4 text-sm text-[#777d74]">No analysis data available.</div>
              )}
            </section>

            {/* Section 05: Technician review & Work Order State Machine */}
            <section className="mt-10 border-t-2 border-[#292d29] pt-5">
              <SectionHeading number="05">Technician review</SectionHeading>
              <p className="mt-5 border-l-2 border-[#b58326] pl-3 text-sm font-bold leading-5">
                AI suggestions are advisory only.
              </p>
              <p className="mt-3 text-xs leading-5 text-[#626a62]">
                In accordance with system invariants, only the technician can authorize work orders or confirm findings.
              </p>

              {/* Work Order State Card if Work Order Exists */}
              {workOrder && (
                <div className="mt-5 border border-[#8f9188] bg-[#f8f6f0] p-4 text-xs">
                  <div className="flex items-center justify-between border-b border-[#dedcd3] pb-2">
                    <div>
                      <span className="font-mono text-sm font-black text-[#292d29]">
                        WORK ORDER #WO-{String(workOrder.id).padStart(4, '0')}
                      </span>
                      <span className="ml-2 font-mono text-[10px] text-[#777d74]">
                        PRIORITY P{workOrder.priority}
                      </span>
                    </div>
                    <span className={`px-2 py-0.5 font-mono text-[10px] font-black uppercase tracking-wider ${
                      workOrder.status === 'approved' ? 'bg-[#286044] text-white' :
                      workOrder.status === 'rejected' ? 'bg-[#986f20] text-white' :
                      'border border-[#b58326] bg-[#fdfaf2] text-[#986f20]'
                    }`}>
                      {workOrder.status}
                    </span>
                  </div>

                  <div className="mt-3">
                    <div className="text-[10px] font-bold uppercase tracking-[0.1em] text-[#777d74]">Proposed Action</div>
                    <p className="mt-1 font-mono text-xs font-semibold text-[#292d29]">
                      {workOrder.proposed_steps || 'Inspection required'}
                    </p>
                  </div>

                  {workOrder.status === 'draft' ? (
                    <div className="mt-4 border-t border-[#dedcd3] pt-3">
                      <div className="flex items-center justify-between">
                        <div className="text-[10px] font-bold uppercase tracking-wider text-[#777d74]">Technician Sign-Off</div>
                        <span className="font-mono text-[10px] text-[#777d74]">
                          Acting as: <b className="text-[#292d29]">{actorId}</b>
                          {actorId === 'TECH-04' && <span className="ml-1 text-[#b1b3aa]">(pass ?actor=ID to change)</span>}
                        </span>
                      </div>
                      <div className="mt-2 grid grid-cols-2 gap-2">
                        <button
                          type="button"
                          onClick={() => handleReviewWorkOrder('approve')}
                          disabled={isReviewing}
                          className="flex items-center justify-center gap-1.5 bg-[#1e4b3b] px-3 py-2 text-center text-[10px] font-black uppercase tracking-[0.12em] text-white hover:bg-[#163b2e] disabled:opacity-50"
                        >
                          <ShieldCheck className="size-3.5" /> Approve ({actorId})
                        </button>
                        <button
                          type="button"
                          onClick={() => handleReviewWorkOrder('reject')}
                          disabled={isReviewing}
                          className="flex items-center justify-center gap-1.5 border border-[#986f20] px-3 py-2 text-center text-[10px] font-black uppercase tracking-[0.12em] text-[#986f20] hover:bg-[#fdfaf2] disabled:opacity-50"
                        >
                          <AlertTriangle className="size-3.5" /> Reject Work Order
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div className="mt-3 border-t border-[#dedcd3] pt-2 font-mono text-[10px] text-[#626a62]">
                      Guarded transition recorded · Reviewed by: <b className="text-[#292d29]">{workOrder.reviewed_by}</b>
                      {workOrder.reviewed_at && ` on ${new Date(workOrder.reviewed_at).toLocaleString()}`}
                    </div>
                  )}
                </div>
              )}

              {/* Action Buttons */}
              <div className="mt-6 grid gap-2">
                {!workOrder && (
                  <button
                    type="button"
                    onClick={() => handleCreateWorkOrder(true)}
                    disabled={isSaving || !analysisData || Boolean(analysisData.detail)}
                    className="bg-[#1e4b3b] px-4 py-3 text-left text-[11px] font-black uppercase tracking-[0.14em] text-white hover:bg-[#163b2e] disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {isSaving ? 'Submitting Work Order...' : 'Confirm inspection & draft work order'}
                  </button>
                )}

                <button
                  type="button"
                  onClick={handleContinueInvestigation}
                  disabled={isSaving || !analysisData || Boolean(analysisData.detail)}
                  className="border border-[#1e4b3b] px-4 py-3 text-left text-[11px] font-black uppercase tracking-[0.14em] text-[#1e4b3b] hover:bg-[#e7eee6] disabled:cursor-not-allowed disabled:opacity-50"
                >
                  Continue investigation (Diagnostics)
                </button>

                <button
                  type="button"
                  onClick={handleSaveReportDraft}
                  disabled={isSavingReport}
                  className="border border-[#8f9188] px-4 py-3 text-left text-[11px] font-black uppercase tracking-[0.14em] text-[#626a62] hover:bg-[#ebe9e1] disabled:opacity-50"
                >
                  {isSavingReport ? 'Saving Report...' : lastSavedTime ? `Save report (Last saved ${lastSavedTime})` : 'Save report'}
                </button>
              </div>
            </section>
          </div>
        </div>

        {/* Section 06: Compact Equipment & Audit History */}
        <section className="mt-14 border-t-2 border-[#292d29] pt-8">
          <SectionHeading number="06" meta="IMMUTABLE AUDIT TRAIL">
            Asset History / CNC Mill M-204
          </SectionHeading>

          <div className="mt-5 overflow-x-auto">
            <table className="w-full text-left font-sans text-xs">
              <thead>
                <tr className="border-b border-[#8f9188] text-[10px] font-black uppercase tracking-[0.14em] text-[#777d74]">
                  <th className="pb-2">Report ID</th>
                  <th className="pb-2">Timestamp</th>
                  <th className="pb-2">Reporter</th>
                  <th className="pb-2">Fault Summary</th>
                  <th className="pb-2">Work Order</th>
                  <th className="pb-2">Status</th>
                  <th className="pb-2">Reviewer Audit</th>
                </tr>
              </thead>
              <tbody>
                {equipmentHistory?.reports && equipmentHistory.reports.length > 0 ? (
                  equipmentHistory.reports.map(rep => (
                    <tr key={rep.id} className="border-b border-[#dedcd3] py-2">
                      <td className="py-3 font-mono font-bold text-[#1e4b3b]">
                        ER-{String(rep.id).padStart(4, '0')}
                      </td>
                      <td className="py-3 font-mono text-[11px] text-[#777d74]">
                        {new Date(rep.timestamp).toLocaleString()}
                      </td>
                      <td className="py-3 font-mono text-[11px] uppercase text-[#292d29]">
                        {rep.reported_by}
                      </td>
                      <td className="max-w-xs truncate py-3 pr-4 text-[#424842]">
                        {rep.description}
                      </td>
                      <td className="py-3 font-mono">
                        {rep.work_order ? `WO-${String(rep.work_order.id).padStart(4, '0')}` : '—'}
                      </td>
                      <td className="py-3">
                        {rep.work_order ? (
                          <span className={`inline-block px-1.5 py-0.5 font-mono text-[9px] font-black uppercase tracking-wider ${
                            rep.work_order.status === 'approved' ? 'bg-[#286044] text-white' :
                            rep.work_order.status === 'rejected' ? 'bg-[#986f20] text-white' :
                            'border border-[#b58326] bg-[#fdfaf2] text-[#986f20]'
                          }`}>
                            {rep.work_order.status} (P{rep.work_order.priority})
                          </span>
                        ) : (
                          <span className="font-mono text-[#777d74]">None</span>
                        )}
                      </td>
                      <td className="py-3 font-mono text-[11px] text-[#626a62]">
                        {rep.work_order?.reviewed_by
                          ? `${rep.work_order.reviewed_by}`
                          : rep.work_order
                          ? 'Pending review'
                          : '—'}
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={7} className="py-4 text-center text-xs text-[#777d74]">
                      No previous equipment history found for M-204.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </section>
      </div>

      {/* Manual Chunk Reference Modal */}
      {selectedManualChunk && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="w-full max-w-lg border-2 border-[#292d29] bg-[#f5f2ea] p-6 shadow-xl">
            <div className="flex items-center justify-between border-b border-[#8f9188] pb-3">
              <div>
                <span className="font-mono text-[10px] uppercase tracking-widest text-[#777d74]">
                  Knowledge Base Reference
                </span>
                <h3 className="font-mono text-sm font-bold text-[#292d29]">{selectedManualChunk}</h3>
              </div>
              <button
                type="button"
                onClick={() => setSelectedManualChunk(null)}
                className="text-[#777d74] hover:text-[#292d29]"
              >
                <X className="size-4" />
              </button>
            </div>
            <div className="mt-4 text-xs leading-5 text-[#424842]">
              <p className="font-semibold text-[#292d29]">Verified Manual Reference Citation:</p>
              <div className="mt-2 border border-[#dedcd3] bg-[#ebe7db] p-3 font-mono text-[11px]">
                Manual section: <b>{selectedManualChunk}</b>
                <br />
                Retrieved via BM25 knowledge index for CNC Mill M-204. Citations verified against stored maintenance documentation.
              </div>
            </div>
            <div className="mt-5 text-right">
              <button
                type="button"
                onClick={() => setSelectedManualChunk(null)}
                className="bg-[#1e4b3b] px-4 py-1.5 text-[11px] font-black uppercase tracking-wider text-white hover:bg-[#163b2e]"
              >
                Close Reference
              </button>
            </div>
          </div>
        </div>
      )}
    </main>
  )
}
