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
