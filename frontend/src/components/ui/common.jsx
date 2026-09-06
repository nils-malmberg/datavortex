/**
 * Briques d'interface partagées par les panneaux avancés (Phase 8).
 *
 * Ces composants existent pour que les nouveaux onglets (stats avancées,
 * groupby, pivot, profiling, tests statistiques…) partagent exactement la même
 * apparence et le même comportement en mode sombre, sans dupliquer les classes
 * Tailwind dans chaque fichier.
 */
import { useEffect, useRef, useState } from 'react'

export const INPUT_CLASS =
  'rounded-md border border-slate-300 bg-white px-2.5 py-1.5 text-sm text-slate-800 ' +
  'focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 ' +
  'dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100 dark:placeholder:text-slate-500'

export const BUTTON_CLASS =
  'rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-600 ' +
  'hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50 ' +
  'dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300 dark:hover:bg-slate-800'

export const PRIMARY_BUTTON_CLASS =
  'rounded-lg bg-blue-600 px-4 py-1.5 text-sm font-medium text-white hover:bg-blue-700 ' +
  'disabled:cursor-not-allowed disabled:opacity-50 dark:bg-blue-500 dark:hover:bg-blue-600'

export function Panel({ children, className = '' }) {
  return (
    <div
      className={`rounded-lg border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900 ${className}`}
    >
      {children}
    </div>
  )
}

export function SectionTitle({ children, hint }) {
  return (
    <div className="flex items-baseline gap-2">
      <h4 className="text-sm font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
        {children}
      </h4>
      {hint && <InfoTip text={hint} />}
    </div>
  )
}

/** Groupe de boutons exclusifs — utilisé pour les sous-onglets et les sélecteurs courts. */
export function Segmented({ options, value, onChange, size = 'md', ariaLabel }) {
  const pad = size === 'sm' ? 'px-2.5 py-1 text-xs' : 'px-3.5 py-1.5 text-sm'
  return (
    <div
      role="tablist"
      aria-label={ariaLabel}
      className="inline-flex flex-wrap gap-1 rounded-lg bg-slate-100 p-1 dark:bg-slate-800"
    >
      {options.map((opt) => (
        <button
          key={opt.value}
          role="tab"
          aria-selected={value === opt.value}
          title={opt.hint}
          onClick={() => onChange(opt.value)}
          className={`rounded-md font-medium transition-colors ${pad} ${
            value === opt.value
              ? 'bg-white text-blue-700 shadow-sm dark:bg-slate-950 dark:text-blue-300'
              : 'text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-100'
          }`}
        >
          {opt.label}
        </button>
      ))}
    </div>
  )
}

export function FieldSelect({ label, value, onChange, options, allowEmpty, emptyLabel = '—', hint, disabled }) {
  return (
    <label className="flex min-w-0 flex-col gap-1 text-sm">
      {label && (
        <span className="flex items-center gap-1 font-medium text-slate-600 dark:text-slate-300">
          {label}
          {hint && <InfoTip text={hint} />}
        </span>
      )}
      <select
        value={value ?? ''}
        disabled={disabled}
        onChange={(e) => onChange(e.target.value)}
        className={`${INPUT_CLASS} min-w-[9rem] disabled:opacity-50`}
      >
        {allowEmpty && <option value="">{emptyLabel}</option>}
        {options.map((opt) => {
          const val = typeof opt === 'string' ? opt : opt.value
          const text = typeof opt === 'string' ? opt : opt.label
          return (
            <option key={val} value={val}>
              {text}
            </option>
          )
        })}
      </select>
    </label>
  )
}

export function NumberField({ label, value, onChange, min, max, step = 1, hint, suffix, disabled }) {
  return (
    <label className="flex flex-col gap-1 text-sm">
      {label && (
        <span className="flex items-center gap-1 font-medium text-slate-600 dark:text-slate-300">
          {label}
          {hint && <InfoTip text={hint} />}
        </span>
      )}
      <span className="flex items-center gap-1.5">
        <input
          type="number"
          value={value}
          min={min}
          max={max}
          step={step}
          disabled={disabled}
          onChange={(e) => onChange(e.target.value === '' ? '' : Number(e.target.value))}
          className={`${INPUT_CLASS} w-24 disabled:opacity-50`}
        />
        {suffix && <span className="text-xs text-slate-500 dark:text-slate-400">{suffix}</span>}
      </span>
    </label>
  )
}

export function SliderField({ label, value, onChange, min, max, step = 1, format = (v) => v, hint }) {
  return (
    <label className="flex min-w-[11rem] flex-col gap-1 text-sm">
      <span className="flex items-center gap-1 font-medium text-slate-600 dark:text-slate-300">
        {label}
        {hint && <InfoTip text={hint} />}
        <span className="ml-auto rounded bg-slate-100 px-1.5 text-xs font-semibold text-slate-600 dark:bg-slate-800 dark:text-slate-300">
          {format(value)}
        </span>
      </span>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="accent-blue-600 dark:accent-blue-400"
      />
    </label>
  )
}

export function Toggle({ label, checked, onChange, hint }) {
  return (
    <label className="flex cursor-pointer items-center gap-2 text-sm text-slate-600 dark:text-slate-300">
      <span
        className={`relative h-5 w-9 rounded-full transition-colors ${
          checked ? 'bg-blue-600 dark:bg-blue-500' : 'bg-slate-300 dark:bg-slate-700'
        }`}
      >
        <input
          type="checkbox"
          className="sr-only"
          checked={checked}
          onChange={(e) => onChange(e.target.checked)}
        />
        <span
          className={`absolute top-0.5 h-4 w-4 rounded-full bg-white transition-transform ${
            checked ? 'translate-x-4' : 'translate-x-0.5'
          }`}
        />
      </span>
      <span className="font-medium">{label}</span>
      {hint && <InfoTip text={hint} />}
    </label>
  )
}

/** Sélection multiple sous forme de puces cliquables. */
export function ChipMultiSelect({ options, selected, onToggle, emptyMessage = 'Aucune colonne disponible.' }) {
  if (options.length === 0) {
    return <p className="text-sm text-slate-400 dark:text-slate-500">{emptyMessage}</p>
  }
  return (
    <div className="flex flex-wrap gap-1.5">
      {options.map((col) => {
        const isOn = selected.includes(col)
        return (
          <label
            key={col}
            className={`cursor-pointer select-none rounded-md border px-2.5 py-1 text-xs font-medium transition-colors ${
              isOn
                ? 'border-blue-500 bg-blue-50 text-blue-700 dark:border-blue-400 dark:bg-blue-950/40 dark:text-blue-300'
                : 'border-slate-300 bg-white text-slate-600 hover:border-slate-400 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-300'
            }`}
          >
            <input type="checkbox" className="hidden" checked={isOn} onChange={() => onToggle(col)} />
            {col}
          </label>
        )
      })}
    </div>
  )
}

export function InfoTip({ text }) {
  return (
    <span
      title={text}
      aria-label={text}
      className="inline-flex h-4 w-4 shrink-0 cursor-help items-center justify-center rounded-full border border-slate-300 text-[10px] font-bold text-slate-400 dark:border-slate-600 dark:text-slate-500"
    >
      ?
    </span>
  )
}

export function ErrorBox({ children }) {
  if (!children) return null
  return (
    <p className="rounded-md bg-red-50 px-4 py-2 text-sm text-red-700 dark:bg-red-950/40 dark:text-red-300">
      {children}
    </p>
  )
}

export function Loading({ children = 'Chargement…' }) {
  return <p className="p-4 text-sm text-slate-500 dark:text-slate-400">{children}</p>
}

export function EmptyState({ children }) {
  return (
    <div className="rounded-lg border border-dashed border-slate-300 p-8 text-center text-sm text-slate-400 dark:border-slate-700 dark:text-slate-500">
      {children}
    </div>
  )
}

export function Badge({ children, tone = 'slate' }) {
  const tones = {
    slate: 'bg-slate-200 text-slate-700 dark:bg-slate-700 dark:text-slate-200',
    blue: 'bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300',
    green: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300',
    amber: 'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300',
    red: 'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300',
    purple: 'bg-purple-100 text-purple-700 dark:bg-purple-900/40 dark:text-purple-300',
  }
  return (
    <span className={`rounded px-1.5 py-0.5 text-xs font-medium ${tones[tone] || tones.slate}`}>{children}</span>
  )
}

/** Copie une valeur dans le presse-papier et confirme visuellement pendant 1,2 s. */
export function CopyButton({ value, title = 'Copier' }) {
  const [copied, setCopied] = useState(false)
  const timer = useRef(null)

  useEffect(() => () => clearTimeout(timer.current), [])

  const copy = async () => {
    const text = String(value ?? '')
    try {
      await navigator.clipboard.writeText(text)
    } catch {
      // navigator.clipboard est indisponible hors HTTPS/localhost : on retombe
      // sur un textarea temporaire, qui fonctionne partout.
      const area = document.createElement('textarea')
      area.value = text
      area.style.position = 'fixed'
      area.style.opacity = '0'
      document.body.appendChild(area)
      area.select()
      try {
        document.execCommand('copy')
      } catch {
        return
      } finally {
        document.body.removeChild(area)
      }
    }
    setCopied(true)
    clearTimeout(timer.current)
    timer.current = setTimeout(() => setCopied(false), 1200)
  }

  return (
    <button
      onClick={copy}
      title={title}
      aria-label={title}
      className="rounded px-1 text-xs text-slate-400 opacity-0 transition-opacity hover:text-blue-600 group-hover:opacity-100 focus:opacity-100 dark:text-slate-500 dark:hover:text-blue-300"
    >
      {copied ? '✓' : '⧉'}
    </button>
  )
}

/** Ligne d'une liste de statistiques, avec bouton de copie au survol. */
export function StatRow({ label, value, hint, copyValue }) {
  return (
    <div className="group flex items-baseline justify-between gap-2 py-0.5">
      <dt className="flex items-center gap-1 text-slate-500 dark:text-slate-400">
        {label}
        {hint && <InfoTip text={hint} />}
      </dt>
      <dd className="flex items-center gap-0.5 font-medium tabular-nums text-slate-800 dark:text-slate-100">
        {value}
        <CopyButton value={copyValue ?? value} title={`Copier ${label}`} />
      </dd>
    </div>
  )
}

/** Grande valeur mise en avant (accuracy, score, nombre de groupes…). */
export function StatCard({ label, value, sub, tone = 'slate' }) {
  const tones = {
    slate: 'border-slate-200 dark:border-slate-800',
    blue: 'border-blue-300 dark:border-blue-800',
    green: 'border-emerald-300 dark:border-emerald-800',
    amber: 'border-amber-300 dark:border-amber-800',
    red: 'border-red-300 dark:border-red-800',
  }
  return (
    <div className={`group rounded-lg border bg-white p-3 dark:bg-slate-900 ${tones[tone] || tones.slate}`}>
      <p className="text-xs font-medium uppercase tracking-wide text-slate-500 dark:text-slate-400">{label}</p>
      <p className="flex items-center gap-1 text-xl font-semibold tabular-nums text-slate-800 dark:text-slate-50">
        {value}
        <CopyButton value={value} title={`Copier ${label}`} />
      </p>
      {sub && <p className="text-xs text-slate-500 dark:text-slate-400">{sub}</p>}
    </div>
  )
}

/** Formatage numérique cohérent, piloté par le curseur de précision. */
export function formatNumber(value, precision = 4) {
  if (value === null || value === undefined) return '—'
  if (typeof value === 'boolean') return value ? 'oui' : 'non'
  if (typeof value !== 'number') return String(value)
  if (!Number.isFinite(value)) return '—'
  if (Number.isInteger(value) && Math.abs(value) < 1e15) return value.toString()
  if (value !== 0 && (Math.abs(value) < 1e-4 || Math.abs(value) >= 1e9)) {
    return value.toExponential(Math.max(1, precision - 1))
  }
  return value.toFixed(precision)
}

/** p-values : notation scientifique sous 1e-4, et seuil plancher lisible. */
export function formatPValue(p) {
  if (p === null || p === undefined || !Number.isFinite(p)) return '—'
  if (p < 1e-10) return '< 1e-10'
  if (p < 1e-4) return p.toExponential(2)
  return p.toFixed(4)
}
