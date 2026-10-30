import { AGENTS, AGENT_BY_NAME, TOOL_LABELS } from '../agents'
import type { AgentName } from '../api'
import type { Edge, LiveAgent } from '../live'

const STATUS_TEXT: Record<string, string> = {
  idle: 'Waiting for a ticket',
  thinking: 'Thinking…',
  tool: 'Using a tool',
  delegating: 'Delegating',
  reported: 'Reported back',
  decided: 'Made the call',
  error: 'Hit a limit',
}

interface Props {
  agents: Record<AgentName, LiveAgent>
  edges: Edge[]
  active: AgentName | null
  running: boolean
  ticketLabel: string | null
}

export function TeamRoom({ agents, edges, active, running, ticketLabel }: Props) {
  const openEdges = edges.filter((e) => e.open)
  return (
    <section className="panel team-room">
      <header className="panel-head">
        <div>
          <h2>The Team Room</h2>
          <p className="sub">
            {running
              ? `Working ${ticketLabel}. Watch who talks to whom.`
              : ticketLabel
                ? `Last run on ${ticketLabel}`
                : 'Pick a ticket and send in the team.'}
          </p>
        </div>
        {running && <span className="live-dot">LIVE</span>}
      </header>

      {openEdges.length > 0 && (
        <div className="relay">
          {openEdges.map((e, i) => (
            <span key={i} className="relay-chip">
              <i style={{ background: AGENT_BY_NAME[e.from].color }} />
              {AGENT_BY_NAME[e.from].title}
              <b>→</b>
              <i style={{ background: AGENT_BY_NAME[e.to].color }} />
              {AGENT_BY_NAME[e.to].title}
            </span>
          ))}
        </div>
      )}

      <div className="agents">
        {AGENTS.map((meta) => {
          const live = agents[meta.name]
          const isActive = running && active === meta.name
          const working = running && live.status !== 'idle' && live.status !== 'reported' && live.status !== 'decided'
          const uniqueTools = [...new Set(live.tools)]
          return (
            <article
              key={meta.name}
              className={`agent ${isActive ? 'active' : ''} ${live.status}`}
              style={{ ['--agent' as string]: meta.color, ['--tint' as string]: meta.tint }}
            >
              <div className="agent-photo" title={meta.landmark}>
                <img src={meta.photo} alt={meta.landmark} style={{ objectPosition: meta.photoPosition }} />
                {working && <span className="pulse" />}
              </div>
              <div className="agent-body">
                <div className="agent-name">
                  <h3>{meta.title}</h3>
                  <span className="agent-status">{STATUS_TEXT[live.status]}</span>
                </div>
                <p className="agent-role">{meta.role}</p>
                <div className={`bubble ${live.line ? '' : 'empty'}`}>
                  {live.line || (meta.name === 'boss' ? '“Bring me a ticket.”' : '“Ready when the Boss calls.”')}
                </div>
                {uniqueTools.length > 0 && (
                  <div className="tools">
                    {uniqueTools.map((t) => (
                      <span key={t} className="tool-chip">
                        {TOOL_LABELS[t] ?? t}
                        {live.tools.filter((x) => x === t).length > 1 && <em>×{live.tools.filter((x) => x === t).length}</em>}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            </article>
          )
        })}
      </div>
    </section>
  )
}
