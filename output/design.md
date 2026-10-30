# Campus Customs Ops Desk: dashboard design

React + Vite + TypeScript in `frontend/`. It talks to the FastAPI backend at `http://localhost:8000`, and the backend's CORS allows `http://localhost:5173`. Start it with `npm run dev`.

## The idea: a Yale front office, not a server log

The people approving payments here aren't engineers watching logs. They're whoever runs the shop that day. So the board reads like a well-run front office on Chapel Street:
- a ticket board
- a room where the team works
- a chequebook that needs a signature
- a ledger that shows the money leaving

Everything is in Yale blue (`#00356b`), with serif headings that feel like a college letterhead. The motto under the header sums up the one rule that matters most: *Lux et Veritas · and every payment signed by a person.*

## Layout (three columns, left to right = the order you work in)

| Column | What's there | Why |
|---|---|---|
| **Left: Ticket Board + Checking** | The 3 tickets as index cards (ruled-paper background, colored edge by status), each with a **Send in the team** button. Below them, the checking balance. | You start by picking work. Cash sits under the tickets because every money decision is about a ticket. |
| **Middle: Team Room, then What each agent did, then Drafts** | The five agents live, then a per-agent summary of the ticket, then the letters they drafted. | This is the show. It's the widest column, so you can follow who's talking to whom. |
| **Right: Needs your signature + Play-by-play** | Payment requests waiting for a person, then the step-by-step feed from the audit trail. | Your job (signing) stays in view while the agents work. The feed is the receipt. |

The header holds the shop date, the model (`gpt-6-luna`), three stats (checking, open tickets, payments to sign) and **Reset shop**. The "to sign" stat pulses gold when something is waiting. On narrow screens the columns stack.

## How agents read differently

Each agent "works out of" a Yale landmark, which gives it a face, a color and a personality you remember after one run:

| Agent | Avatar (Wikimedia Commons) | Color | Why that landmark |
|---|---|---|---|
| **Boss** | Handsome Dan, the original Yale bulldog (1890) | Yale blue | The mascot is in charge. Its card spans the full width at the top of the Team Room. |
| **Inventory** | Sterling Memorial Library | Green | The library knows every shelf, and Inventory knows every SKU and size. |
| **Accounting** | Harkness Tower | Gold | The clock tower keeps time, and Accounting keeps the books. Gold matches the cheques. |
| **Facilities** | Old Campus courtyard | Purple | The grounds. Facilities looks after the shop space and the lease. |
| **Customer Service** | Woolsey statue (the toe students rub for luck) | Orange | The friendly face everyone greets. Its drafts are what customers see. |

**While a ticket runs**, each card shows:
- **Status:** waiting, thinking, using a tool, delegating, reported back, or made the call.
- **Speech bubble:** what the agent is saying right now, for example "Asks Accounting: please request payment for invoice 501…", or its report back.
- **Tool chips:** each MCP tool the agent used, with ×counts.

The agent that's currently active lifts up and glows in its own color, and its photo gets a pulse ring. Idle agents fade to grey, so on ticket 102 you can *see* that Inventory and Customer Service never got called.

**Relay chips** at the top of the room (Boss → Inventory, Inventory → Accounting) show each delegation that's still open. They disappear when the report comes back, which makes the full connectivity between agents visible.

**In the play-by-play**, each step has a left border in the agent's color and an icon by type: 💭 think, 🔧 tool, ➡️ delegate, ↩️ report, ⚖️ decision, ✍️ human approval. Human actions show as **You**.

## Resolved tickets

- **Status pills:**
  - Open: blue.
  - Team at work: pulsing blue.
  - **Needs your signature:** gold.
  - Blocked: red.
  - **Resolved:** green.
- **The stamp:** when a ticket becomes resolved, a green rubber stamp, **RESOLVED**, slams onto its index card at an angle. A Handsome Dan toast says "Boola boola! Ticket #101 is resolved", and blue-and-white confetti with little "Y"s falls once. The button changes to **Done**.
- **How a ticket gets to resolved:** the Boss marks a ticket resolved only when nothing is waiting on a person, meaning the payments it needed are paid and its drafts are saved.
  - The first run usually ends at *Needs your signature*.
  - After you approve the ticket's last pending payment, the board automatically **sends the team back** to finish. For example, Inventory drafts the tee restock now that the vendor can ship, and the Boss resolves the ticket.
  - A checkbox lets you turn that automatic follow-up off.
- **"What each agent did on #N":** this summary covers every run on the ticket since the last reset (first run plus follow-ups). It shows:
  - the Boss's call, with its status
  - for each agent, who asked it, who it asked, what it said, its tools with counts, and steps and tokens

## Cash

- **The balance:** shown big in serif type. When a payment is approved, the number **counts down** to the new balance over about a second, and a red "−$840.00" drops away beside it. You *feel* the money leave.
- **Committed bar:** a striped gold bar shows how much of the balance is already promised to pending requests, next to what's free after that. For example, $2,400 is promised to the rent and $160 is free. This is the same "cash minus pending requests" rule the agents follow, made visible.
- **Payments list:** each payment made, with its amount in red and *who approved it*.
- **The rule, in italics:** "Cash only goes out in this shop, and it never goes below $0."

## Approvals ("Needs your signature")

- **Each request is a cheque:** request number, ticket, "Pay to Elm City Properties", a big amount, a memo (invoice or lease, plus the agent's reason) and "Prepared by Accounting".
- **Signing as:** you type your name once, and it's remembered. **Approve & pay** and **Reject** stay disabled until there's a name, because the backend stores it as `approved_by`.
- **Locked mid-run:** approvals are locked while the team is working, so cash can't change under the agents.
- **Refusals stay visible:** if the backend refuses (for example, cash would go negative), the reason shows as a red toast and nothing moves.

## Drafts

Customer messages look like letters on cream paper, and restock orders like forms on pale blue. Every one is marked **Draft · not sent**, because nothing leaves the shop without a person.

## Small things that make it pleasant

- **Polling speed:** live polling every 0.9 s during a run, and every 4–5 s when idle. That's quick enough to feel alive without hammering the backend.
- **Offline screen:** if the backend is down, a friendly page shows Handsome Dan and the exact `uvicorn` command to start it.
- **Reduced motion:** animations switch off for people who set "reduce motion" in their system settings.
- **Photo credits:** a strip of thumbnails in the footer, each linking to its Commons page with author and license (from `public/yale/credits.json`).

## Photos

There are six photos from Wikimedia Commons, all downloaded at 960 px or smaller:
- Handsome Dan 1890 (public domain)
- Harkness Tower (public domain, Carol M. Highsmith)
- Sterling Memorial Library (CC BY-SA 4.0, Christian David)
- Woolsey statue (CC BY 2.0, Pascal Walschots)
- Old Campus courtyard (CC0, DimiTalen)
- Yale Bowl (CC BY 4.0, Kenneth C. Zirkel)

Campus Customs is a class project, not an official Yale site.
