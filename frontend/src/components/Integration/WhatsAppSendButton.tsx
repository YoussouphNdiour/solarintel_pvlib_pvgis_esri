// ── WhatsAppSendButton ────────────────────────────────────────────────────────
// Sends a generated PDF report to a Senegalese WhatsApp number.

import { useState } from 'react'
import { useSendReportWhatsApp } from '@/hooks/useIntegrations'
import type { SendReportWhatsAppRequest } from '@/types/api'

interface Props { reportId: string; disabled?: boolean }
type UIState = 'idle' | 'form' | 'sent'

// ── Phone helpers ─────────────────────────────────────────────────────────────

/** Accepted prefixes: 70-78 mobile, 33 fixed. */
const SN_PHONE_RE = /^(7[0-8]|33)\d{7}$/

function formatPhone(raw: string): string {
  const d = raw.replace(/\D/g, '').slice(0, 9)
  if (d.length <= 2) return d
  if (d.length <= 5) return `${d.slice(0, 2)} ${d.slice(2)}`
  if (d.length <= 7) return `${d.slice(0, 2)} ${d.slice(2, 5)} ${d.slice(5)}`
  return `${d.slice(0, 2)} ${d.slice(2, 5)} ${d.slice(5, 7)} ${d.slice(7)}`
}

function validatePhone(formatted: string): string | null {
  const d = formatted.replace(/\s/g, '')
  if (!d.length) return 'Le numéro est requis'
  if (d.length !== 9) return 'Le numéro doit contenir 9 chiffres'
  if (!SN_PHONE_RE.test(d)) return 'Format invalide — utilisez 77/78/76/70/33 + 7 chiffres'
  return null
}

// ── Component ─────────────────────────────────────────────────────────────────

export default function WhatsAppSendButton({ reportId, disabled = false }: Props) {
  const [uiState, setUiState] = useState<UIState>('idle')
  const [phone, setPhone] = useState('')
  const [caption, setCaption] = useState('')
  const [phoneError, setPhoneError] = useState<string | null>(null)
  const [sentTo, setSentTo] = useState('')
  const mutation = useSendReportWhatsApp()

  function open() { setUiState('form'); setPhone(''); setCaption(''); setPhoneError(null); mutation.reset() }
  function cancel() { setUiState('idle'); mutation.reset() }

  function handlePhoneChange(raw: string) {
    const f = formatPhone(raw)
    setPhone(f)
    if (phoneError !== null) setPhoneError(validatePhone(f))
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    const err = validatePhone(phone)
    if (err !== null) { setPhoneError(err); return }
    const digits = phone.replace(/\s/g, '')
    const payload: SendReportWhatsAppRequest = { reportId, phone: digits }
    const trimmed = caption.trim()
    if (trimmed.length > 0) payload.caption = trimmed
    mutation.mutate(payload, {
      onSuccess: () => { setSentTo(digits); setUiState('sent') },
    })
  }

  if (uiState === 'idle') {
    return (
      <button type="button" onClick={open} disabled={disabled}
        className="flex items-center gap-2 rounded-xl border border-green-300 bg-green-50 hover:bg-green-100 active:bg-green-200 disabled:opacity-50 disabled:cursor-not-allowed text-green-800 font-semibold py-3 px-5 text-sm transition-colors">
        <span aria-hidden="true">📱</span>Envoyer via WhatsApp
      </button>
    )
  }

  if (uiState === 'sent') {
    return (
      <div className="flex items-center gap-2 rounded-xl border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-800">
        <span aria-hidden="true">✅</span>
        <span>Envoyé à +221&nbsp;{sentTo}</span>
        <button type="button" onClick={() => setUiState('idle')}
          className="ml-auto text-xs text-green-600 hover:text-green-800 underline underline-offset-2">
          Envoyer à un autre
        </button>
      </div>
    )
  }

  const apiError = mutation.isError
    ? mutation.error instanceof Error ? mutation.error.message : 'Une erreur est survenue'
    : null

  return (
    <form onSubmit={handleSubmit} noValidate
      className="rounded-xl border border-green-200 bg-green-50/60 p-4 space-y-3"
      aria-label="Envoyer le rapport via WhatsApp">
      <div>
        <label htmlFor="wa-phone" className="block text-xs font-medium text-gray-700 mb-1">
          <span aria-hidden="true">🇸🇳</span> Numéro WhatsApp
        </label>
        <input id="wa-phone" type="tel" inputMode="numeric" value={phone} autoComplete="tel-national"
          onChange={(e) => handlePhoneChange(e.target.value)} placeholder="77 XXX XX XX"
          aria-describedby={phoneError !== null ? 'wa-phone-error' : 'wa-phone-hint'}
          aria-invalid={phoneError !== null}
          className={`w-full rounded-lg border px-3 py-2 text-sm bg-white text-gray-900 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-green-400 focus:border-transparent ${phoneError !== null ? 'border-red-400' : 'border-gray-200'}`} />
        {phoneError !== null
          ? <p id="wa-phone-error" role="alert" className="mt-1 text-xs text-red-600">{phoneError}</p>
          : <p id="wa-phone-hint" className="mt-1 text-xs text-gray-400">Format : 77/78/76/70/33 XX XX XX</p>}
      </div>
      <div>
        <label htmlFor="wa-caption" className="block text-xs font-medium text-gray-700 mb-1">
          Message accompagnateur <span className="text-gray-400">(optionnel)</span>
        </label>
        <textarea id="wa-caption" rows={2} maxLength={200} value={caption}
          onChange={(e) => setCaption(e.target.value.slice(0, 200))}
          placeholder="Ex : Voici votre rapport solaire SolarIntel."
          className="w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-900 placeholder:text-gray-400 resize-none focus:outline-none focus:ring-2 focus:ring-green-400 focus:border-transparent" />
        <p className="mt-0.5 text-right text-xs text-gray-400">{caption.length}/200</p>
      </div>
      {apiError !== null && <p role="alert" className="text-xs text-red-600">{apiError}</p>}
      <div className="flex gap-2">
        <button type="submit" disabled={mutation.isPending}
          className="flex items-center gap-2 rounded-xl bg-green-600 hover:bg-green-700 active:bg-green-800 disabled:opacity-60 text-white font-semibold py-2.5 px-4 text-sm transition-colors">
          {mutation.isPending
            ? <><span className="inline-block w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" aria-hidden="true" />Envoi en cours...</>
            : 'Envoyer'}
        </button>
        <button type="button" onClick={cancel} disabled={mutation.isPending}
          className="rounded-xl border border-gray-300 bg-white hover:bg-gray-50 disabled:opacity-60 text-gray-700 font-semibold py-2.5 px-4 text-sm transition-colors">
          Annuler
        </button>
      </div>
    </form>
  )
}
