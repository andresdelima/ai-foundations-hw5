import { STATUS_LABEL, TICKET_ICONS } from '../agents'
import type { Ticket } from '../api'

interface Props {
  tickets: Ticket[]
  selected: number | null
  runningId: number | null
  justResolved: number | null
  onSelect: (id: number) => void
  onRun: (id: number) => void
}

function detail(t: Ticket) {
  if (t.type === 'customer_order') return `${t.qty} × ${t.sku} · size ${t.size}`
  if (t.type === 'price_override') return `${t.qty} × ${t.sku} · size ${t.size} · bulk discount`
  if (t.type === 'rent_notice') return `Lease ${t.lease_id} · Chapel Street shop`
  return t.subject
}

export function TicketBoard({ tickets, selected, runningId, justResolved, onSelect, onRun }: Props) {
  return (
    <section className="panel board">
      <header className="panel-head">
        <div>
          <h2>Ticket Board</h2>
          <p className="sub">
            {tickets.filter((t) => t.board_state === 'resolved').length} of {tickets.length} resolved
          </p>
        </div>
      </header>
      <div className="tickets">
        {tickets.map((t) => {
          const running = runningId === t.id
          return (
            <article
              key={t.id}
              className={`ticket s-${t.status} ${selected === t.id ? 'selected' : ''} ${running ? 'running' : ''}`}
              onClick={() => onSelect(t.id)}
            >
              <div className="ticket-top">
                <span className="ticket-icon">{TICKET_ICONS[t.type] ?? '📌'}</span>
                <span className="ticket-id">#{t.id}</span>
                <span className={`status-pill s-${t.status}`}>{running ? 'Team at work' : STATUS_LABEL[t.status]}</span>
              </div>
              <h3>{t.subject}</h3>
              <p className="ticket-who">{t.requester}</p>
              <p className="ticket-detail">{detail(t)}</p>
              {t.status === 'resolved' && (
                <div className={`stamp ${justResolved === t.id ? 'fresh' : ''}`}>Resolved</div>
              )}
              <button
                className="btn run"
                disabled={runningId !== null || t.status === 'resolved'}
                onClick={(e) => {
                  e.stopPropagation()
                  onRun(t.id)
                }}
              >
                {running ? 'Working…' : t.status === 'open' ? 'Send in the team' : t.status === 'resolved' ? 'Done' : 'Run again'}
              </button>
            </article>
          )
        })}
      </div>
    </section>
  )
}
