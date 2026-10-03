import React from 'react'

export function SectionHeading({ number, children, meta }: { number: string; children: React.ReactNode; meta?: string }) {
  return (
    <div className="flex items-baseline justify-between border-b border-[#bdbdb3] pb-2">
      <h2 className="text-[11px] font-black uppercase tracking-[0.2em]">{number} — {children}</h2>
      {meta && <span className="font-mono text-[10px] text-[#777d74]">{meta}</span>}
    </div>
  )
}

export function TriageRecord({
  number, kind, status, title, children, warning = false, assisted = false
}: {
  number: string, kind: string, status: string, title: string, children?: React.ReactNode, warning?: boolean, assisted?: boolean
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
        {children && <div className="mt-2 text-[11px] leading-4 text-[#626a62]">{children}</div>}
      </div>
    </article>
  )
}

export function EvidenceRef({ id, onSelect }: { id: string; onSelect: (id: string) => void }) {
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
