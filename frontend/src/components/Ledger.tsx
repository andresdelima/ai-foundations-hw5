import { useEffect, useRef, useState } from 'react'
import { AGENT_BY_NAME } from '../agents'
import type { AgentName, Cash, Payment, PaymentRequest } from '../api'
import { money } from '../api'

// Counts smoothly from the old balance to the new one so a payment visibly "drops" the cash.
function useCountTo(target: number) {
  const [shown, setShown] = useState(target)
  const from = useRef(target)
  useEffect(() => {
    const start = performance.now()
    const a = from.current
    let raf = 0
    const tick = (now: number) => {
      const k = Math.min(1, (now - start) / 1200)
      const eased = 1 - Math.pow(1 - k, 3)
      setShown(a + (target - a) * eased)
      if (k < 1) raf = requestAnimationFrame(tick)
      else from.current = target
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [target])
  return shown
}

interface CashProps {
  cash: Cash | null
  payments: Payment[]
  lastDrop: number | null
}

export function CashLedger({ cash, payments, lastDrop }: CashProps) {
  const balance = useCountTo(cash?.balance ?? 0)
  const committedPct = cash && cash.balance > 0 ? Math.min(100, (cash.committed_to_requests / cash.balance) * 100) : 0
  return (
    <section className="panel ledger">
      <header className="panel-head">
        <div>
          <h2>Checking</h2>
          <p className="sub">cash_accounts · as of {cash?.as_of ?? '…'}</p>
        </div>
      </header>
      <div className="balance">
        <span className="balance-num">{money(balance)}</span>
        {lastDrop !== null && <span key={lastDrop} className="drop">−{money(lastDrop)}</span>}
      </div>
      {cash && (
        <>
          <div className="commit-bar" title="Share of the balance already promised to pending requests">
            <span style={{ width: `${committedPct}%` }} />
          </div>
          <div className="commit-legend">
            <span><i className="c-committed" /> Promised to pending requests: {money(cash.committed_to_requests)}</span>
            <span><i className="c-free" /> Free after that: {money(cash.available_after_requests)}</span>
          </div>
        </>
      )}
      <p className="cash-rule">Cash only goes out in this shop, and it never goes below $0.</p>
      {payments.length > 0 && (
        <ul className="paid-list">
          {payments.map((p) => (
            <li key={p.id}>
              <span>{p.kind === 'invoice' ? `Invoice ${p.ref_id}` : `Rent · lease ${p.ref_id}`}</span>
              <span className="minus">−{money(p.amount)}</span>
              <small>approved by {p.approved_by}</small>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

interface ApprovalProps {
  requests: PaymentRequest[]
  approver: string
  setApprover: (s: string) => void
  busyId: number | null
  locked: boolean
  onApprove: (r: PaymentRequest) => void
  onReject: (r: PaymentRequest) => void
}

export function Approvals({ requests, approver, setApprover, busyId, locked, onApprove, onReject }: ApprovalProps) {
  const pending = requests.filter((r) => r.status === 'pending')
  const decided = requests.filter((r) => r.status !== 'pending').slice(-3).reverse()
  return (
    <section className={`panel approvals ${pending.length ? 'has-pending' : ''}`}>
      <header className="panel-head">
        <div>
          <h2>Needs your signature</h2>
          <p className="sub">Agents only prepare payments. Nothing is paid until a person approves it here.</p>
        </div>
        {pending.length > 0 && <span className="count-badge">{pending.length}</span>}
      </header>

      <label className="approver">
        <span>Signing as</span>
        <input value={approver} onChange={(e) => setApprover(e.target.value)} placeholder="Your name" />
      </label>

      {pending.length === 0 && <p className="empty-note">No payments waiting. The agents will ask here when they need one.</p>}

      {pending.map((r) => {
        const by = AGENT_BY_NAME[r.requested_by as AgentName]
        return (
          <article key={r.id} className="cheque">
            <div className="cheque-top">
              <span className="cheque-no">Request #{r.id}</span>
              <span className="cheque-ticket">Ticket {r.ticket_id ?? '—'}</span>
            </div>
            <div className="cheque-pay">
              Pay to <b>{r.payee}</b>
            </div>
            <div className="cheque-amount">{money(r.amount)}</div>
            <p className="cheque-memo">
              {r.kind === 'invoice' ? `Invoice ${r.ref_id}` : `Rent, lease ${r.ref_id}`} · {r.reason}
            </p>
            <p className="cheque-by">
              Prepared by <i style={{ background: by?.color }} /> {by?.title ?? r.requested_by} on {r.requested_on}
            </p>
            <div className="cheque-actions">
              <button className="btn approve" disabled={!approver.trim() || busyId !== null || locked} onClick={() => onApprove(r)}>
                {busyId === r.id ? 'Paying…' : 'Approve & pay'}
              </button>
              <button className="btn ghost" disabled={!approver.trim() || busyId !== null || locked} onClick={() => onReject(r)}>
                Reject
              </button>
            </div>
            {locked && <p className="hint">The team is mid-run. Sign once they finish.</p>}
          </article>
        )
      })}

      {decided.length > 0 && (
        <ul className="decided">
          {decided.map((r) => (
            <li key={r.id} className={`d-${r.status}`}>
              #{r.id} {r.payee} {money(r.amount)}: <b>{r.status}</b>
              {r.decided_by ? ` by ${r.decided_by}` : ''}
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
