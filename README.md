# Sanvidhi EPC (`sanvidhi_epc`)

Frappe / ERPNext v16 app by **Sanvidhi Tech Pvt. Ltd.** for EPC contractors and plotted-land developers:
BOQ and budgets, contractor work orders, measurement, contractor and client RA billing, client certification,
daily site reporting, and plot sales from booking to possession. Everything lives in one workspace,
**Sanvidhi EPC**, with an icon on the app, the workspace, every document type and every shortcut.

| # | Workflow | Documents (icon) |
|---|----------|------------------|
| 1 | Tender to project budget | **BOQ** (`clipboard-list`): BOQ lines with sell rate and budgeted cost rate; on submit the budgeted cost becomes the project's estimated cost; revisions by amendment |
| 2 | Award work | **Contractor Work Order** (`hard-hat`): BOQ lines awarded at contractor rates, retention %, TDS %, mobilisation advance and recovery % |
| 3 | Measure | **Measurement Book** (`ruler`): contractor or client measurement, Nos × L × B × D, photos; quantity cannot pass the work order (or BOQ) without an approved variation (EPC Project Manager / EPC MD) |
| 4 | Pay the contractor | **Contractor RA Bill** (`receipt-text`): previous / this bill / up to date from the measurement books; retention, advance recovery (capped at the advance outstanding), TDS; → draft Purchase Invoice and a retention / advance Journal Entry; print *Contractor RA Bill* |
| 5 | Bill the client | **Client RA Bill** (`receipt`): progress bill against the BOQ, billed quantity never above the BOQ quantity, retention; → draft Sales Invoice (GST / e-Invoice from the taxes template and India Compliance) |
| 6 | Certification | **Certification** (`badge-check`): what the client's engineer certified vs submitted, reason required for any difference; the invoice is raised for the certified value |
| 7 | Plot inventory | **Plot** (`land-plot`): layout, plot no., area, rate, facing, 7/12; status Available / Booked / Sold / Blocked |
| 8 | Booking | **Plot Booking** (`map-pin`): price, discount (above the limit only the EPC MD can submit), payment schedule that must add up to the agreed value, broker commission; → draft Sales Order with the schedule |
| 9 | Collections | **Demand Letter** (`mail`): instalment + previous dues + interest on late payment; drafted daily ahead of each due date, emailed on submit; print *Demand Letter*. Receipts against the sales order refresh the booking's dues automatically |
| 10 | Possession | **Plot Handover** (`key-round`): no-dues check, document checklist, registration details; plot becomes Sold; print *Possession Letter* |
| 11 | Site reporting | **Daily Progress Report** (`notebook-pen`): work done, labour, machinery, hindrances, photos; one per project per day; optional rule blocking material requests until yesterday's DPR is in |
| 12 | Evening summary | **Daily Digest** (`newspaper`): every open project's DPR (or "missing"), % complete and margin, emailed at 7 pm |
| 13 | Plan and track (standard ERPNext) | **Project / Task / Gantt / Timesheet**: BOQ submit applies the *EPC Site* project template (stages) and makes a Task per BOQ line; work order dates schedule the tasks; client measurement sets task progress and the project's % complete (by value); each DPR submits a labour Timesheet (hours for all crews, cost for own labour only); the BOQ shows **value of work done vs actual cost** (subcontract + material issued + own labour + other direct cost) and the margin on work done |

Settings: **Sanvidhi EPC Settings** (`settings`) - default retention / TDS / advance recovery, service and
billing items, retention and advance accounts, plot discount limit, demand-letter lead days, digest recipients.

Roles: EPC MD, EPC Project Manager, EPC Site Engineer, EPC Billing Engineer, EPC Accounts User, Plot Sales User.
The EPC roles also get access to Project, Task, Timesheet, Project Template and Activity Type, so the team does not
need ERPNext's "Projects User" role as well.

Planning needs a **default holiday list on the company** to create the template's stages (ERPNext schedules template
tasks around holidays); without one, only the BOQ line tasks are created and a message says why.

## Install

```bash
bench get-app https://github.com/sanvidhi-git/sanvidhi-epc
bench --site <site> install-app sanvidhi_epc
```

Then open **Sanvidhi EPC Settings**, choose the company, the three non-stock items (contractor service, client
billing, plot sale) and the retention / advance accounts.

## Test

```bash
bench --site <test-site> execute sanvidhi_epc.tests.scenario_workflows.run
```

Runs every workflow end to end with its own tagged data, including the negative cases (quantity above order,
discount above limit, handover with dues). Use a test site: it posts invoices and journal entries.

## Demo data

```bash
bench --site <demo-site> execute sanvidhi_epc.demo.demo_data.run
```

Loads the Srushti Infra & Agro demo in 13 steps (BOQ to client invoice, site stores, DPRs, plots sold and booked,
demand letters) with a demo user per role. See [docs/DEMO_DATA.md](docs/DEMO_DATA.md).

## Layout

Follows the `vsgil_sugar` structure: `sanvidhi_epc/<module>/` with `doctype/`, `number_card/`,
`print_format/`, `workspace/` (and `sidebar/` for Frappe 16.52+); app-level `desktop_icon/`,
`workspace_sidebar/`, `public/icons/desktop_icons/{solid,subtle}/`, `public/images/`, `setup/`, `tasks/`,
`utils/`, `patches/` and `tests/`. One module, **Sanvidhi EPC**, so there is exactly one workspace and sidebar.
