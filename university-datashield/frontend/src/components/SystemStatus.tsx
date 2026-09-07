import type { BackendStatus, HealthResponse } from '../types'

interface StatusRowProps {
  label: string
  value: string
  statusOk: boolean | null   // null = neutral / info
  detail?: string
}

function StatusRow({ label, value, statusOk, detail }: StatusRowProps) {
  const dotColor =
    statusOk === true  ? 'bg-emerald-400' :
    statusOk === false ? 'bg-red-400'     :
                         'bg-blue-400'

  const textColor =
    statusOk === true  ? 'text-emerald-400' :
    statusOk === false ? 'text-red-400'     :
                         'text-blue-300'

  return (
    <div className="flex items-center justify-between py-2.5 border-b border-[rgb(var(--color-border))] last:border-0">
      <div className="flex items-center gap-2.5">
        <span className={`status-dot ${dotColor}`} />
        <span className="text-sm text-slate-300">{label}</span>
      </div>
      <div className="text-right">
        <span className={`text-sm font-medium ${textColor}`}>{value}</span>
        {detail && <p className="text-[10px] text-slate-600 mt-0.5">{detail}</p>}
      </div>
    </div>
  )
}

interface SystemStatusProps {
  backendStatus: BackendStatus
  healthData: HealthResponse | null
  error: string | null
  lastChecked: Date | null
  onRefresh: () => void
}

export default function SystemStatus({
  backendStatus,
  healthData,
  error,
  lastChecked,
  onRefresh,
}: SystemStatusProps) {
  const apiLabel =
    backendStatus === 'online'   ? 'Online' :
    backendStatus === 'offline'  ? 'Offline' :
                                   'Checking…'

  const dbLabel =
    !healthData          ? '—' :
    healthData.database.ok ? 'Connected' : 'Error'

  const lastCheckedStr = lastChecked
    ? lastChecked.toLocaleTimeString()
    : '—'

  return (
    <div className="card p-5">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-sm font-semibold text-white">System Status</h2>
          <p className="text-[11px] text-slate-500 mt-0.5">
            Last checked: {lastCheckedStr}
          </p>
        </div>
        <button
          onClick={onRefresh}
          className="text-xs text-slate-400 hover:text-slate-200 transition-colors
                     rounded-md px-2.5 py-1.5 bg-white/5 hover:bg-white/10"
          title="Refresh status"
        >
          ↻ Refresh
        </button>
      </div>

      <StatusRow
        label="Backend API"
        value={apiLabel}
        statusOk={
          backendStatus === 'online'  ? true  :
          backendStatus === 'offline' ? false : null
        }
        detail={error ?? (healthData ? `v${healthData.version}` : undefined)}
      />
      <StatusRow
        label="Database"
        value={dbLabel}
        statusOk={
          !healthData ? null :
          healthData.database.ok ? true : false
        }
        detail={
          healthData?.database.ok
            ? `${healthData.database.event_count ?? 0} event(s) recorded`
            : healthData?.database.error
        }
      />
      <StatusRow
        label="Environment"
        value="Development"
        statusOk={null}
        detail="Phase 1 — Foundation"
      />
      <StatusRow
        label="Data Mode"
        value="Synthetic Data Only"
        statusOk={null}
        detail="No real student data is used"
      />
    </div>
  )
}
