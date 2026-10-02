import { useEffect, useRef, useState } from 'react'
import { Paperclip } from 'lucide-react'

const hardcodedEvents = [
  { id: 'E-04', time: '09:38', who: 'OPERATOR', text: 'Reported high-pitched spindle noise during rapid movement.' },
  { id: 'E-03', time: '09:21', who: 'TECHNICIAN', text: 'Coolant level checked — within normal range.' },
  { id: 'E-02', time: 'YESTERDAY · 16:10', who: 'TECHNICIAN', text: 'Routine spindle inspection completed.' },
  { id: 'E-01', time: 'MAY 14', who: 'SERVICE RECORD', text: 'Scheduled maintenance completed.' },
]

const hardcodedMeasurements = [
  { id: 'M-01', label: 'SPINDLE SPEED', value: '1,240', unit: 'RPM' },
  { id: 'M-02', label: 'VIBRATION', value: '4.8', unit: 'mm/s' },
  { id: 'M-03', label: 'BEARING TEMP', value: '71', unit: '°C' },
  { id: 'M-04', label: 'HYDRAULIC PRESSURE', value: '151', unit: 'bar' },
]

function SectionHeading({ number, children, meta }: { number: string; children: React.ReactNode; meta?: string }) {
  return (
    <div className="flex items-baseline justify-between border-b border-[#bdbdb3] pb-2">
      <h2 className="text-[11px] font-black uppercase tracking-[0.2em]">{number} — {children}</h2>
      {meta && <span className="font-mono text-[10px] text-[#777d74]">{meta}</span>}
    </div>
  )
}

function TriageRecord({ number, kind, status, title, children, warning = false, assisted = false }: { number: string; kind: string; status: string; title: string; children: React.ReactNode; warning?: boolean; assisted?: boolean }) {
  return (
    <article className={`grid gap-3 border-b border-[#c9c8be] py-4 last:border-b-0 sm:grid-cols-[42px_145px_minmax(0,1fr)] ${assisted ? 'bg-[#efede4]' : ''}`}>
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
    <button type="button" onClick={() => onSelect(id)} className="font-mono font-bold text-[#1e4b3b] underline decoration-[#9aa99e] underline-offset-2 hover:text-[#986f20]">
      [{id}]
    </button>
  )
}

export default function App() {
  const [reportText, setReportText] = useState('High-pitched spindle noise starts when the spindle accelerates above 1,200 RPM. Noise was not present during idle operation this morning. Coolant level was checked and appears normal.')
  const [activeEvidence, setActiveEvidence] = useState<string | null>(null)

  const [analysisData, setAnalysisData] = useState<any>(null)
  const [isAnalyzing, setIsAnalyzing] = useState(true)
  const [isSaving, setIsSaving] = useState(false)

  const evidenceRefs = useRef<Record<string, HTMLElement | null>>({})

  const reportId = new URLSearchParams(window.location.search).get('report_id') || '1'

  useEffect(() => {
    fetch(`/api/reports/${reportId}/analyze`, { method: 'POST' })
      .then(res => res.json())
      .then(data => {
        setAnalysisData(data)
      })
      .catch(err => console.error(err))
      .finally(() => setIsAnalyzing(false))
  }, [reportId])

  const handleSaveWorkOrder = async (isConfirm: boolean) => {
    if (!analysisData || analysisData.detail) return
    setIsSaving(true)

    // Merge rule findings and AI findings
    const findings = [
      ...(analysisData.rule_results || []).map((r: any) => ({
        kind: r.status === 'ok' ? 'observation' : 'possible_cause',
        source: 'rules',
        description: `[${r.sensor}] ${r.reason}`,
        citations: []
      })),
      ...(analysisData.ai_findings || []).map((f: any) => ({
        kind: f.kind,
        source: 'ai',
        description: f.description,
        citations: f.citations || []
      }))
    ]

    try {
      const res = await fetch(`/api/reports/${reportId}/work-orders`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          priority: analysisData.final_priority || 1,
          proposed_steps: isConfirm ? "Inspection required" : "Continue investigation",
          findings: findings
        })
      })
      if (res.ok) {
        alert('Work order created successfully!')
      } else {
        const err = await res.json()
        alert(`Error: ${err.detail}`)
      }
    } catch (e) {
      console.error(e)
      alert('Failed to save work order')
    } finally {
      setIsSaving(false)
    }
  }

  const selectEvidence = (id: string) => {
    setActiveEvidence(id)
    evidenceRefs.current[id]?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }

  return (
    <main className="min-h-screen bg-[#f5f2ea] text-[#292d29]">
      <header className="border-b border-[#292d29] px-5 py-4 sm:px-8 lg:px-12">
        <div className="mx-auto flex max-w-[1320px] items-center justify-between">
          <div className="text-sm font-black tracking-[0.14em]">AGGROSO</div>
          <div className="text-right font-mono text-[10px] uppercase tracking-[0.12em] text-[#777d74]">
            EQUIPMENT REPORT / ER-{(reportId).padStart(4, '0')}
            <br />
            <span className="text-[#986f20]">STATUS: AWAITING TRIAGE</span>
          </div>
        </div>
      </header>
      <div className="mx-auto max-w-[1320px] px-5 pb-16 sm:px-8 lg:px-12">
        <section className="border-b-2 border-[#292d29] py-8 sm:py-10">
          <div className="flex flex-col justify-between gap-5 sm:flex-row sm:items-end">
            <div>
              <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-[#777d74]">Asset identity</div>
              <h1 className="mt-3 text-4xl font-black uppercase tracking-[-0.05em] sm:text-6xl">CNC mill <span className="font-normal text-[#9b9d94]">/</span> M-204</h1>
              <p className="mt-3 text-xs font-bold uppercase tracking-[0.16em] text-[#626a62]">Bay 2 / Line A / CNC machining</p>
            </div>
            <div className="border-l-2 border-[#b58326] pl-4 text-[10px] uppercase tracking-[0.16em] text-[#777d74]">
              <span>Current state</span>
              <br />
              <span className="font-bold text-[#292d29]">Inspection hold</span>
              <div className="mt-3 normal-case tracking-normal">
                Last service
                <br />
                <span className="font-mono text-[#292d29]">14 May 2026 · 16:10</span>
              </div>
              <div className="mt-3 flex gap-3 font-mono text-[9px] tracking-[0.08em] text-[#626a62]">
                <span>ER-{(reportId).padStart(4, '0')}</span>
                <span>OPENED 09:42</span>
                <span>REV 01</span>
              </div>
            </div>
          </div>
        </section>
        <div className="grid gap-10 lg:grid-cols-[minmax(0,1fr)_minmax(360px,0.76fr)] lg:gap-16">
          <div>
            <section className="border-b border-[#bdbdb3] py-7">
              <SectionHeading number="01" meta="RECORDED 09:42">Observation</SectionHeading>
              <textarea
                aria-label="Equipment observation"
                value={reportText}
                onChange={e => setReportText(e.target.value)}
                className="mt-5 min-h-36 w-full resize-y border-y border-[#8d9087] bg-transparent px-0 py-3 text-base leading-7 outline-none focus:border-[#1e4b3b]"
              />
              <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
                <span className="text-[10px] text-[#777d74]">
                  Describe symptoms, operating conditions, and checks already performed.
                  <EvidenceRef id="E-04" onSelect={selectEvidence} />
                  <EvidenceRef id="M-01" onSelect={selectEvidence} />
                </span>
                <button className="flex items-center gap-2 border border-[#8f9188] px-3 py-2 text-[10px] font-bold uppercase tracking-[0.1em] hover:bg-[#ebe9e1]">
                  <Paperclip className="size-3.5" />Attach evidence
                </button>
              </div>
            </section>

            <section className="border-b border-[#bdbdb3] py-7">
              <SectionHeading number="02" meta="MOST RECENT VALUES">Measurements</SectionHeading>
              <div className="mt-5 grid grid-cols-2 border-y border-[#8f9188] sm:grid-cols-4">
                {hardcodedMeasurements.map(({ id, label, value, unit }) => (
                  <div key={id} ref={node => { evidenceRefs.current[id] = node }} className={`border-b border-[#c9c8be] px-3 py-4 transition-colors sm:border-b-0 sm:border-r last:border-r-0 ${activeEvidence === id ? 'bg-[#e5eadf]' : ''}`}>
                    <div className="flex items-center justify-between text-[10px] font-bold tracking-[0.1em] text-[#777d74]">
                      <span>{label}</span>
                      <EvidenceRef id={id} onSelect={selectEvidence} />
                    </div>
                    <div className="mt-3 font-mono text-xl font-bold">
                      {value}<span className="ml-1 text-[10px] font-sans font-bold text-[#777d74]">{unit}</span>
                    </div>
                  </div>
                ))}
              </div>
            </section>

            <section className="py-7">
              <SectionHeading number="03" meta="OLDEST → MOST RECENT">Recent evidence</SectionHeading>
              <div className="mt-5 border-l border-[#8f9188]">
                {[...hardcodedEvents].reverse().map(({ id, time, who, text }) => (
                  <div key={id} ref={node => { evidenceRefs.current[id] = node }} className={`relative ml-5 border-b border-[#dedcd3] pb-5 pl-5 pt-1 transition-colors last:border-b-0 ${activeEvidence === id ? 'bg-[#e5eadf]' : ''}`}>
                    <span className="absolute -left-[5px] top-1 size-2 border border-[#1e4b3b] bg-[#f5f2ea]" />
                    <div className="flex items-center gap-2 font-mono text-[10px] font-bold text-[#777d74]">
                      <EvidenceRef id={id} onSelect={selectEvidence} />
                      <span>{time}</span>
                      <span className="text-[#b1b3aa]">/</span>
                      <span className="font-sans tracking-[0.12em]">{who}</span>
                    </div>
                    <p className="mt-2 text-sm leading-5 text-[#424842]">{text}</p>
                  </div>
                ))}
              </div>
            </section>
          </div>
          <div>
            <section className="border-t-2 border-[#292d29] pt-4">
              <SectionHeading number="04" meta="EVALUATED LATEST">Triage record</SectionHeading>

              {isAnalyzing ? (
                <div className="mt-5 py-4 text-sm text-[#777d74]">Analyzing report...</div>
              ) : analysisData?.detail ? (
                <div className="mt-5 py-4 text-sm text-[#986f20]">Error: {analysisData.detail}</div>
              ) : analysisData ? (
                <>
                  <div className="mt-5 border-b border-[#8f9188] pb-2 text-[10px] font-black uppercase tracking-[0.18em] text-[#286044]">
                    Deterministic rule results
                  </div>
                  {analysisData.rule_results?.map((r: any, idx: number) => (
                    <TriageRecord
                      key={`rule-${idx}`}
                      number={`R-${(idx + 1).toString().padStart(2, '0')}`}
                      kind="Rule check"
                      status={r.status === 'ok' ? 'Normal' : r.status === 'warn' ? 'Warning' : 'Critical'}
                      title={r.reason}
                      warning={r.status !== 'ok'}
                    >
                      <p><b>Rule</b> — {r.sensor}</p>
                    </TriageRecord>
                  ))}

                  {analysisData.ai_findings && analysisData.ai_findings.length > 0 && (
                    <>
                      <div className="mt-5 border-b border-[#8f9188] pb-2 text-[10px] font-black uppercase tracking-[0.18em] text-[#687068]">
                        AI observation / possible cause
                      </div>
                      {analysisData.ai_findings.map((f: any, idx: number) => (
                        <TriageRecord
                          key={`ai-${idx}`}
                          number={`AI-${(idx + 1).toString().padStart(2, '0')}`}
                          kind="Assisted observation"
                          status={f.kind === 'possible_cause' ? 'Possible cause' : 'Observation'}
                          title={f.description}
                          assisted
                        >
                          {f.citations && f.citations.length > 0 && (
                            <p><b>Evidence</b> — {f.citations.map((c: any) => c.chunk_id || `Event ${c.event_index}`).join(', ')}</p>
                          )}
                        </TriageRecord>
                      ))}
                    </>
                  )}
                  {analysisData.ai_status !== 'ok' && (
                    <div className="mt-4 border border-[#b58326] bg-[#fdfaf2] p-3 text-xs text-[#986f20]">
                      <b>AI Analysis Unavailable:</b> {analysisData.ai_error_code || 'Unknown error'}. Showing rules-only analysis.
                    </div>
                  )}
                </>
              ) : (
                <div className="mt-5 py-4 text-sm text-[#777d74]">No analysis data available.</div>
              )}
            </section>

            <section className="mt-10 border-t-2 border-[#292d29] pt-5">
              <SectionHeading number="05">Technician review</SectionHeading>
              <p className="mt-5 border-l-2 border-[#b58326] pl-3 text-sm font-bold leading-5">AI suggestions are not confirmed findings.</p>
              <p className="mt-3 text-xs leading-5 text-[#626a62]">Only the technician can confirm the operational decision.</p>

              <div className="mt-6 grid gap-2">
                <button
                  onClick={() => handleSaveWorkOrder(true)}
                  disabled={isSaving || !analysisData || !!analysisData.detail}
                  className="bg-[#1e4b3b] px-4 py-3 text-left text-[11px] font-black uppercase tracking-[0.14em] text-white hover:bg-[#163b2e] disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {isSaving ? 'Saving...' : 'Confirm inspection'}
                </button>
                <button
                  onClick={() => handleSaveWorkOrder(false)}
                  disabled={isSaving || !analysisData || !!analysisData.detail}
                  className="border border-[#1e4b3b] px-4 py-3 text-left text-[11px] font-black uppercase tracking-[0.14em] text-[#1e4b3b] hover:bg-[#e7eee6] disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Continue investigation
                </button>
                <button className="border border-[#8f9188] px-4 py-3 text-left text-[11px] font-black uppercase tracking-[0.14em] text-[#626a62] hover:bg-[#ebe9e1]">
                  Save report
                </button>
              </div>
            </section>
          </div>
        </div>
      </div>
    </main>
  )
}
