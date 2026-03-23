// ── ComingSoon ────────────────────────────────────────────────────────────────

interface ComingSoonProps {
  label: string
}

export default function ComingSoon({ label }: ComingSoonProps) {
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center rounded-2xl border-2 border-dashed border-gray-300 bg-white p-12 text-center">
      <div className="mb-4 text-5xl" aria-hidden="true">🚧</div>
      <h2 className="text-xl font-bold text-gray-900">{label}</h2>
      <p className="mt-2 text-sm text-gray-500">
        Cette fonctionnalité est en cours de développement.
      </p>
      <span className="mt-4 inline-flex items-center rounded-full bg-solar-100 px-3 py-1 text-xs font-medium text-solar-700">
        Bientôt disponible
      </span>
    </div>
  )
}
