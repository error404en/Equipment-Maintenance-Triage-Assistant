import { useEffect, useState } from 'react'
import { api, type EquipmentResponse } from '../api'

export function Home({ onNewReport, onSelectReport }: { onNewReport: () => void, onSelectReport: (id: number) => void }) {
  const [equipment, setEquipment] = useState<EquipmentResponse[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    load()
  }, [])

  const load = () => {
    setLoading(true)
    setError(null)
    api.getEquipment()
      .then(setEquipment)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }

  return (
    <div className="mx-auto max-w-[1320px] px-5 pb-16 pt-10 sm:px-8 lg:px-12">
      <div className="flex items-center justify-between mb-8">
        <h1 className="text-3xl font-black uppercase tracking-[-0.05em] sm:text-5xl">Equipment List</h1>
        <button onClick={onNewReport} className="bg-[#1e4b3b] px-4 py-3 text-left text-[11px] font-black uppercase tracking-[0.14em] text-white hover:bg-[#163b2e]">
          New Report
        </button>
      </div>
      
      {loading ? (
        <div className="animate-pulse flex space-x-4">
          <div className="flex-1 space-y-6 py-1">
            <div className="h-2 bg-[#dedcd3] rounded"></div>
            <div className="space-y-3">
              <div className="grid grid-cols-3 gap-4">
                <div className="h-2 bg-[#dedcd3] rounded col-span-2"></div>
                <div className="h-2 bg-[#dedcd3] rounded col-span-1"></div>
              </div>
              <div className="h-2 bg-[#dedcd3] rounded"></div>
            </div>
          </div>
        </div>
      ) : error ? (
        <div className="p-4 bg-[#fdfaf2] border border-[#986f20] text-[#986f20]">
          <p className="font-bold">Error loading equipment: {error}</p>
          <button onClick={load} className="mt-2 underline font-mono text-xs">Retry</button>
        </div>
      ) : equipment.length === 0 ? (
        <div className="text-center py-20 border-2 border-dashed border-[#dedcd3]">
          <p className="text-[#626a62] font-mono text-sm mb-4">No equipment found.</p>
          <button onClick={onNewReport} className="bg-[#1e4b3b] px-4 py-3 text-left text-[11px] font-black uppercase tracking-[0.14em] text-white hover:bg-[#163b2e]">
            Create First Report
          </button>
        </div>
      ) : (
        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {equipment.map(eq => (
            <div key={eq.id} className="border-2 border-[#292d29] p-5 bg-[#f8f6f0]">
              <div className="text-[10px] font-bold uppercase tracking-[0.16em] text-[#777d74] mb-2">{eq.type}</div>
              <h2 className="text-2xl font-black mb-4">{eq.identifier}</h2>
              <div className="space-y-3 border-t border-[#dedcd3] pt-4">
                <h3 className="text-[10px] font-bold uppercase tracking-[0.1em] text-[#292d29]">Latest Reports</h3>
                {eq.latest_reports.length === 0 ? (
                  <p className="text-xs text-[#777d74] italic">No reports yet</p>
                ) : (
                  eq.latest_reports.map(rep => (
                    <div key={rep.id} className="cursor-pointer hover:bg-[#ebe9e1] p-2 -mx-2 transition-colors" onClick={() => onSelectReport(rep.id)}>
                      <div className="font-mono text-[10px] text-[#626a62] mb-1">{new Date(rep.timestamp).toLocaleDateString()} · ER-{String(rep.id).padStart(4,'0')}</div>
                      <div className="text-sm truncate">{rep.description}</div>
                    </div>
                  ))
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
