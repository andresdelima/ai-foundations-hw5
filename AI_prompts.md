# AI Prompts Log

This file logs what I typed during vibe coding for HW5. The running app, the database writes, and the screenshots are the evidence.

## Setup: Project Context

### Prompt Typed

> Hi! Today we are working on HW5

> Some context...
> We are buidling a multi-agent operations for Campus Customs (Yale merch store we have based our previous assignment on)
>
> The goal is to build and multi-agent operations; the agentic team that runs the shop. Open tickets land on a board; customer orders, rent, unpaid bills, discount requests, whatever the shop has to handle. We are buidling 3 pieces that talk to each other:
> -MCP server
> -FastAPI backend + multi-agent team
> -React dashboard (so human can monitor and approve requests)
>
> Agent team should have full connectivity: any agent may delegate tasks to any other agent for help. Figures for agents include:
> -Boss: reads each ticket, decides who should work on it and makes final calls
> -Inventory: checks stock by SKU and size, spots shortfalls and fiugres our which vendor can restock
> -Facilities: handles the shop space side (leases, rent etc)
> -Customer services: drafts messages for customers.
>
> Do not move forward with anything yet, this is just context information. I will give you step by step instructions on every problem that we go through.

> Some rules for the shop:
>
> -The field desk.date_today is "today" for the shop. Use this date to determine what is overdue.
> -Vendor lead times come from the vendors table.
> -A vendor will not ship new product while they still have an open unpaid invoice.
> -Human approval is required for any payments. Points will be deducted if this is not done. If payment is ,made, make sure to update relevant table.
> -If there is not enough cash, the pay tool must refuse: no negative balance.
> -Cash only goes out in this homework. We did not model revenue, so no money comes in.
> -Before a full run to resolve the tickets, make sure to reset the database to the original values.
> -Do not email customers or call real vendors. Drafts stay on the board.
>
> Use your PORTKEY_API_KEY for AI calls. For this assignment, use only gpt-6-luna through Portkey for every agent. Multi-agent chats burn tokens fast. POints will be deducted if any other model shows up in your code or runs.
>
> We will do one problem at a time.
>
> Final submission will be a public GitHub repo (follow the same file tree structure from last HW).

### Follow-Up Prompt

None needed.

## Problem 1: AI Prompts Log

### Prompt Typed

> create AI_prompts.md at the start of the assignment and keep it updated as you work. This file is the log of what you typed to your vibe coder.
>
> Each problem needs its own section. Each section must include:
> -The problem number and title
> -At least one prompt you typed, in your own words as much as possible
> -One follow-up prompt if you needed it (and one sentence on what was lacking after the first).

### Follow-Up Prompt

None needed.

## Data Hand-Off

### Prompt Typed

> OK that was P1. I just realized I did not unpack the data. Before we move forward with P2, help me do that. I just downloaded data.zip to my downloads folder on this pc. Please find it and unzip it to this HW's folder. You should have data/campus_customs.db . That file is the original shop database. Tables include desk, tickets, inventory, pricing, vendors, leases, cash_accounts, payments and inventories.
>
> Your tools will update the database as tickets get resolved. Make a copy of the database file called data/campus_customs_new.db and point your MCP server and backend at that working copy. Keep campus_customs.db untouched so you can reset when you want to restart resolving tickets.

### Follow-Up Prompt

None needed.

## Problem 2: Study the CC Database

### Prompt Typed

> P2: study the cc database
>
> Open data/campus_customs.db and look through every table and its fields. Copy the original file to data/campus_customs_new.db - later problems update that working copy.
>
> Study the 3 open tickets so you see how they link to other tables.
>
> Start output/harness.md . For each table, list the fields and one short line on why that table matters for the agents. We will keep growing this harness file in later problems.

### Follow-Up Prompt

None needed.

## Problem 3: Build the MCP Server

### Prompt Typed

> OK, move on to P3: Build the MCP server
>
> Write an MCP server in mcp_server/ using FastMCP. It will talk to data/campus_customs_new.db
>
> No need to connect or run it in this problem.
>
> Every agent in this hw uses the tools in this MCP server. More tools to be added later. For now, write 3 tools that are needed for the tickets in the database. Give me options and I will decide the 3 tools. Keep names clear, never invent any data, only use information in the database.
>
> In output/harness.md , list each of you 3 MCP tools. For every tool include: which table it reads, which ticket it helps unlock (101, 102, 103) and one sentence on why that tool is the right one for that ticket.
>
> Vague lines like "reads inventory" score low. Tie the tool to the ticket!
>
> Also add a short mcp_server/README.md file that explains what the MCP server is for, which database file it uses and the 3 tools it has.

### Follow-Up Prompt

> (Picked in the vibe coder's option menu) Ticket 101: get_vendor_status · Ticket 102: get_lease_rent · Ticket 103: check_order_fill

**What was lacking:** The first prompt asked for options instead of tools, so the vibe coder needed my choice of the three tools before it could build them.

## Problem 4: Connect the MCP Server and Smoke-Test the Tools

### Prompt Typed

> P4: Add the mcp server to vibe coder and test each tool
>
> Add the MCP server to this project, so the vibe coder can call the tools. Save the connection JSON text in .mcp json at the project root (or however your vide coder saver the local MCP server lists).
>
> When the coder is connected, test each of the 3 MCP tools. Save the evidence in output/mcp_smoke.json
>
> For every tool include:
>
> -The prompt that was given to generate the tool
> -The tool name
> -The tool output (must match values in data/campus_customs_new.db )

### Follow-Up Prompt

> Run the tests

**What was lacking:** After the first prompt the server was registered in .mcp.json, but the session had to reopen in the HW5 folder to load it before the tools could be called.

## Problem 5: Build the Agent Team and Grow the MCP Tools

### Prompt Typed

> P5: Build the agent team and grow the MCP tools
>
> Build the agentic team for CC using PydanticAI: Boss, Inventory, Accounting, Facilities and Customer Service. Include prompts, models and agent loops so they can delegate work to each other with full connectivity.
>
> Put the agent prompts in backend/prompts/ - one file per agent. Put data types in backend/models.py and the agent files  under backend/ (your layout can vary as long as the five roles are clear). Use your PORTKEY_API_KEY and only gpt-6-luna for every agent.
>
> Create detailed prompt options for the shop rules that agent needs. Give me prompt options that cover all aspects of an agent's work and scope.

### Follow-Up Prompt

> (Picked in the vibe coder's option menu, from docs/prompt_options.md) Discounts: A. Tiered band · Payment order: A. Unblock first · Delegation: A. Bounded mesh · Customer Service voice: A. Warm Yale spirit

**What was lacking:** The first prompt asked for prompt options, so the vibe coder needed my picks on the four policy choices before it could write the final prompts.

### Follow-Up Prompt 2

> Yes, tighten it

**What was lacking:** The ticket 103 customer draft told the Yale AI Club a payment was "still pending", which leaked internal accounting into a customer message, so the Customer Service prompt needed a stricter rule.


## Problem 5 (Part 2): MCP-Only Shop Access, Audit Trail, Safety

### Prompt Typed

> Part 2 for P5:
>
> If additional tools are needed for MCP server so they can workmwith open tickets, please add them. Shop facts come from the MCP server over data/campus_customs_new.db - do not invent a second shop-tools layer that bupasses MCP. Make sure this is true for the prior step too.
>
> Wire the agents so they append to output/audit_trail.json as they run: for each agent-loop step, record enough to audit later. Append to this file -  do not wipe it each run.
>
> In output/harness.md , list each agent and each MCP tool (including ones you add in this problem) along with which table the tool uses. Also add a short safety section: the guardrails a real business would want when agents touch real customers and real money, plus limits that keep token use in check.
>
> Update mcp_server/README.md so the tool list matches what you have now.

### Follow-Up Prompt

None needed.

## Problem 6: Plan the Three Tickets

### Prompt Typed

> P6: Plan the three tickets
>
> Before you wire the backend, write down what you expect the team to do on each open ticket. Build output/desk_tickets.html - a page you can double-click with one tab per ticket (101, 102, 103). Also add empty cash and reflection tabs for later problems (leave them blank for now). On each ticket tab, fill an Expected section only (leave room for an Actual section you will fill after you run the agents).
>
> Fir each tickets expected section, write in your own words:
>
> -Who the boss should call first and why
> -All the agent delegations you expect - not "boss calls everyone"
> -Which MCP tools you expect that run to use.
>
> Plans that send every specialist on every ticket score low. You will compare this plan to a what actually happens when your agents resolve the 3 tickets.

### Follow-Up Prompt

None needed.

## Problem 7: Backend Routes

### Prompt Typed

> P7: Backend routes
>
> The React frontend dashboard (next problem) needs a backend it can call. In backend/main.py , use  FastAPI and add routes that do the following:
>
> -Return the 3 tickets and whether each is open or resolved
> -Take a ticket id and run your agent team on that ticket
> -Return recent agent events - what each agent said and which tools they used. So the board can refresh.
> -Approve a payment or purchase after a human clicks approve (agents only prepare the pay; this route is what actually changes cash)
> -Return the current checking balance from cash_accounts
> -Reset the database to the original values when you want to try a fresh run.
>
> From the backend/ folder, start the server with this terminal:
>
> uvicorn main:app --reload --port 8000
>
> This turn on your backend at http://localhost:8000 so the frontend dashboard can call those routes.
>
> In output/harness.md , list each route in one line (what URL / what it does).

### Follow-Up Prompt

None needed.

## Problem 8: Agent Dashboard

### Prompt Typed

> P8: Agent dashboard
>
> Build the frontend dashboard in frontend/ with React + Vite + TypeScript. The page should call the routes you built in P7. At minimum the board should:
> -List all 3 tickets
> -Let you pick one ticket and start the agent team on it
> -Show each agent and what they are saying / doing while the ticket runs
> -Mark a ticket resolved when the run finishes
> -Show a short summary of what each agent did on that ticket
> -Let a human approve a pay or purchase when asked
> -Show the checking balance (it should drop after an approved pay)
>
> Make the dashboard look good! Add images of Yale, like Handsome Dan (the Yale bulldog) and other iconic figures of the university.
>
> Tell the front end to talk to your backend at http://localhost:8000 . On the backend, allow the Vite page origin (usually http://localhost:5173) so the browser is allowed to call those routes.
>
> Start the board with:
> npm run dev
>
> This opens the React desk in your browser so you can pick tickets and watch agents.
>
> Write output/design.md with what you chose for the dashboard look (layout, how agents read differently, how resolved tickets and cash show up) and why - including the creative choices that make it feels special and something humans could actually enjoy using.

### Follow-Up Prompt

> (Picked in the vibe coder's option menu) Photos to download from Wikimedia Commons: Original Handsome Dan (1890), Harkness Tower, Sterling Library, Woolsey statue, Old Campus courtyard, Yale Bowl

**What was lacking:** The first prompt asked for Yale images but didn't name specific files, so the vibe coder listed licensed Wikimedia Commons photos with sizes and licenses for me to choose before downloading anything.

## Problem 9: Resolve the Tickets

### Prompt Typed

> P9: Resolve the tickets
>
> Before testing the agents on a full run over the 3 tickets, reset the working database data/campus_customs_new.db again so you start clean. Note the startin checking balance. Then run all 3 tickets on the board (101, 102, 103) until each is resolved.
>
> Open output/desk_tickets.html from problem 6. On each ticket tab, fill the actual section from this run: which agents worked, what they delegated, and which tools they used. Keep your Expected section so you can compare the two.
>
> On the Cash tab of the same output/desk_tickets.html , itemize the money:
>
> -Starting checking balance (after the reset)
> -For each ticket: how cash changed when that ticket resolved, and why (which pay / purchase, dollar amount).
> -Ending checking balance - it must match cash_accounts in the working database
>
> Wrong cash math loses points even if the board shows every ticket resolved. Also save:
> -output/resolved_tickets.json - for each ticket: id, final status, short outcome, what each agent contributed, and any human approval.
> -output/resolved_board.html - a page you can double - click with a screenshot of your React board for each resolved ticket (101, 102, 103).
>
> Append real runs to output/audit_trail.json . Finish output/harness.md si ut covers tables, MCP tools, the five agents, API routes, the dashboard and safety rules.
>
> Try again

### Follow-Up Prompt

> All 3 have resolved

**What was lacking:** The agents can only prepare payments, so the vibe coder had to stop after the first runs of 101 and 102 until I approved requests #1 and #2 on the board myself (and ran 103) before it could fill in the results.


## Problem 10: Reflection

### Prompt Typed

> Problem 10: Reflection
>
> Open output/desk_ticket.html , we need to work on completing a reflection that answers the following questions:
>
> -How would you evaluate the performance of the agents on each ticket and why?
> -For each ticket, how did actual compare to the expected plan you wrote earlier?
> -What would have been simpler as one agent with tools and why?
> -Describe 3 new problems CC might face that this agent team could not solve with the tools you built, and explain the tools and agents you would need to solve them.
>
> I am going to start giving you some of my thoughts. What I want you to do is to help me complement these and with all that information create a nice draft that goes into the output/desk_ticket.html .  Do not add anything that you don't run by me as this is supposed to be my own reflection. Lets work question by question

### Follow-Up Prompt

> For the 102 ticket, was the follow up a result of an error from our agent or actually something that the agent picked up: ie. the lease renewal was off after the first one was paid?

> I think there is a lot of redundancy. I don't understand entirely why so much redudancy (back and forth between agents) is necessary for tasks that are fairly simple. My guess is that this makes the whole process safer but at the same time it makes it way more inefficient and expensive. Is that correct?

> For Q4, definetely a tool that allows purchasing on credit (as most companies do from their suppliers). Being able to generate a document that promises paying in the future (ie. 90days) according to pre-arranged crontract terms. This would require human approval prior to final execution. However, having this would prevent the problem from ticket 103 from becoming recurrent.
>
> I had also thought about being able to take back returns from customers who are not satisfied with their product, understand why and either try to replace the item or refund the money after they return the item.

> I think the finance planner should be a priority. Incorporating an agent that integrates financial obligations ahead of time creates a safety mechanism to prevent missing any of these (including taxes and expenses) while making the process more efficient by preventing each agent from having to keep invidivual track of this.

**What was lacking:** The reflection had to be my own, so each answer needed my views (accuracy and guardrails for Q1, redundancy vs. safety for Q3, credit purchasing, returns and a finance planner for Q4) and a check on whether the 102 follow-up was an agent error before anything went into the page.

### Follow-Up Prompt 2

> We also need 3 problems that CC faced with the current agent team that could have been solved with the existing tools...
>
> I'm thinking the issue with the confusion on the date that the rent was due

> yeah, I like the idea of ticket being re-read 7 times. very inefficient and expensive.

> I also like the option about inventory talking to accounting... too much back and forth

**What was lacking:** The first four questions only covered problems that needed new tools, so the reflection also needed the problems the team hit that the existing tools could already have solved.


### Follow-Up Prompt 3

> ok finally tie every answer to this app and the three tickets you ran - use the ticket tabs and Cash tab on the same page as your evidence. Generic AI essays without Campus Customs details will score low. So please, make adjustments to include details about CC.

> If you need additional information to make it more specific, ask me and I can provide more details

**What was lacking:** The answers used some Campus Customs facts but didn't point to the ticket tabs and Cash tab as evidence, so each answer needed explicit links and concrete CC details (customers, vendors, SKUs, dollar amounts, cash before and after).

> I like these details, go ahead and add them

> (Picked in the vibe coder's option menu) Approvals: unblock first felt right · Return policy: 30 days, unworn with tags · Credit terms: net-30


## Publishing: Public GitHub Repo

### Prompt Typed

> Push your code to a public GitHub repository so graders can clone it. I will submit the repo URL to canvas. Also put it in output/github_url.txt
>
> Do not push your real .env to the GitHub repo. Do include both database files under data/ (the original and the working copy) so graders can run your app easily.
>
> Expected file layout will be attached in an image to follow:

### Follow-Up Prompt

> (Attached the expected file layout image: hw5/ with AI_prompts.md, requirements.txt, .env.example, .gitignore, .mcp.json, README.md, data/, mcp_server/, frontend/, backend/ and output/)

**What was lacking:** The first prompt said the file layout would follow in an image, so the vibe coder waited for it before creating the repo, to make sure the files matched.
