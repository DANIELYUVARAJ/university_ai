interface KpiCardProps {
  title: string
  value: string | number
  subtitle?: string
  accentClass: string
  iconBg: string
  icon: string
  demo?: boolean
  animDelay?: string
}

export default function KpiCard({
  title,
  value,
  subtitle,
  accentClass,
  iconBg,
  icon,
  demo = true,
  animDelay = '',
}: KpiCardProps) {
  return (
    <div className={`kpi-card animate-fade-in-up opacity-0 ${animDelay}`}>
      <div className="flex items-start justify-between">
        <div className={`flex h-10 w-10 items-center justify-center rounded-xl ${iconBg} text-xl`}>
          {icon}
        </div>
        {demo && (
          <span className="badge bg-amber-500/10 text-amber-400 border border-amber-500/20 text-[10px]">
            Demo
          </span>
        )}
      </div>

      <div>
        <p className={`text-3xl font-bold ${accentClass}`}>{value}</p>
        <p className="mt-0.5 text-xs font-medium text-slate-400">{title}</p>
        {subtitle && (
          <p className="mt-1 text-[11px] text-slate-600">{subtitle}</p>
        )}
      </div>
    </div>
  )
}
