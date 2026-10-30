// Talks to the FastAPI backend from P7. Start it with:
//   cd backend && uvicorn main:app --reload --port 8000
export const API_BASE = 'http://localhost:8000'

export type AgentName = 'boss' | 'inventory' | 'accounting' | 'facilities' | 'customer_service'
export type TicketStatus = 'open' | 'in_progress' | 'waiting_approval' | 'blocked' | 'resolved'

export interface Ticket {
  id: number
  type: string
  requester: string
  subject: string
  sku: string | null
  size: string | null
  qty: number | null
  lease_id: number | null
  invoice_id: number | null
  status: TicketStatus
  notes: string | null
  created_at: string
  board_state: 'open' | 'resolved'
}

export interface AgentEvent {
  seq: number
  ts: string
  run_id: string
  ticket_id: number | null
  kind: string
  agent: AgentName | 'human'
  chain: string[]
  to: AgentName | null
  model: string | null
  detail: Record<string, any>
  summary: string
}

export interface Cash {
  today: string
  account: string
  balance: number
  as_of: string
  committed_to_requests: number
  available_after_requests: number
}

export interface PaymentRequest {
  id: number
  kind: 'invoice' | 'rent'
  ref_id: number
  amount: number
  payee: string
  reason: string | null
  ticket_id: number | null
  requested_by: string
  status: 'pending' | 'approved' | 'rejected' | 'paid'
  requested_on: string
  decided_by: string | null
  decided_on: string | null
  payment_id: number | null
}

export interface Payment {
  id: number
  kind: string
  ref_id: number
  amount: number
  account: string
  paid_at: string
  approved_by: string
}

export interface Draft {
  id: number
  ticket_id: number | null
  kind: 'customer_message' | 'restock_order'
  recipient: string
  subject: string
  body: string
  created_by: string
  created_on: string
  status: string
}

export interface AgentSummary {
  agent: AgentName
  asked_by: string[]
  delegated_to: string[]
  tools: string[]
  tool_counts: Record<string, number>
  said: string | null
  model_steps: number
  tokens: number
}

export interface Decision {
  ticket_id: number
  decision: string
  status: TicketStatus
  who_worked: AgentName[]
  payment_request_ids: number[]
  draft_ids: number[]
  discount: { pct: number; unit_price: number; qty: number; total: number; within_policy: boolean; needs_human: boolean } | null
  note: string
}

export interface TicketSummary {
  ticket_id: number
  run_id: string | null
  runs?: number
  started?: string
  agents: AgentSummary[]
  decision: Decision | null
}

export interface RunResult {
  run_id: string
  ticket_id: number
  decision: Decision & { error?: string }
  delegations: number
  usage: { requests: number; input_tokens: number; output_tokens: number }
}

export interface ApproveResult {
  approved: boolean
  message: string
  cash: Cash
  ticket_id: number | null
  followup_ready: boolean
  payment: { amount: number; payee: string; new_balance: number }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
  })
  const body = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(body?.detail ?? `${res.status} ${res.statusText}`)
  return body as T
}

export const api = {
  health: () => request<{ ok: boolean; model: string; agent_running: boolean }>('/api/health'),
  tickets: () => request<{ tickets: Ticket[]; open: number; resolved: number }>('/api/tickets'),
  runTicket: (id: number) => request<RunResult>(`/api/tickets/${id}/run`, { method: 'POST' }),
  summary: (id: number) => request<TicketSummary>(`/api/tickets/${id}/summary`),
  events: (params: { since?: number; ticket_id?: number; limit?: number }) => {
    const q = new URLSearchParams()
    Object.entries(params).forEach(([k, v]) => v !== undefined && q.set(k, String(v)))
    return request<{ events: AgentEvent[]; last_seq: number; agent_running: boolean }>(`/api/events?${q}`)
  },
  cash: () => request<Cash>('/api/cash'),
  payments: () => request<{ requests: PaymentRequest[]; payments: Payment[]; total_paid: number } & Cash>('/api/payments'),
  approve: (id: number, approver: string) =>
    request<ApproveResult>(`/api/payments/${id}/approve`, { method: 'POST', body: JSON.stringify({ approver }) }),
  reject: (id: number, approver: string, note?: string) =>
    request<{ rejected: boolean; message: string }>(`/api/payments/${id}/reject`, {
      method: 'POST',
      body: JSON.stringify({ approver, note }),
    }),
  drafts: (ticketId?: number) => request<{ drafts: Draft[] }>(`/api/drafts${ticketId ? `?ticket_id=${ticketId}` : ''}`),
  reset: () => request<{ reset: boolean }>('/api/reset', { method: 'POST' }),
}

export const money = (n: number) =>
  n.toLocaleString('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: 2 })
