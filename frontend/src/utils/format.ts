// ── Formatting utilities for SolarIntel v2 ───────────────────────────────────

/**
 * Format a monetary value in FCFA using French locale spacing.
 * e.g. 1234567 → "1 234 567 FCFA"
 */
export function formatFCFA(value: number): string {
  const formatted = Math.round(value).toLocaleString('fr-FR')
  return `${formatted} FCFA`
}

/**
 * Format an energy value in kWh using French locale spacing.
 * e.g. 12345 → "12 345 kWh"
 */
export function formatKwh(value: number): string {
  const formatted = Number(value.toFixed(1)).toLocaleString('fr-FR')
  return `${formatted} kWh`
}

/**
 * Format a peak power value in kWc.
 * e.g. 12.5 → "12.5 kWc"
 */
export function formatKwc(value: number): string {
  const formatted = Number(value.toFixed(2)).toLocaleString('fr-FR')
  return `${formatted} kWc`
}

export const MONTHS_FR = [
  'Jan', 'Fév', 'Mar', 'Avr', 'Mai', 'Jun',
  'Jul', 'Aoû', 'Sep', 'Oct', 'Nov', 'Déc',
] as const

/**
 * Format a date string as relative time in French.
 * e.g. "il y a 2 heures", "il y a 3 jours", "à l'instant"
 */
export function formatRelativeTime(dateString: string): string {
  const rtf = new Intl.RelativeTimeFormat('fr', { numeric: 'auto' })
  const diffMs = new Date(dateString).getTime() - Date.now()
  const diffSec = Math.round(diffMs / 1000)
  const diffMin = Math.round(diffSec / 60)
  const diffHrs = Math.round(diffMin / 60)
  const diffDays = Math.round(diffHrs / 24)

  if (Math.abs(diffSec) < 60) return "à l'instant"
  if (Math.abs(diffMin) < 60) return rtf.format(diffMin, 'minute')
  if (Math.abs(diffHrs) < 24) return rtf.format(diffHrs, 'hour')
  return rtf.format(diffDays, 'day')
}

/**
 * Format a byte count as a human-readable file size in French.
 * e.g. 1200000 → "1,1 Mo", 340000 → "332 Ko"
 */
export function formatFileSize(bytes: number): string {
  if (bytes >= 1_000_000) {
    return `${(bytes / 1_000_000).toLocaleString('fr-FR', { maximumFractionDigits: 1 })} Mo`
  }
  return `${Math.round(bytes / 1_000).toLocaleString('fr-FR')} Ko`
}
