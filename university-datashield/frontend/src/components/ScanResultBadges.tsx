import type { Classification, ConfidenceBand, FieldResult } from '../types'

// ── Classification badge styling ─────────────────────────────────────────────

interface ClassBadgeConfig {
  label: string
  bg: string
  text: string
  border: string
  dot: string
}

const CLASS_CONFIG: Record<Classification, ClassBadgeConfig> = {
  DIRECT_IDENTIFIER:  { label: 'Direct ID',   bg: 'bg-red-500/10',    text: 'text-red-400',    border: 'border-red-500/30',    dot: 'bg-red-400' },
  QUASI_IDENTIFIER:   { label: 'Quasi ID',    bg: 'bg-orange-500/10', text: 'text-orange-400', border: 'border-orange-500/30', dot: 'bg-orange-400' },
  SENSITIVE_ATTRIBUTE:{ label: 'Sensitive',   bg: 'bg-amber-500/10',  text: 'text-amber-400',  border: 'border-amber-500/30',  dot: 'bg-amber-400' },
  ACADEMIC_DATA:      { label: 'Academic',    bg: 'bg-blue-500/10',   text: 'text-blue-400',   border: 'border-blue-500/30',   dot: 'bg-blue-400' },
  PLACEMENT_DATA:     { label: 'Placement',   bg: 'bg-purple-500/10', text: 'text-purple-400', border: 'border-purple-500/30', dot: 'bg-purple-400' },
  NON_SENSITIVE:      { label: 'Non-Sensitive', bg: 'bg-emerald-500/10', text: 'text-emerald-400', border: 'border-emerald-500/30', dot: 'bg-emerald-400' },
}

const BAND_CONFIG: Record<ConfidenceBand, { label: string; color: string; bar: string }> = {
  HIGH:   { label: 'HIGH',   color: 'text-red-400',     bar: 'bg-red-500' },
  MEDIUM: { label: 'MED',    color: 'text-amber-400',   bar: 'bg-amber-500' },
  LOW:    { label: 'LOW',    color: 'text-slate-400',   bar: 'bg-slate-500' },
  NONE:   { label: 'NONE',   color: 'text-slate-600',   bar: 'bg-slate-700' },
}

export function ClassificationBadge({ cls }: { cls: Classification }) {
  const cfg = CLASS_CONFIG[cls]
  return (
    <span className={`badge border ${cfg.bg} ${cfg.text} ${cfg.border} gap-1.5`}>
      <span className={`status-dot ${cfg.dot}`} />
      {cfg.label}
    </span>
  )
}

export function ConfidenceBar({ score, band }: { score: number; band: ConfidenceBand }) {
  const cfg = BAND_CONFIG[band]
  return (
    <div className="flex items-center gap-2 min-w-[120px]">
      <div className="flex-1 h-1.5 rounded-full bg-slate-700/60 overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-500 ${cfg.bar}`}
          style={{ width: `${score}%` }}
        />
      </div>
      <span className={`text-xs font-mono font-semibold w-7 text-right ${cfg.color}`}>
        {score}
      </span>
      <span className={`badge text-[10px] border ${
        band === 'HIGH'   ? 'bg-red-500/10 text-red-400 border-red-500/30'   :
        band === 'MEDIUM' ? 'bg-amber-500/10 text-amber-400 border-amber-500/30' :
                            'bg-slate-700/40 text-slate-500 border-slate-600/30'
      }`}>
        {cfg.label}
      </span>
    </div>
  )
}

export function SignalDots({ field }: { field: FieldResult }) {
  const signals = [
    { key: 'field_name_match', label: 'Name', active: field.signals.field_name_match },
    { key: 'pattern_match',    label: 'Pattern', active: field.signals.pattern_match },
    { key: 'data_type_match',  label: 'Type', active: field.signals.data_type_match },
    { key: 'semantic_match',   label: 'Semantic', active: field.signals.semantic_match },
  ]
  return (
    <div className="flex gap-1">
      {signals.map(s => (
        <span
          key={s.key}
          title={s.label}
          className={`status-dot ${s.active ? 'bg-emerald-400' : 'bg-slate-700'}`}
        />
      ))}
    </div>
  )
}
