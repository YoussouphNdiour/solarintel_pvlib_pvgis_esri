// ── EquipmentPage ─────────────────────────────────────────────────────────────
// Catalogue of solar equipment with live Senegalese market prices.

import { Link } from 'react-router-dom'
import EquipmentPriceTable from '@/components/Integration/EquipmentPriceTable'

// ── Inline wrench icon (lucide-style) ─────────────────────────────────────────

function IconWrench() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width="22"
      height="22"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z" />
    </svg>
  )
}

function IconChevronLeft() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <polyline points="15 18 9 12 15 6" />
    </svg>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function EquipmentPage() {
  return (
    <div className="max-w-4xl mx-auto px-4 py-6 space-y-6">
      {/* Back link */}
      <Link
        to="/dashboard"
        className="inline-flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700 transition-colors"
      >
        <IconChevronLeft />
        Retour au tableau de bord
      </Link>

      {/* Page header */}
      <header className="flex items-start gap-4">
        <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-solar-100 text-solar-600">
          <IconWrench />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-gray-900">
            Catalogue Équipements
          </h1>
          <p className="mt-1 text-sm text-gray-500">
            Prix du marché sénégalais, actualisés hebdomadairement
          </p>
        </div>
      </header>

      {/* Price table */}
      <section aria-label="Prix des équipements solaires">
        <EquipmentPriceTable />
      </section>

      {/* Disclaimer */}
      <p className="text-xs text-gray-400 text-center">
        Ces prix sont fournis à titre indicatif. Contactez directement les fournisseurs
        pour obtenir un devis personnalisé.
      </p>
    </div>
  )
}
