import { useState, useEffect } from 'react'
import { Home } from './pages/Home'
import { NewReport } from './pages/NewReport'
import { Analysis } from './pages/Analysis'

type Page = 'home' | 'new_report' | 'analysis'

export default function App() {
  const [page, setPage] = useState<Page>('home')
  const [reportId, setReportId] = useState<number | null>(null)

  const searchParams = new URLSearchParams(window.location.search)
  const initialActorId = searchParams.get('actor') || 'TECH-04'
  const [actorId, setActorId] = useState(initialActorId)

  // Quick effect to initialize from URL if someone links directly to a report
  useEffect(() => {
    const rid = searchParams.get('report_id')
    if (rid) {
      setReportId(parseInt(rid, 10))
      setPage('analysis')
    }
  }, [])

  const handleReportCreated = (id: number) => {
    setReportId(id)
    setPage('analysis')
  }

  const handleSelectReport = (id: number) => {
    setReportId(id)
    setPage('analysis')
  }

  return (
    <main className="min-h-screen bg-[#f5f2ea] text-[#292d29]">
      <header className="border-b border-[#292d29] px-5 py-4 sm:px-8 lg:px-12">
        <div className="mx-auto flex max-w-[1320px] items-center justify-between">
          <div className="text-sm font-black tracking-[0.14em]">TRIAGE ASSISTANT</div>
          <div className="flex items-center gap-4 text-right font-mono text-[10px] uppercase tracking-[0.12em] text-[#777d74]">
            <div className="flex items-center gap-2 border-r border-[#8f9188] pr-4">
              <span>Acting as:</span>
              <input
                type="text"
                value={actorId}
                onChange={e => setActorId(e.target.value)}
                className="w-24 bg-transparent border-b border-[#8f9188] outline-none font-bold text-[#292d29]"
              />
            </div>
            {page === 'analysis' && reportId ? (
              <span>REPORT / ER-{String(reportId).padStart(4, '0')}</span>
            ) : (
              <span>DASHBOARD</span>
            )}
          </div>
        </div>
      </header>

      {page === 'home' && (
        <Home
          onNewReport={() => setPage('new_report')}
          onSelectReport={handleSelectReport}
        />
      )}
      {page === 'new_report' && (
        <NewReport
          actorId={actorId}
          onReportCreated={handleReportCreated}
          onCancel={() => setPage('home')}
        />
      )}
      {page === 'analysis' && reportId && (
        <Analysis
          reportId={reportId}
          actorId={actorId}
          onBack={() => setPage('home')}
        />
      )}
    </main>
  )
}
