# Sanvidhi EPC (`sanvidhi_epc`) - design notes

## 1. One app, one module, one workspace

Every document type sits in the single module **Sanvidhi EPC**, so the app has exactly one workspace and
one sidebar. Frappe v16.52+ resolves a form's sidebar from its module: with one module, the curated
Sanvidhi EPC sidebar (with an icon on every item) stays on screen from the workspace to any form.

| Area | Documents |
| --- | --- |
| Estimate & award | BOQ, Contractor Work Order |
| Measure & bill | Measurement Book, Contractor RA Bill, Client RA Bill, Certification |
| Site reporting | Daily Progress Report, Daily Digest |
| Plot sales | Plot, Plot Booking, Demand Letter, Plot Handover |
| Setup | Sanvidhi EPC Settings |

The user sees one desktop tile (App icon, `desktop_icon/sanvidhi_epc.json`), one sidebar and one workspace.
The sidebar ships in both formats: `workspace_sidebar/sanvidhi_epc.json` (Frappe v16 before 16.52, the
`vsgil_sugar` layout) and `sanvidhi_epc/sidebar/sanvidhi_epc/` (16.52+, made with `bench convert-sidebar-fixtures`).
The workspace opens with an icon grid of every app (`setup/module_tiles.py`, rebuilt on each migrate), each
app drawn from its own solid desktop icon in `public/icons/desktop_icons/solid/`. Every DocType carries a Lucide `icon`; the same
icon is used on its sidebar item and workspace link, and its SVG on the app tile, so a document is recognisable everywhere.

| Document | Icon |
| --- | --- |
| Workspace / sidebar header / app | `construction` (+ SVG logo, solid and subtle desktop icons) |
| BOQ | `clipboard-list` |
| Contractor Work Order | `hard-hat` |
| Measurement Book | `ruler` |
| Contractor RA Bill | `receipt-text` |
| Client RA Bill | `receipt` |
| Certification | `badge-check` |
| Plot | `land-plot` |
| Plot Booking | `map-pin` |
| Demand Letter | `mail` |
| Plot Handover | `key-round` |
| Daily Progress Report | `notebook-pen` |
| Daily Digest | `newspaper` |
| Sanvidhi EPC Settings | `settings` |

## 2. Standard ERPNext underneath

- Project is the site; BOQ budgeted cost is written to `Project.estimated_costing`.
- Contractors are Suppliers, clients and plot buyers are Customers, leads are Leads.
- Money moves only through standard documents made in draft from the custom ones: Purchase Invoice and
  Journal Entry (contractor RA bill), Sales Invoice (client RA bill), Sales Order with payment schedule
  (plot booking), Payment Entry (receipts). TDS and GST stay with ERPNext / India Compliance.

## 3. Roll-ups are recomputed, never incremented

`utils/progress.py` recomputes awarded, measured and billed quantities on the BOQ and work order from the
submitted documents after every submit and cancel, so amendments cannot drift the totals.
`utils/collections.py` recomputes a booking's receipts from Payment Entries against its Sales Order (and
invoices made from it), and spreads them over the instalments first-due-first-paid.

## 4. Controls

| Control | Where |
| --- | --- |
| One active BOQ per project; revise by amendment | `BOQ.before_submit` |
| Measured to date ≤ work order / BOQ quantity unless a variation is approved by EPC Project Manager / MD | `MeasurementBook.validate_limits` |
| A measurement is billed once | `billing_status` on Measurement Book, set by the RA bill |
| Advance recovery ≤ advance outstanding | `ContractorRABill.calculate` |
| RA bills cancelled newest first | `before_cancel` on both RA bills |
| Certified ≠ submitted needs a reason | `Certification.validate` |
| A plot is booked once; Booked / Sold only through documents | `PlotBooking.validate_plot`, `Plot.validate` |
| Discount above the limit needs EPC MD | `PlotBooking.before_submit` |
| Possession only with nil dues and mandatory documents | `PlotHandover.before_submit` |
| One DPR per project per day; optional block on material requests | `DailyProgressReport.validate`, `utils/site.py` |

## 5. Project management: standard ERPNext, driven by the EPC documents

`utils/planning.py` keeps ERPNext's Project, Task, Timesheet and Gantt in step with the EPC documents, rather
than replacing them.

| Event | Effect |
| --- | --- |
| BOQ submit | Project template from Settings (*EPC Site*: Mobilisation → Execution → Quality checks → Handover, with dependencies) if the project has no tasks; one Task per BOQ line under *Execution* (`Task.boq`, `Task.boq_ref`), weight = share of BOQ value; a BOQ revision updates the same tasks by BOQ ref and cancels dropped lines |
| Work order submit / cancel | Task start / end = earliest start and latest end of the work orders on that line (clamped to the project's dates); the Execution group is widened to span its tasks |
| Client measurement submit / cancel | Task progress = client-measured qty ÷ BOQ qty; status Open / Working / Completed; actual start / end from the measurement dates; Execution group progress = value-weighted average |
| DPR submit / cancel | A submitted Timesheet on the project (`Timesheet.daily_progress_report`): one row per crew, one shift, costed at the Activity Type rate × headcount for own labour, *Contractor Labour* (₹0) for supplier crews; cancelled with the DPR |
| Stock Entry, Timesheet, Purchase Invoice submit / cancel; contractor and client RA bills; daily job | BOQ "Progress and Margin to Date" recomputed |

**% complete.** The project's method is set to *Manual* and its value written from the BOQ (value of client-measured
work ÷ contract value). ERPNext's *Task Weight* method rounds each task's share to two decimals (56.5% against the
true 56.1% in the demo), so the BOQ figure is used for both.

**Margin.** ERPNext's project gross margin is billed amount minus all costs, which swings with billing timing. The BOQ
instead compares the **value of work done** (client-measured quantity × BOQ rate) with **actual cost**:

| Cost | Source |
| --- | --- |
| Subcontract | `current_value` of submitted Contractor RA Bills (accrued when certified, not when invoiced) |
| Material | Stock issues to the project (rows with a source and no target warehouse) |
| Own labour | Timesheet costing on the project |
| Other direct | Non-stock Purchase Invoice items on the project, excluding the invoices made from RA bills |

**Cost variance** = budgeted cost of work done (measured qty × BOQ cost rate) − actual cost.

**Permissions.** `grant_project_permissions` adds the EPC roles to Project, Task, Timesheet, Project Template and
Activity Type once per rule (tracked in a default), so a rule an administrator later changes is not reapplied.
