import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { AgentEvent, Cash, Draft, Payment, PaymentRequest, Ticket, TicketSummary } from './api'
import { api, money } from './api'
import { TICKET_ICONS } from './agents'
import { deriveLive, latestRunId } from './live'
import { TeamRoom } from './components/TeamRoom'
import { TicketBoard } from './components/TicketBoard'
import { Approvals, CashLedger } from './components/Ledger'
import { AgentSummaries, Drafts, PlayByPlay } from './components/TicketDetail'
import { Credits } from './components/Credits'

interface Toast {
  id: number
  text: string
  tone: 'info' | 'good' | 'bad'
}

export default function App() {
  const [online, setOnline] = useState<boolean | null>(null)
  const [model, setModel] = useState('')
  const [tickets, setTickets] = useState<Ticket[]>([])
  const [selected, setSelected] = useState<number | null>(null)
  const [events, setEvents] = useState<AgentEvent[]>([])
  const [summary, setSummary] = useState<TicketSummary | null>(null)
  const [drafts, setDrafts] = useState<Draft[]>([])
  const [cash, setCash] = useState<Cash | null>(null)
  const [requests, setRequests] = useState<PaymentRequest[]>([])
  const [payments, setPayments] = useState<Payment[]>([])
  const [runningId, setRunningId] = useState<number | null>(null)
  const [busyApproval, setBusyApproval] = useState<number | null>(null)
  const [approver, setApprover] = useState(() => localStorage.getItem('cc-approver') ?? '')
  const [autoFollowUp, setAutoFollowUp] = useState(true)
  const [lastDrop, setLastDrop] = useState<number | null>(null)
  const [justResolved, setJustResolved] = useState<number | null>(null)
  const [toasts, setToasts] = useState<Toast[]>([])
  const lastSeq = useRef(0)
  const prevStatus = useRef<Record<number, string>>({})

  useEffect(() => localStorage.setItem('cc-approver', approver), [approver])

  const toast = useCallback((text: string, tone: Toast['tone'] = 'info') => {
    const id = Date.now() + Math.random()
    setToasts((t) => [...t, { id, text, tone }])
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 6000)
  }, [])

  // ---------------------------------------------------------------- loading
  const loadTickets = useCallback(async () => {
    const r = await api.tickets()
    setTickets(r.tickets)
    for (const t of r.tickets) {
      const before = prevStatus.current[t.id]
      if (before && before !== 'resolved' && t.status === 'resolved') {
        setJustResolved(t.id)
        toast(`Boola boola! Ticket #${t.id} is resolved.`, 'good')
        setTimeout(() => setJustResolved(null), 4000)
      }
      prevStatus.current[t.id] = t.status
    }
    setSelected((s) => s ?? r.tickets[0]?.id ?? null)
  }, [toast])

  const loadMoney = useCallback(async () => {
    const [c, p] = await Promise.all([api.cash(), api.payments()])
    setCash(c)
    setRequests(p.requests)
    setPayments(p.payments)
  }, [])

  const loadTicketDetail = useCallback(async (id: number) => {
    const [s, d] = await Promise.all([api.summary(id), api.drafts(id)])
    setSummary(s)
    setDrafts(d.drafts)
  }, [])

  const loadEvents = useCallback(async (id: number, fresh: boolean) => {
    const r = await api.events(fresh ? { ticket_id: id, limit: 400 } : { ticket_id: id, since: lastSeq.current })
    lastSeq.current = r.last_seq
    // Two polls can overlap (timer + end of run), so merge by sequence number to avoid duplicates.
    setEvents((old) => {
      if (fresh) return r.events
      const seen = new Set(old.map((e) => e.seq))
      return [...old, ...r.events.filter((e) => !seen.has(e.seq))].slice(-600)
    })
  }, [])

  // First load + health check
  useEffect(() => {
    api
      .health()
      .then((h) => {
        setOnline(true)
        setModel(h.model)
        return Promise.all([loadTickets(), loadMoney()])
      })
      .catch(() => setOnline(false))
  }, [loadTickets, loadMoney])

  // When the selected ticket changes, load its history
  useEffect(() => {
    if (selected === null) return
    loadEvents(selected, true).catch(() => {})
    loadTicketDetail(selected).catch(() => {})
  }, [selected, loadEvents, loadTicketDetail])

  // Polling: fast while the team works, slow otherwise
  useEffect(() => {
    if (!online || selected === null) return
    const fast = runningId !== null
    const t = setInterval(() => {
      loadEvents(selected, false).catch(() => {})
      if (fast) loadTickets().catch(() => {})
    }, fast ? 900 : 4000)
    const slow = setInterval(() => {
      loadTickets().catch(() => {})
      loadMoney().catch(() => {})
    }, 5000)
    return () => {
      clearInterval(t)
      clearInterval(slow)
    }
  }, [online, selected, runningId, loadEvents, loadTickets, loadMoney])

  // ---------------------------------------------------------------- actions
  const runTicket = useCallback(
    async (id: number, why?: string) => {
      setSelected(id)
      setRunningId(id)
      toast(why ?? `The Boss is reading ticket #${id}…`)
      try {
        const r = await api.runTicket(id)
        const d = r.decision
        if (d.error) toast(`Run on #${id} stopped: ${d.error}`, 'bad')
        else toast(`#${id}: ${d.status.replace('_', ' ')} · ${r.usage.requests} model calls`, d.status === 'resolved' ? 'good' : 'info')
      } catch (e) {
        toast(`Couldn't run #${id}: ${(e as Error).message}`, 'bad')
      } finally {
        setRunningId(null)
        await Promise.all([loadTickets(), loadMoney(), loadEvents(id, false), loadTicketDetail(id)]).catch(() => {})
      }
    },
    [toast, loadTickets, loadMoney, loadEvents, loadTicketDetail],
  )

  const approve = useCallback(
    async (r: PaymentRequest) => {
      setBusyApproval(r.id)
      try {
        const res = await api.approve(r.id, approver.trim())
        setLastDrop(res.payment.amount)
        toast(`Paid ${money(res.payment.amount)} to ${res.payment.payee}. Checking is now ${money(res.payment.new_balance)}.`, 'good')
        await loadMoney()
        if (res.followup_ready && res.ticket_id && autoFollowUp) {
          setBusyApproval(null)
          await runTicket(res.ticket_id, `Payment cleared. Sending the team back to finish #${res.ticket_id}…`)
        }
      } catch (e) {
        toast((e as Error).message, 'bad')
        await loadMoney()
      } finally {
        setBusyApproval(null)
      }
    },
    [approver, autoFollowUp, toast, loadMoney, runTicket],
  )

  const reject = useCallback(
    async (r: PaymentRequest) => {
      setBusyApproval(r.id)
      try {
        const res = await api.reject(r.id, approver.trim(), 'Rejected on the dashboard')
        toast(res.message)
        await loadMoney()
      } catch (e) {
        toast((e as Error).message, 'bad')
      } finally {
        setBusyApproval(null)
      }
    },
    [approver, toast, loadMoney],
  )

  const reset = useCallback(async () => {
    if (!window.confirm('Reset the shop to the original database? Payments, drafts and ticket progress go back to the start. The audit trail is kept.')) return
    await api.reset()
    prevStatus.current = {}
    setLastDrop(null)
    toast('Fresh start: the shop is back to the original data.')
    await Promise.all([loadTickets(), loadMoney()])
    if (selected !== null) {
      await loadEvents(selected, true)
      await loadTicketDetail(selected)
    }
  }, [toast, loadTickets, loadMoney, loadEvents, loadTicketDetail, selected])

  // ----------------------------------------------------------------- derive
  const ticket = tickets.find((t) => t.id === selected) ?? null
  const runId = useMemo(() => latestRunId(events), [events])
  const live = useMemo(() => deriveLive(events, runId), [events, runId])
  const pendingCount = requests.filter((r) => r.status === 'pending').length

  if (online === false) {
    return (
      <div className="offline">
        <img src="/yale/handsome-dan-1890.jpg" alt="Handsome Dan" />
        <h1>The backend is asleep</h1>
        <p>Start it from the <code>backend/</code> folder, then reload this page:</p>
        <pre>uvicorn main:app --reload --port 8000</pre>
      </div>
    )
  }

  return (
    <div className="app">
      <header className="hero">
        <div className="hero-inner">
          <div className="brand">
            <span className="crest">CC</span>
            <div>
              <h1>Campus Customs · Ops Desk</h1>
              <p>Chapel Street, New Haven · Shop date <b>{cash?.today ?? '…'}</b> · Every agent on <b>{model || '…'}</b></p>
            </div>
          </div>
          <div className="hero-stats">
            <div>
              <span>Checking</span>
              <b>{cash ? money(cash.balance) : '…'}</b>
            </div>
            <div>
              <span>Open tickets</span>
              <b>{tickets.filter((t) => t.board_state === 'open').length}</b>
            </div>
            <div className={pendingCount ? 'attention' : ''}>
              <span>To sign</span>
              <b>{pendingCount}</b>
            </div>
            <button className="btn ghost light" onClick={reset} disabled={runningId !== null}>
              Reset shop
            </button>
          </div>
        </div>
        <p className="hero-motto">Lux et Veritas · and every payment signed by a person</p>
      </header>

      <main className="grid">
        <div className="col-left">
          <TicketBoard
            tickets={tickets}
            selected={selected}
            runningId={runningId}
            justResolved={justResolved}
            onSelect={setSelected}
            onRun={(id) => runTicket(id)}
          />
          <CashLedger cash={cash} payments={payments} lastDrop={lastDrop} />
        </div>

        <div className="col-mid">
          <TeamRoom
            agents={live.agents}
            edges={live.edges}
            active={live.active}
            running={runningId !== null && runningId === selected}
            ticketLabel={ticket ? `${TICKET_ICONS[ticket.type] ?? ''} #${ticket.id} ${ticket.subject}` : null}
          />
          <AgentSummaries summary={summary} ticket={ticket} />
          <Drafts drafts={drafts} />
        </div>

        <div className="col-right">
          <Approvals
            requests={requests}
            approver={approver}
            setApprover={setApprover}
            busyId={busyApproval}
            locked={runningId !== null}
            onApprove={approve}
            onReject={reject}
          />
          <label className="auto-follow">
            <input type="checkbox" checked={autoFollowUp} onChange={(e) => setAutoFollowUp(e.target.checked)} />
            After I approve a ticket's last payment, send the team back to finish it
          </label>
          <PlayByPlay events={events} runId={runId} />
        </div>
      </main>

      <Credits />

      <div className="toasts">
        {toasts.map((t) => (
          <div key={t.id} className={`toast ${t.tone}`}>
            {t.tone === 'good' && <img src="/yale/handsome-dan-1890.jpg" alt="" />}
            {t.text}
          </div>
        ))}
      </div>
      {justResolved !== null && <Confetti />}
    </div>
  )
}

function Confetti() {
  const pieces = Array.from({ length: 36 }, (_, i) => i)
  return (
    <div className="confetti" aria-hidden>
      {pieces.map((i) => (
        <span
          key={i}
          style={{
            left: `${(i * 37) % 100}%`,
            animationDelay: `${(i % 9) * 0.08}s`,
            background: i % 3 === 0 ? '#00356b' : i % 3 === 1 ? '#286dc0' : '#ffffff',
          }}
        >
          {i % 6 === 0 ? 'Y' : ''}
        </span>
      ))}
    </div>
  )
}
