// ── NarrativePanel ────────────────────────────────────────────────────────────
// Displays the streaming narrative with typing cursor and clipboard copy.

import { useState } from 'react'
import { Copy, Check } from 'lucide-react'

// ── Skeleton ──────────────────────────────────────────────────────────────────

function NarrativeSkeleton() {
  return (
    <div className="space-y-2 py-1" aria-hidden="true">
      {[100, 95, 88, 100, 72, 90, 60].map((w, i) => (
        <div
          key={i}
          className={`h-3 bg-gray-200 rounded animate-pulse`}
          style={{ width: `${w}%`, animationDelay: `${i * 80}ms` }}
        />
      ))}
    </div>
  )
}

// ── Simple markdown renderer (bold + italic — no heavy library) ───────────────

function renderMarkdown(text: string): React.ReactNode[] {
  // Split on paragraph boundaries
  const paragraphs = text.split(/\n\n+/)

  return paragraphs.map((para, pIdx) => {
    // Replace **bold** and *italic* inline
    const segments: React.ReactNode[] = []
    const pattern = /(\*\*[^*]+\*\*|\*[^*]+\*)/g
    let lastIndex = 0
    let match: RegExpExecArray | null

    while ((match = pattern.exec(para)) !== null) {
      // Text before match
      if (match.index > lastIndex) {
        segments.push(para.slice(lastIndex, match.index))
      }
      const raw = match[0]
      if (raw.startsWith('**')) {
        segments.push(
          <strong key={`${pIdx}-b-${match.index}`} className="font-semibold text-gray-900">
            {raw.slice(2, -2)}
          </strong>,
        )
      } else {
        segments.push(
          <em key={`${pIdx}-i-${match.index}`} className="italic text-gray-700">
            {raw.slice(1, -1)}
          </em>,
        )
      }
      lastIndex = match.index + raw.length
    }

    // Remaining text
    if (lastIndex < para.length) {
      segments.push(para.slice(lastIndex))
    }

    return (
      <p
        key={pIdx}
        className="text-sm text-gray-700 leading-relaxed animate-[fadeSlideIn_0.4s_ease_both]"
        style={{ animationDelay: `${pIdx * 40}ms` }}
      >
        {segments}
      </p>
    )
  })
}

// ── Component ─────────────────────────────────────────────────────────────────

interface NarrativePanelProps {
  narrative: string
  isStreaming: boolean   // true while report_writer agent is running
  isLoading: boolean     // true before agent starts
}

export default function NarrativePanel({
  narrative,
  isStreaming,
  isLoading,
}: NarrativePanelProps) {
  const [copied, setCopied] = useState(false)

  function handleCopy() {
    if (narrative.trim() === '') return
    void navigator.clipboard.writeText(narrative).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }

  const isEmpty = narrative.trim() === ''

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-4 space-y-3">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-gray-800">Rapport narratif</h3>
        <button
          type="button"
          onClick={handleCopy}
          disabled={isEmpty}
          className="flex items-center gap-1.5 text-xs font-medium text-gray-500 hover:text-gray-700 disabled:opacity-30 disabled:cursor-not-allowed transition-colors px-2 py-1 rounded-lg hover:bg-gray-50"
          aria-label="Copier le rapport dans le presse-papiers"
        >
          {copied ? (
            <Check size={13} className="text-emerald-500" aria-hidden="true" />
          ) : (
            <Copy size={13} aria-hidden="true" />
          )}
          {copied ? 'Copié !' : 'Copier'}
        </button>
      </div>

      {/* Body */}
      <div
        role="status"
        aria-live="polite"
        aria-label="Texte du rapport IA"
        className="min-h-[80px]"
      >
        {isLoading && !isStreaming && isEmpty ? (
          <NarrativeSkeleton />
        ) : isEmpty && !isStreaming ? (
          <p className="text-sm text-gray-400 italic">Le rapport narratif apparaîtra ici.</p>
        ) : (
          <div className="space-y-3">
            {renderMarkdown(narrative)}
            {isStreaming && (
              <span
                className="inline-block w-0.5 h-4 bg-gray-600 ml-0.5 align-middle animate-[blink_0.8s_step-end_infinite]"
                aria-hidden="true"
              />
            )}
          </div>
        )}
      </div>
    </div>
  )
}
