import type { AgentEvent, AgentName } from './api'
import { TOOL_LABELS } from './agents'

// Turns the audit-trail events of one run into "what is each agent doing right now".
export type LiveStatus = 'idle' | 'thinking' | 'tool' | 'delegating' | 'reported' | 'decided' | 'error'

export interface LiveAgent {
  status: LiveStatus
  line: string
  tools: string[]
  lastSeq: number
}

export interface Edge {
  from: AgentName
  to: AgentName
  open: boolean
}

const NAMES: AgentName[] = ['boss', 'inventory', 'accounting', 'facilities', 'customer_service']
const LABEL: Record<AgentName, string> = {
  boss: 'Boss',
  inventory: 'Inventory',
  accounting: 'Accounting',
  facilities: 'Facilities',
  customer_service: 'Customer Service',
}

export function latestRunId(events: AgentEvent[]): string | null {
  for (let i = events.length - 1; i >= 0; i--) if (events[i].run_id) return events[i].run_id
  return null
}

export function deriveLive(events: AgentEvent[], runId: string | null) {
  const agents = Object.fromEntries(
    NAMES.map((n) => [n, { status: 'idle', line: '', tools: [], lastSeq: 0 } as LiveAgent]),
  ) as Record<AgentName, LiveAgent>
  const edges: Edge[] = []
  let active: AgentName | null = null

  for (const e of events) {
    if (!runId || e.run_id !== runId || e.agent === 'human') continue
    const me = agents[e.agent as AgentName]
    const d = e.detail ?? {}
    me.lastSeq = e.seq
    active = e.agent as AgentName
    switch (e.kind) {
      case 'model_step':
        me.status = 'thinking'
        if (d.text) me.line = d.text
        break
      case 'tool':
        me.status = 'tool'
        me.tools.push(d.tool)
        me.line = `${TOOL_LABELS[d.tool] ?? d.tool}: ${e.summary}`
        break
      case 'delegate': {
        const to = e.to as AgentName
        me.status = 'delegating'
        me.line = `Asks ${LABEL[to]}: ${d.task ?? ''}`
        agents[to].status = 'thinking'
        agents[to].line = `Picking up a task from ${LABEL[e.agent as AgentName]}…`
        agents[to].lastSeq = e.seq
        edges.push({ from: e.agent as AgentName, to, open: true })
        break
      }
      case 'delegate_refused':
        me.line = `Couldn't ask ${LABEL[e.to as AgentName]}: ${d.reason ?? ''}`
        break
      case 'report': {
        me.status = 'reported'
        me.line = d.summary ?? ''
        const edge = [...edges].reverse().find((x) => x.from === e.to && x.to === e.agent && x.open)
        if (edge) edge.open = false
        if (e.to) agents[e.to as AgentName].status = 'thinking'
        break
      }
      case 'decision':
        me.status = 'decided'
        me.line = d.decision ?? ''
        break
      case 'error':
        me.status = 'error'
        me.line = d.error ?? ''
        break
    }
  }
  return { agents, edges, active }
}
