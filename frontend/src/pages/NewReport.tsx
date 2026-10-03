import { useState } from 'react'
import { api } from '../api'

export function NewReport({ actorId, onReportCreated, onCancel }: { actorId: string, onReportCreated: (id: number) => void, onCancel: () => void }) {
  const [eqType, setEqType] = useState('cnc')
  const [eqIdentifier, setEqIdentifier] = useState('')
  const [description, setDescription] = useState('')
  const [events, setEvents] = useState([{ message: '', coolant_temperature: '', vibration: '', spindle_speed: '', hydraulic_pressure: '', bearing_temperature: '' }])
  
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  
  const validate = () => {
    if (eqType !== 'cnc') return 'Only "cnc" equipment type is supported.'
    if (!eqIdentifier.trim()) return 'Equipment identifier is required.'
    if (!description.trim()) return 'Description is required.'
    if (description.length > 2000) return 'Description is too long.'
    if (events.length === 0) return 'At least one event is required.'
    if (events.length > 50) return 'Too many events.'
    
    for (let i = 0; i < events.length; i++) {
      const e = events[i]
      if (!e.message.trim()) return `Event ${i+1} message is required.`
      if (e.message.length > 1000) return `Event ${i+1} message is too long.`
      
      const keys = ['coolant_temperature', 'vibration', 'spindle_speed', 'hydraulic_pressure', 'bearing_temperature'] as const
      for (const k of keys) {
        if (e[k]) {
          if (isNaN(Number(e[k]))) return `Event ${i+1} reading ${k} must be numeric.`
        }
      }
    }
    return null
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    const err = validate()
    if (err) {
      setError(err)
      return
    }
    
    setLoading(true)
    setError(null)
    
    const payload = {
      equipment_type: eqType,
      equipment_identifier: eqIdentifier,
      reported_by: actorId,
      description,
      events: events.map(ev => {
        const readings: any = {}
        const keys = ['coolant_temperature', 'vibration', 'spindle_speed', 'hydraulic_pressure', 'bearing_temperature'] as const
        keys.forEach(k => {
          if (ev[k]) readings[k] = Number(ev[k])
        })
        return {
          message: ev.message,
          readings
        }
      })
    }
    
    try {
      const res = await api.createReport(payload)
      onReportCreated(res.id)
    } catch (e: any) {
      setError(e.message)
      setLoading(false)
    }
  }

  return (
    <div className="mx-auto max-w-[800px] px-5 pb-16 pt-10 sm:px-8">
      <div className="mb-8 border-b-2 border-[#292d29] pb-6">
        <h1 className="text-3xl font-black uppercase tracking-[-0.05em]">New Issue Report</h1>
        <p className="mt-2 text-sm text-[#626a62]">Submit a new diagnostic report for triage analysis.</p>
      </div>
      
      {error && (
        <div className="mb-6 border border-[#b58326] bg-[#fdfaf2] p-4 text-[#986f20] text-sm font-bold">
          {error}
        </div>
      )}
      
      <form onSubmit={handleSubmit} className="space-y-8">
        <div className="grid grid-cols-2 gap-6">
          <div>
            <label className="block text-[10px] font-bold uppercase tracking-[0.1em] text-[#777d74] mb-2">Equipment Type</label>
            <select value={eqType} onChange={e => setEqType(e.target.value)} className="w-full border border-[#8f9188] bg-[#f5f2ea] p-2 text-sm">
              <option value="cnc">CNC Mill</option>
            </select>
          </div>
          <div>
            <label className="block text-[10px] font-bold uppercase tracking-[0.1em] text-[#777d74] mb-2">Identifier (e.g. M-204)</label>
            <input value={eqIdentifier} onChange={e => setEqIdentifier(e.target.value)} placeholder="M-204" className="w-full border border-[#8f9188] bg-[#f5f2ea] p-2 text-sm" />
          </div>
        </div>
        
        <div>
          <label className="block text-[10px] font-bold uppercase tracking-[0.1em] text-[#777d74] mb-2">Description</label>
          <textarea value={description} onChange={e => setDescription(e.target.value)} rows={4} className="w-full border border-[#8f9188] bg-[#f5f2ea] p-2 text-sm" placeholder="Describe the problem..."></textarea>
        </div>
        
        <div className="border-t border-[#dedcd3] pt-6">
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-[11px] font-black uppercase tracking-[0.14em]">Events & Readings</h2>
            <button type="button" onClick={() => setEvents([...events, { message: '', coolant_temperature: '', vibration: '', spindle_speed: '', hydraulic_pressure: '', bearing_temperature: '' }])} className="text-[10px] font-bold uppercase tracking-[0.1em] text-[#1e4b3b] hover:underline">
              + Add Event
            </button>
          </div>
          
          <div className="space-y-4">
            {events.map((ev, idx) => (
              <div key={idx} className="border border-[#c9c8be] bg-[#f8f6f0] p-4 relative">
                {events.length > 1 && (
                  <button type="button" onClick={() => setEvents(events.filter((_, i) => i !== idx))} className="absolute top-2 right-2 text-[#986f20] text-xs font-bold hover:underline">Remove</button>
                )}
                <div className="mb-4 pr-10">
                  <label className="block text-[10px] font-bold uppercase tracking-[0.1em] text-[#777d74] mb-1">Event Message</label>
                  <input value={ev.message} onChange={e => { const newE = [...events]; newE[idx].message = e.target.value; setEvents(newE) }} className="w-full border border-[#8f9188] bg-white p-2 text-sm" placeholder="Log message or observation" />
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                  <div>
                    <label className="block text-[9px] font-bold uppercase tracking-wider text-[#777d74] mb-1">Coolant Temp</label>
                    <input type="number" step="any" value={ev.coolant_temperature} onChange={e => { const newE = [...events]; newE[idx].coolant_temperature = e.target.value; setEvents(newE) }} className="w-full border border-[#8f9188] bg-white p-1.5 text-xs" />
                  </div>
                  <div>
                    <label className="block text-[9px] font-bold uppercase tracking-wider text-[#777d74] mb-1">Vibration</label>
                    <input type="number" step="any" value={ev.vibration} onChange={e => { const newE = [...events]; newE[idx].vibration = e.target.value; setEvents(newE) }} className="w-full border border-[#8f9188] bg-white p-1.5 text-xs" />
                  </div>
                  <div>
                    <label className="block text-[9px] font-bold uppercase tracking-wider text-[#777d74] mb-1">Spindle Speed</label>
                    <input type="number" step="any" value={ev.spindle_speed} onChange={e => { const newE = [...events]; newE[idx].spindle_speed = e.target.value; setEvents(newE) }} className="w-full border border-[#8f9188] bg-white p-1.5 text-xs" />
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
        
        <div className="flex gap-4 pt-4">
          <button type="submit" disabled={loading} className="bg-[#1e4b3b] px-6 py-3 text-[11px] font-black uppercase tracking-[0.14em] text-white hover:bg-[#163b2e] disabled:opacity-50">
            {loading ? 'Submitting...' : 'Submit Report'}
          </button>
          <button type="button" onClick={onCancel} disabled={loading} className="border border-[#1e4b3b] px-6 py-3 text-[11px] font-black uppercase tracking-[0.14em] text-[#1e4b3b] hover:bg-[#e7eee6] disabled:opacity-50">
            Cancel
          </button>
        </div>
      </form>
    </div>
  )
}
