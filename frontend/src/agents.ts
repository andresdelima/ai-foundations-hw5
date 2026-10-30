import type { AgentName } from './api'

// Each agent "works out of" a Yale landmark: the photo is its avatar, the color
// is how you spot it in the play-by-play.
export interface AgentMeta {
  name: AgentName
  title: string
  role: string
  photo: string
  photoPosition: string
  landmark: string
  color: string
  tint: string
}

export const AGENTS: AgentMeta[] = [
  {
    name: 'boss',
    title: 'Boss',
    role: 'Reads every ticket, routes it, makes the final call',
    photo: '/yale/handsome-dan-1890.jpg',
    photoPosition: '50% 18%',
    landmark: 'Handsome Dan, the original Yale bulldog (1890)',
    color: '#00356b',
    tint: '#e3ecf7',
  },
  {
    name: 'inventory',
    title: 'Inventory',
    role: 'Stock by SKU and size, shortfalls, vendor restocks',
    photo: '/yale/sterling-library.jpg',
    photoPosition: '50% 45%',
    landmark: 'Sterling Memorial Library: it knows every shelf',
    color: '#2f7d5b',
    tint: '#e2f2ea',
  },
  {
    name: 'accounting',
    title: 'Accounting',
    role: 'Cash, invoices, payment requests',
    photo: '/yale/harkness-tower.jpg',
    photoPosition: '50% 30%',
    landmark: 'Harkness Tower: keeps time and keeps the books',
    color: '#b07d12',
    tint: '#f8efda',
  },
  {
    name: 'facilities',
    title: 'Facilities',
    role: 'The Chapel Street lease, rent and landlord',
    photo: '/yale/old-campus.jpg',
    photoPosition: '50% 55%',
    landmark: 'Old Campus: looks after the grounds',
    color: '#7a4b9c',
    tint: '#efe6f6',
  },
  {
    name: 'customer_service',
    title: 'Customer Service',
    role: 'Drafts every message, nothing gets sent',
    photo: '/yale/woolsey-statue.jpg',
    photoPosition: '45% 40%',
    landmark: "Woolsey's statue: the friendly face everyone greets",
    color: '#c2410c',
    tint: '#fbe9df',
  },
]

export const AGENT_BY_NAME = Object.fromEntries(AGENTS.map((a) => [a.name, a])) as Record<AgentName, AgentMeta>

export const TOOL_LABELS: Record<string, string> = {
  get_ticket: 'read ticket',
  list_open_tickets: 'scan board',
  list_tickets: 'scan board',
  get_shop_date: 'check date',
  check_order_fill: 'check stock',
  list_inventory: 'scan shelves',
  list_vendors: 'list vendors',
  get_vendor_status: 'vendor status',
  draft_restock_order: 'draft restock',
  get_cash_balance: 'check cash',
  list_open_invoices: 'open invoices',
  list_payment_requests: 'payment requests',
  list_payments: 'payments made',
  request_payment: 'request payment',
  pay_approved_request: 'pay (approved)',
  get_lease_rent: 'lease & rent',
  list_leases: 'list leases',
  check_discount_policy: 'discount rule',
  draft_customer_message: 'draft message',
  list_drafts: 'read drafts',
  update_ticket: 'update ticket',
}

export const TICKET_ICONS: Record<string, string> = {
  customer_order: '👕',
  rent_notice: '🏛️',
  price_override: '🏷️',
}

export const STATUS_LABEL: Record<string, string> = {
  open: 'Open',
  in_progress: 'Team at work',
  waiting_approval: 'Needs your signature',
  blocked: 'Blocked',
  resolved: 'Resolved',
}
