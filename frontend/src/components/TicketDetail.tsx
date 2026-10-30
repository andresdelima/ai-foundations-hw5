import { AGENT_BY_NAME, STATUS_LABEL, TOOL_LABELS } from '../agents'
import type { AgentEvent, Draft, Ticket, TicketSummary } from '../api'
import { money } from '../api'

const KIND_ICON: Record<string, string> = {
  ticket_start: '🎫',
  model_step: '💭',
  tool: '🔧',
  delegate: '➡️',
  delegate_refused: '⛔',
  report: '↩️',
  decision: '⚖️',
  error: '⚠️',
  human_approve: '✍️',
  human_reject: '✋',
  run_start: '▶️',
  run_end: '⏹️',
}

export function AgentSummaries({ summary, ticket }: { summary: TicketSummary | null; ticket: Ticket | null }) {
  if (!ticket) return null
  const d = summary?.decision
  return (
    <section className="panel summary">
      <header className="panel-head">
        <div>
          <h2>What each agent did on #{ticket.id}</h2>
          <p className="sub">{summary?.run_id ? `${summary.runs ?? 1} run${(summary.runs ?? 1) > 1 ? 's (first run + follow-ups after approvals)' : ''} · latest ${summary.run_id}` : 'No run yet. Send in the team.'}</p>
        </div>
      </header>
      {d && (
        <div className={`verdict s-${d.status}`}>
          <div className="verdict-head">
            <span className="verdict-label">The Boss's call</span>
            <span className={`status-pill s-${d.status}`}>{STATUS_LABEL[d.status] ?? d.status}</span>
          </div>
          <p>{d.decision}</p>
          {d.discount && (
            <p className="discount">
              Discount {(d.discount.pct * 100).toFixed(0)}% · {money(d.discount.unit_price)} × {d.discount.qty} ={' '}
              <b>{money(d.discount.total)}</b>
              {d.discount.within_policy ? ' · within policy' : ' · outside policy, needs a person'}
            </p>
          )}
        </div>
      )}
      <div className="summ-rows">
        {summary?.agents.map((a) => {
          const meta = AGENT_BY_NAME[a.agent]
          return (
            <div className="summ" key={a.agent} style={{ ['--agent' as string]: meta.color, ['--tint' as string]: meta.tint }}>
              <img src={meta.photo} alt="" style={{ objectPosition: meta.photoPosition }} />
              <div>
                <div className="summ-head">
                  <b>{meta.title}</b>
                  {a.asked_by.length > 0 && <span>asked by {a.asked_by.map((n) => AGENT_BY_NAME[n as keyof typeof AGENT_BY_NAME]?.title ?? n).join(', ')}</span>}
                  {a.delegated_to.length > 0 && (
                    <span>→ asked {[...new Set(a.delegated_to)].map((n) => AGENT_BY_NAME[n as keyof typeof AGENT_BY_NAME]?.title ?? n).join(', ')}</span>
                  )}
                </div>
                {a.said && <p className="summ-said">{a.said}</p>}
                <div className="tools">
                  {Object.entries(a.tool_counts).map(([t, n]) => (
                    <span key={t} className="tool-chip">
                      {TOOL_LABELS[t] ?? t}
                      {n > 1 && <em>×{n}</em>}
                    </span>
                  ))}
                </div>
              </div>
              <small className="summ-tokens">{a.model_steps} steps · {a.tokens.toLocaleString()} tokens</small>
            </div>
          )
        })}
      </div>
    </section>
  )
}

export function Drafts({ drafts }: { drafts: Draft[] }) {
  if (!drafts.length) return null
  return (
    <section className="panel drafts">
      <header className="panel-head">
        <div>
          <h2>On the board: drafts</h2>
          <p className="sub">Nothing here was emailed or sent. A person reviews and sends.</p>
        </div>
      </header>
      <div className="letters">
        {drafts.map((d) => (
          <article key={d.id} className={`letter ${d.kind}`}>
            <div className="letter-head">
              <span>{d.kind === 'restock_order' ? 'Restock order' : 'Message'} #{d.id}</span>
              <span className="unsent">Draft · not sent</span>
            </div>
            <p className="letter-to">
              To: <b>{d.recipient}</b>
            </p>
            <p className="letter-subject">{d.subject}</p>
            <p className="letter-body">{d.body}</p>
            <p className="letter-by">by {AGENT_BY_NAME[d.created_by as keyof typeof AGENT_BY_NAME]?.title ?? d.created_by} · {d.created_on}</p>
          </article>
        ))}
      </div>
    </section>
  )
}

export function PlayByPlay({ events, runId }: { events: AgentEvent[]; runId: string | null }) {
  const shown = events.filter((e) => (runId ? e.run_id === runId || e.agent === 'human' : true) && e.kind !== 'run_start' && e.kind !== 'run_end')
  return (
    <section className="panel feed">
      <header className="panel-head">
        <div>
          <h2>Play-by-play</h2>
          <p className="sub">Every step from the audit trail, newest first</p>
        </div>
      </header>
      <ol className="events">
        {[...shown].reverse().map((e) => {
          const meta = e.agent === 'human' ? null : AGENT_BY_NAME[e.agent]
          return (
            <li key={e.seq} style={{ ['--agent' as string]: meta?.color ?? '#111827' }}>
              <span className="ev-icon">{KIND_ICON[e.kind] ?? '•'}</span>
              <span className="ev-who">{meta?.title ?? 'You'}</span>
              <span className="ev-text">
                {e.kind === 'delegate' && e.to ? <b>asks {AGENT_BY_NAME[e.to].title}: </b> : null}
                {e.kind === 'report' && e.to ? <b>reports to {AGENT_BY_NAME[e.to].title}: </b> : null}
                {e.kind === 'model_step' && !e.detail?.text ? <i>thinking… {e.summary}</i> : e.summary}
              </span>
              <time>{new Date(e.ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}</time>
            </li>
          )
        })}
        {!shown.length && <li className="empty-note">Nothing yet.</li>}
      </ol>
    </section>
  )
}
