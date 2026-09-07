interface PlaceholderPageProps {
  title: string
  description: string
  icon: string
  phase: string
}

export default function PlaceholderPage({
  title,
  description,
  icon,
  phase,
}: PlaceholderPageProps) {
  return (
    <main className="flex-1 overflow-y-auto px-8 py-8">
      <div className="mb-6">
        <span className="badge bg-slate-700/60 text-slate-400 border border-slate-600/50">
          Coming · {phase}
        </span>
        <h1 className="mt-2 text-2xl font-bold text-white">{title}</h1>
        <p className="mt-1 text-sm text-slate-400">{description}</p>
      </div>

      <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-[rgb(var(--color-border))] bg-[rgb(var(--color-bg-card))]/50 py-24 px-8">
        <div className="text-5xl mb-4 opacity-30">{icon}</div>
        <p className="text-lg font-semibold text-slate-400">{title}</p>
        <p className="mt-2 text-sm text-slate-600 text-center max-w-sm">
          This feature is planned for a future phase. The navigation is set up
          so implementation can plug in here directly.
        </p>
        <div className="mt-6 rounded-lg bg-amber-500/10 border border-amber-500/20 px-4 py-2.5">
          <p className="text-xs text-amber-400 text-center">
            📋 See <code className="font-mono">docs/requirements.md</code> for the full feature roadmap.
          </p>
        </div>
      </div>
    </main>
  )
}
