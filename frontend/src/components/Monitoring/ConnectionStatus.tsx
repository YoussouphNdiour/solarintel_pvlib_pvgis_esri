// ── ConnectionStatus ──────────────────────────────────────────────────────────
// Small pill showing WebSocket connection state with click-to-reconnect.

interface ConnectionStatusProps {
  isConnected: boolean
  reconnectAttempts: number
  onReconnect: () => void
}

export default function ConnectionStatus({
  isConnected,
  reconnectAttempts,
  onReconnect,
}: ConnectionStatusProps) {
  const isReconnecting = !isConnected && reconnectAttempts > 0 && reconnectAttempts <= 3
  const isOffline = !isConnected && reconnectAttempts > 3

  let pillClasses: string
  let dotClasses: string
  let label: string

  if (isConnected) {
    pillClasses = 'bg-green-50 text-green-700 border-green-200 hover:bg-green-100'
    dotClasses = 'bg-green-500 animate-pulse'
    label = 'Temps réel'
  } else if (isReconnecting) {
    pillClasses = 'bg-amber-50 text-amber-700 border-amber-200 hover:bg-amber-100'
    dotClasses = 'bg-amber-500 animate-pulse'
    label = `Reconnexion... (${reconnectAttempts})`
  } else if (isOffline) {
    pillClasses = 'bg-red-50 text-red-700 border-red-200 hover:bg-red-100'
    dotClasses = 'bg-red-500'
    label = 'Hors ligne'
  } else {
    // initial connecting state
    pillClasses = 'bg-amber-50 text-amber-700 border-amber-200 hover:bg-amber-100'
    dotClasses = 'bg-amber-500 animate-pulse'
    label = 'Connexion...'
  }

  return (
    <button
      type="button"
      onClick={onReconnect}
      title={isConnected ? 'Connecté — cliquer pour reconnecter' : 'Cliquer pour reconnecter'}
      className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium transition-colors ${pillClasses}`}
      aria-label={`État de la connexion WebSocket: ${label}`}
    >
      <span className={`h-2 w-2 rounded-full ${dotClasses}`} aria-hidden="true" />
      {label}
    </button>
  )
}
