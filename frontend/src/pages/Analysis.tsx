import { useEffect, useState, useRef } from 'react'
import { api, type AnalysisData, type WorkOrderHistory, type EquipmentHistoryResponse } from '../api'
import { SectionHeading, TriageRecord, EvidenceRef } from '../components/Shared'
import { AlertTriangle, ShieldCheck, X } from 'lucide-react'

export function Analysis({ reportId, actorId, onBack }: { reportId: number, actorId: string, onBack: () => void }) {
  const [data, setData] = useState<AnalysisData | null>(null)
  const [history, setHistory] = useState<EquipmentHistoryResponse | null>(null)
  const [workOrder, setWorkOrder] = useState<WorkOrderHistory | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  // const [activeEvidence, setActiveEvidence] = useState<string | null>(null)
  const [selectedManualChunk, setSelectedManualChunk] = useState<string | null>(null)
  
  // WO Edit state
  const [woPriority, setWoPriority] = useState<number>(1)
  const [woSteps, setWoSteps] = useState<string>('')
  const [rejectReason, setRejectReason] = useState<string>('')
  const [isDrafting, setIsDrafting] = useState(false)
  const [isReviewing, setIsReviewing] = useState(false)

  const evidenceRefs = useRef<Record<string, HTMLElement | null>>({})

  useEffect(() => {
    load()
  }, [reportId])

  const load = () => {
    setLoading(true)
    setError(null)
    api.analyzeReport(reportId)
      .then(analysis => {
        setData(analysis)
        if (analysis.equipment_id) {
          api.getEquipmentHistory(analysis.equipment_id)
            .then(hist => {
              setHistory(hist)
              const reportHist = hist.reports.find(r => r.id === reportId)
              if (reportHist?.work_order) {
                setWorkOrder(reportHist.work_order)
                setWoPriority(reportHist.work_order.priority)
                setWoSteps(reportHist.work_order.proposed_steps || '')
              } else {
                setWoPriority(analysis.final_priority)
              }
            })
            .catch(console.error)
        }
      })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }

  const handleCreateDraft = async () => {
    if (!data) return
    setIsDrafting(true)
    try {
      const wo = await api.createDraftWorkOrder(reportId)
      setWorkOrder(wo)
      setWoPriority(wo.priority)
      setWoSteps(wo.proposed_steps || '')
      if (data.equipment_id) {
        const hist = await api.getEquipmentHistory(data.equipment_id)
        setHistory(hist)
      }
    } catch (e: any) {
      setError(e.message)
    } finally {
      setIsDrafting(false)
    }
  }

  const handleReview = async (action: 'approve' | 'reject') => {
    if (!workOrder) return
    setIsReviewing(true)
    try {
      const wo = await api.reviewWorkOrder(workOrder.id, action, actorId)
      setWorkOrder(wo)
      if (data?.equipment_id) {
        const hist = await api.getEquipmentHistory(data.equipment_id)
        setHistory(hist)
      }
    } catch (e: any) {
      setError(e.message)
    } finally {
      setIsReviewing(false)
    }
  }

  const selectEvidence = (id: string) => {
    // setActiveEvidence(id)
    const el = evidenceRefs.current[id]
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'center' })
    }
  }

  if (loading) {
    return <div className="p-10 text-center animate-pulse font-mono text-sm">Loading Analysis...</div>
  }

  if (error) {
    return (
      <div className="p-10 mx-auto max-w-[800px]">
        <div className="p-4 bg-[#fdfaf2] border border-[#986f20] text-[#986f20]">
          <p className="font-bold">Error: {error}</p>
          <div className="flex gap-4 mt-4">
            <button onClick={load} className="underline font-mono text-xs">Retry</button>
            <button onClick={onBack} className="underline font-mono text-xs">Back</button>
          </div>
        </div>
      </div>
    )
  }

  if (!data) return null

  const renderCitations = (citations?: { chunk_id?: string, event_index?: number }[]) => {
    if (!citations || citations.length === 0) return null
    return (
      <div className="flex flex-wrap items-center gap-1.5 font-sans mt-2">
        <b className="font-bold text-[#292d29] text-[11px]">Citations:</b>
        {citations.map((c, cIdx) => (
          c.event_index ? (
            <EvidenceRef key={cIdx} id={`E-${String(c.event_index).padStart(2, '0')}`} onSelect={selectEvidence} />
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
    )
  }

  return (
    <div className="mx-auto max-w-[1320px] px-5 pb-16 pt-10 sm:px-8 lg:px-12">
      <button onClick={onBack} className="mb-6 font-mono text-xs text-[#777d74] hover:text-[#292d29] flex items-center gap-2">
        ← Back to Equipment
      </button>

      <div className="grid gap-10 lg:grid-cols-[minmax(0,1fr)_minmax(380px,0.8fr)] lg:gap-16">
        <div>
          <section className="border-b border-[#bdbdb3] py-7">
            <SectionHeading number="01">Observations & Facts</SectionHeading>
            <div className="mt-5">
              {data.rule_results.map((r, idx) => (
                <TriageRecord
                  key={idx}
                  number={`R-${String(idx + 1).padStart(2, '0')}`}
                  kind="Rule Check"
                  status={r.status === 'ok' ? 'Normal' : r.status === 'missing' ? 'Missing Data' : r.status === 'conflict' ? 'Conflict' : 'Warning/Critical'}
                  title={r.reason}
                  warning={r.status !== 'ok'}
                >
                  <p>Severity P{r.severity} - {r.message}</p>
                  {renderCitations(r.evidence)}
                </TriageRecord>
              ))}
              {data.rule_results.length === 0 && <p className="text-xs text-[#777d74]">No deterministic rule results.</p>}
            </div>
          </section>

          <section className="border-b border-[#bdbdb3] py-7">
            <SectionHeading number="02">AI Analysis (Unconfirmed)</SectionHeading>
            
            <div className="mt-4 border border-[#8f9188] bg-[#f3efe4] p-3 text-xs mb-6">
              <div className="flex items-center justify-between">
                <span className="font-mono text-[10px] font-black uppercase tracking-wider text-[#777d74]">AI Engine Status</span>
                {data.ai_status === 'ok' ? (
                  <span className="border border-[#286044] bg-[#edf4ef] px-2 py-0.5 font-mono text-[9px] font-black uppercase text-[#286044]">● OK / ONLINE</span>
                ) : data.ai_status === 'degraded' ? (
                  <span className="border border-[#b58326] bg-[#fdfaf2] px-2 py-0.5 font-mono text-[9px] font-black uppercase text-[#986f20]">▲ DEGRADED</span>
                ) : (
                  <span className="border border-[#8f9188] bg-[#eceae1] px-2 py-0.5 font-mono text-[9px] font-black uppercase text-[#626a62]">○ UNAVAILABLE ({data.ai_error_code})</span>
                )}
              </div>
            </div>

            <h3 className="text-[10px] font-bold uppercase tracking-wider text-[#986f20] mb-4">Possible Causes</h3>
            {data.ai_findings.filter(f => f.kind === 'possible_cause').map((f, i) => (
              <TriageRecord key={i} number={`PC-${i+1}`} kind="Hypothesis" status="Unconfirmed" title={f.description} assisted warning>
                {renderCitations(f.citations)}
              </TriageRecord>
            ))}
            {data.ai_findings.filter(f => f.kind === 'possible_cause').length === 0 && <p className="text-xs text-[#777d74]">No possible causes identified.</p>}

            <h3 className="text-[10px] font-bold uppercase tracking-wider text-[#1e4b3b] mt-6 mb-4">Follow-up Questions</h3>
            {data.ai_questions && data.ai_questions.length > 0 ? (
              <ul className="space-y-4">
                {data.ai_questions.map((q, i) => (
                  <li key={i} className="text-sm border-l-2 border-[#1e4b3b] pl-3">
                    <p className="font-medium">{q.description}</p>
                    {renderCitations(q.citations)}
                  </li>
                ))}
              </ul>
            ) : <p className="text-xs text-[#777d74]">No follow-up questions.</p>}

            <h3 className="text-[10px] font-bold uppercase tracking-wider text-[#286044] mt-6 mb-4">Inspection Steps</h3>
            {data.ai_steps && data.ai_steps.length > 0 ? (
              <ul className="space-y-4">
                {data.ai_steps.map((s, i) => (
                  <li key={i} className="text-sm border-l-2 border-[#286044] pl-3">
                    <p className="font-medium">{s.description}</p>
                    {renderCitations(s.citations)}
                  </li>
                ))}
              </ul>
            ) : <p className="text-xs text-[#777d74]">No inspection steps.</p>}
          </section>

          <section className="py-7">
            <SectionHeading number="03">Confirmed Findings</SectionHeading>
            <p className="mt-4 text-xs text-[#777d74] italic">No technician-confirmed findings recorded for this report.</p>
          </section>
        </div>

        <div>
          <section className="border-t-2 border-[#292d29] pt-4">
            <SectionHeading number="04">Work Order Editor</SectionHeading>
            
            <div className="mt-4 border border-[#b58326] bg-[#fdfaf2] p-3 text-xs mb-6 text-[#986f20]">
              <AlertTriangle className="inline size-4 mr-2" />
              <strong>Notice:</strong> The system NEVER controls equipment or approves work automatically. Human authorization is always required.
            </div>

            {data.ai_priority_reason && (
              <div className="mb-6 p-4 bg-[#f8f6f0] border border-[#dedcd3]">
                <h4 className="text-[10px] font-bold uppercase tracking-wider text-[#777d74] mb-2">Priority Rationale (P{data.final_priority})</h4>
                <p className="text-sm">{data.ai_priority_reason.description}</p>
                {renderCitations(data.ai_priority_reason.citations)}
              </div>
            )}

            {!workOrder ? (
              <div className="space-y-4">
                <button 
                  onClick={handleCreateDraft} 
                  disabled={isDrafting}
                  className="w-full bg-[#1e4b3b] px-4 py-3 text-[11px] font-black uppercase tracking-[0.14em] text-white hover:bg-[#163b2e] disabled:opacity-50"
                >
                  {isDrafting ? 'Drafting...' : 'Generate Server Draft Work Order'}
                </button>
              </div>
            ) : (
              <div className="border border-[#8f9188] bg-[#f8f6f0] p-4 text-xs">
                <div className="flex items-center justify-between border-b border-[#dedcd3] pb-2 mb-4">
                  <span className="font-mono text-sm font-black text-[#292d29]">WO-{String(workOrder.id).padStart(4, '0')}</span>
                  <span className={`px-2 py-0.5 font-mono text-[10px] font-black uppercase tracking-wider ${
                    workOrder.status === 'approved' ? 'bg-[#286044] text-white' :
                    workOrder.status === 'rejected' ? 'bg-[#986f20] text-white' :
                    'border border-[#b58326] bg-[#fdfaf2] text-[#986f20]'
                  }`}>
                    {workOrder.status}
                  </span>
                </div>

                <div className="space-y-4">
                  <div>
                    <label className="block text-[10px] font-bold uppercase tracking-[0.1em] text-[#777d74] mb-1">Priority</label>
                    <input type="number" value={woPriority} onChange={e => setWoPriority(Number(e.target.value))} disabled={workOrder.status !== 'draft'} className="w-full border border-[#8f9188] bg-white p-2 text-sm disabled:bg-[#ebe9e1]" />
                  </div>
                  <div>
                    <label className="block text-[10px] font-bold uppercase tracking-[0.1em] text-[#777d74] mb-1">Proposed Steps</label>
                    <textarea value={woSteps} onChange={e => setWoSteps(e.target.value)} disabled={workOrder.status !== 'draft'} rows={6} className="w-full border border-[#8f9188] bg-white p-2 text-xs font-mono disabled:bg-[#ebe9e1]"></textarea>
                  </div>
                  
                  {workOrder.status === 'draft' && (
                    <div className="border-t border-[#dedcd3] pt-4">
                      <div className="mb-3">
                        <label className="block text-[10px] font-bold uppercase tracking-[0.1em] text-[#777d74] mb-1">Reject Reason (Optional)</label>
                        <input value={rejectReason} onChange={e => setRejectReason(e.target.value)} className="w-full border border-[#8f9188] bg-white p-2 text-sm" placeholder="Reason if rejecting..." />
                      </div>
                      <div className="grid grid-cols-2 gap-2">
                        <button onClick={() => handleReview('approve')} disabled={isReviewing} className="flex items-center justify-center gap-1.5 bg-[#1e4b3b] px-3 py-2 text-[10px] font-black uppercase tracking-[0.12em] text-white hover:bg-[#163b2e] disabled:opacity-50">
                          <ShieldCheck className="size-3.5" /> Approve
                        </button>
                        <button onClick={() => handleReview('reject')} disabled={isReviewing} className="flex items-center justify-center gap-1.5 border border-[#986f20] px-3 py-2 text-[10px] font-black uppercase tracking-[0.12em] text-[#986f20] hover:bg-[#fdfaf2] disabled:opacity-50">
                          <AlertTriangle className="size-3.5" /> Reject
                        </button>
                      </div>
                    </div>
                  )}

                  {workOrder.status !== 'draft' && (
                    <div className="mt-3 font-mono text-[10px] text-[#626a62]">
                      Reviewed by: <b className="text-[#292d29]">{workOrder.reviewed_by}</b>
                    </div>
                  )}
                </div>
              </div>
            )}
          </section>
        </div>
      </div>

      <section className="mt-14 border-t-2 border-[#292d29] pt-8">
        <SectionHeading number="05">Equipment History Timeline</SectionHeading>
        <div className="mt-5 overflow-x-auto">
          <table className="w-full text-left font-sans text-xs">
            <thead>
              <tr className="border-b border-[#8f9188] text-[10px] font-black uppercase tracking-[0.14em] text-[#777d74]">
                <th className="pb-2">Report ID</th>
                <th className="pb-2">Timestamp</th>
                <th className="pb-2">Reporter</th>
                <th className="pb-2">Summary</th>
                <th className="pb-2">WO Status</th>
              </tr>
            </thead>
            <tbody>
              {history?.reports && history.reports.length > 0 ? (
                history.reports.map(rep => (
                  <tr key={rep.id} className="border-b border-[#dedcd3] py-2">
                    <td className="py-3 font-mono font-bold text-[#1e4b3b]">ER-{String(rep.id).padStart(4, '0')}</td>
                    <td className="py-3 font-mono text-[11px] text-[#777d74]">{new Date(rep.timestamp).toLocaleString()}</td>
                    <td className="py-3 font-mono text-[11px] uppercase text-[#292d29]">{rep.reported_by}</td>
                    <td className="max-w-xs truncate py-3 pr-4 text-[#424842]">{rep.description}</td>
                    <td className="py-3">
                      {rep.work_order ? (
                        <span className={`inline-block px-1.5 py-0.5 font-mono text-[9px] font-black uppercase tracking-wider ${
                          rep.work_order.status === 'approved' ? 'bg-[#286044] text-white' :
                          rep.work_order.status === 'rejected' ? 'bg-[#986f20] text-white' :
                          'border border-[#b58326] bg-[#fdfaf2] text-[#986f20]'
                        }`}>{rep.work_order.status}</span>
                      ) : <span className="font-mono text-[#777d74]">None</span>}
                    </td>
                  </tr>
                ))
              ) : (
                <tr><td colSpan={5} className="py-4 text-center text-xs text-[#777d74]">No history found.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      {/* Manual Chunk Reference Modal */}
      {selectedManualChunk && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="w-full max-w-lg border-2 border-[#292d29] bg-[#f5f2ea] p-6 shadow-xl">
            <div className="flex items-center justify-between border-b border-[#8f9188] pb-3">
              <div>
                <span className="font-mono text-[10px] uppercase tracking-widest text-[#777d74]">Knowledge Base Reference</span>
                <h3 className="font-mono text-sm font-bold text-[#292d29]">{selectedManualChunk}</h3>
              </div>
              <button onClick={() => setSelectedManualChunk(null)} className="text-[#777d74] hover:text-[#292d29]"><X className="size-4" /></button>
            </div>
            <div className="mt-4 text-xs leading-5 text-[#424842]">
              <div className="mt-2 border border-[#dedcd3] bg-[#ebe7db] p-3 font-mono text-[11px]">
                Manual section: <b>{selectedManualChunk}</b><br />
                Retrieved via BM25 knowledge index.
              </div>
            </div>
            <div className="mt-5 text-right">
              <button onClick={() => setSelectedManualChunk(null)} className="bg-[#1e4b3b] px-4 py-1.5 text-[11px] font-black uppercase tracking-wider text-white hover:bg-[#163b2e]">Close Reference</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
