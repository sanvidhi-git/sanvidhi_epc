# Sanvidhi EPC - demo data, step by step

`sanvidhi_epc/demo/demo_data.py` loads a complete, realistic data set for the MD demo of Srushti Infra & Agro:
one EPC road contract taken from BOQ to client invoice, a site store, three subcontractors, a week of daily
reports, and a plotted layout with plots open, booked, sold and handed over. Dates are relative to the day you
load it (the last ~10 months), so the demo always looks current.

All parties, amounts and references are fictional sample data. **Use a demo site only** - the script posts stock,
invoices, journal entries and payments.

---

## 0. Prepare a demo site (once, ~10 minutes)

```bash
cd ~/frappe-bench
bench new-site demo.local --admin-password admin --install-app erpnext
bench --site demo.local install-app sanvidhi_epc
```

Open `http://demo.local:8000`, log in as Administrator and finish the **setup wizard**:

| Field | Value |
| --- | --- |
| Country / currency / time zone | India / INR / Asia/Kolkata |
| Company | Srushti Infra and Agro (abbr. SIA) |
| Chart of accounts | Standard |
| Financial year | 01-04-2026 to 31-03-2027 (step 1 adds the previous year itself) |

## 1. Load everything

```bash
bench --site demo.local execute sanvidhi_epc.demo.demo_data.run
```

Expected output (about 1-2 minutes):

```
  done   1. Items, UOM, warehouse, accounts and Sanvidhi EPC Settings.
  ...
  done  13. W7: P-07's road milestone demanded with the unpaid agreement instalment and late interest; ...
Demo users: md@ / pm@ / site@ / billing@ / accounts@ / sales@srushti.demo  password: Demo@2026!
```

Other commands:

| Purpose | Command |
| --- | --- |
| Which steps are done | `bench --site demo.local execute sanvidhi_epc.demo.demo_data.status` |
| Run / re-run one step | `bench --site demo.local execute sanvidhi_epc.demo.demo_data.run --kwargs "{'step': 10}"` |
| Run again after a failure | the same `run` command - finished steps are skipped, each step commits on its own |

Each step checks for its own records before creating them, so re-running a step does not duplicate data.
If a step fails, it is rolled back and the error is printed; fix the cause and run again.

---

## 2. What each step creates

### Step 1 - Masters and settings
- Previous fiscal year (2025-26) if missing, so back-dated bookings can post; holiday list **Srushti Sundays**
  as the company default (ERPNext needs one to schedule tasks from a project template).
- UOM **Bag**; service items **EPC Contract Service**, **EPC Client Billing**, **EPC Plot Sale**, **Machinery Hire**; stock items
  **Cement OPC 53** (₹380/bag), **TMT Steel Fe500** (₹62/kg), **Aggregate 40mm** (₹1,450/m³).
- Warehouse **Khopoli Site Store**.
- Accounts **Retention Payable**, **Contractor Advances**, **Retention Receivable**.
- **Sanvidhi EPC Settings**: retention 5%, TDS 2%, advance recovery 10%, client retention 5%, max plot discount
  2%, demand letters 7 days ahead, late interest 12% p.a., digest on to md@srushti.demo, demand-letter email off;
  planning: tasks from BOQ on, project template **EPC Site**, labour timesheets from DPRs on (8 h per head).

### Step 2 - Demo users (password `Demo@2026!`)

| User | Role in the demo | Roles |
| --- | --- | --- |
| md@srushti.demo | Managing Director | EPC MD + ERPNext managers |
| pm@srushti.demo | Project Manager | EPC Project Manager, Projects / Purchase / Stock User |
| site@srushti.demo | Site Engineer | EPC Site Engineer, Projects / Stock / Purchase User |
| billing@srushti.demo | Billing Engineer | EPC Billing Engineer, Projects / Sales User |
| accounts@srushti.demo | Accounts | EPC Accounts User, Accounts / Purchase / Sales User |
| sales@srushti.demo | Plot sales | Plot Sales User, Sales User |

### Step 3 - Parties and projects
- Client **Sahyadri Industrial Park Pvt Ltd**; 10 plot buyers (Anil Deshmukh, Sunita Patil, ...).
- Contractors **Shree Ganesh Earthmovers**, **Sai Road Builders**, **Konkan Masonry Works**; suppliers
  **Om Cement Traders**, **Raigad Steel Suppliers**, **Konkan Equipment Hire**; broker **Pali Land Consultants**.
- Projects **Khopoli Internal Roads** (EPC site), **Sun Valley Farm Layout**, **Mountain Heights Layout**.

### Step 4 - BOQ (Workflow 1)

| Ref | Item | Qty | Rate | Amount | Budget cost rate |
| --- | --- | --- | --- | --- | --- |
| 1.1 | Earthwork excavation | 1,200 m³ | 180 | 2,16,000 | 140 |
| 1.2 | PCC M10 | 85 m³ | 5,200 | 4,42,000 | 4,300 |
| 2.1 | WBM road, two layers | 3,400 m² | 420 | 14,28,000 | 330 |
| 2.2 | Stormwater drain | 650 m | 1,450 | 9,42,500 | 1,150 |
| 3.1 | Compound wall | 900 m | 2,800 | 25,20,000 | 2,250 |
| | **Total** | | | **55,48,500** | budget 44,28,000 (20% margin) |

Submitted. The budget is written to the project's estimated cost, and the project gets its plan in ERPNext:

- the **EPC Site** template's stages - Mobilisation and site setup → **Execution** (group) → Quality checks and snag
  list → Handover to client, with dependencies;
- one **Task per BOQ line** under Execution (e.g. "2.1 Internal road, WBM in two layers"), weighted by its share of
  the contract value. Task progress comes from client measurement, so the project's % complete is by value.

### Step 5 - Contractor work orders (Workflow 2)

Labour-and-machinery contracts: the company buys cement, steel and aggregate and issues them free, so PCC, drain
and wall rates are below the budget cost rate (the material cost comes through the site store).

| Contractor | BOQ lines @ rate | Value | Advance | Dates (→ task schedule) |
| --- | --- | --- | --- | --- |
| Shree Ganesh Earthmovers | 1.1 @ 140, 1.2 @ 1,700 | 3,12,500 | - | 62 days ago → 25 days ago |
| Sai Road Builders | 2.1 @ 330, 2.2 @ 750 | 16,09,500 | 3,00,000, recovered 10% per bill | 50 days ago → in 40 days |
| Konkan Masonry Works | 3.1 @ 1,650 | 14,85,000 | 1,00,000, recovered 10% per bill | 20 days ago → in 100 days |

The work order dates become the BOQ tasks' start and end dates (the Gantt). **Mobilisation** is marked completed.

### Step 6 - Site stores
- Two material requests → purchase orders (Om Cement Traders, Raigad Steel Suppliers) → purchase receipts into
  Khopoli Site Store.
- Three material issues booked to the project (cement, aggregate, steel). Stock left: 180 bags cement,
  30 m³ aggregate, 1,400 kg steel.
- **One draft material request for 300 bags of cement**, raised yesterday, for the MD or PM to approve live.
- A purchase invoice from Konkan Equipment Hire for 60 hours of roller hire (₹48,000) booked to the project:
  a direct cost that is neither stock nor subcontract.

### Step 7 - Contractor measurement books (Workflow 3)
Four MBs: earthwork in full (45 days ago); roads and drains in two lots (35 and 12 days ago); 30 m of compound
wall (8 days ago, measured but not yet billed).

### Step 8 - Contractor RA bills (Workflow 4)

| Bill | Contractor | This bill | Retention | Advance rec. | TDS | Net payable | State |
| --- | --- | --- | --- | --- | --- | --- | --- |
| CRA-1 | Shree Ganesh | 3,12,500 | 15,625 | - | 6,250 | 2,90,625 | Purchase invoice + JE submitted |
| CRA-2 | Sai Road | 8,19,000 | 40,950 | 81,900 | 16,380 | 6,79,770 | Purchase invoice + JE submitted |
| CRA-3 | Sai Road | 7,90,500 | 39,525 | 79,050 | 15,810 | 6,56,115 | Submitted - **click Make Purchase Invoice in the demo** |

### Step 9 - Client billing and certification (Workflows 5-6)
- Client MBs for the same work.
- **Client RA Bill 1**: ₹18,49,000 submitted; the client certified ₹18,11,200 (₹37,800 held: "WBM on Road B
  chainage 200-290 to be re-rolled"); sales invoice raised for the certified value.
- **Client RA Bill 2**: ₹12,63,500, **awaiting certification**. Record the certification live, then make the invoice.
- Billed to date ≈ ₹31.1 lakh of the ₹55.5 lakh contract.
- Task progress follows: 1.1, 1.2, 2.1 and 2.2 **Completed**, 3.1 compound wall **Working** at 3.3%; the project
  and BOQ show **56.1% complete** (by value).

### Step 10 - Daily progress reports and digest (Workflow 8)
A DPR for each of the last 8 days at Khopoli (WBM layer 2 on Road C, masonry, labour by contractor, roller hours
and diesel). Two days are rain days with work stopped. Each DPR submits a **labour Timesheet** on the project:
contractor crews (masons, helpers, operators) are recorded as hours with no cost, because they are paid through RA
bills; own staff (1 supervisor, 4 helpers) carry cost at the Activity Type rates - ₹3,520 a full day, ₹23,680 for
the 8 days. Daily Digests for yesterday and today show Khopoli reported, with its progress and margin line, and
the two layouts missing.

**Progress and margin to date** on the BOQ after this step:

| | ₹ |
| --- | --- |
| Value of work done (client-measured qty × BOQ rate) | 31,12,500 |
| Subcontract (contractor RA bills) | 19,22,000 |
| Material issued from the site store | 4,51,300 |
| Own labour (timesheets) | 23,680 |
| Other direct cost (roller hire) | 48,000 |
| **Actual cost** | **24,44,980** |
| **Margin on work done** | **6,67,520 (21.4%)** |
| Budgeted cost of work done / cost variance | 24,70,500 / +25,520 (under budget) |

### Step 11 - Plot master
Sun Valley Farm Layout: **P-01 ... P-18** (3,200-8,000 sq ft at ₹480/sq ft; P-18 is a 21,800 sq ft
agricultural plot at ₹140). Mountain Heights: **MH-01 ... MH-06**.

### Step 12 - Bookings, receipts, possession (Workflows 6-7)
Each booking has the schedule Booking 10% → Agreement 20% (+30 days) → Road and drainage 30% (+120 days) →
Registration 40% (+240 days), with a sales order carrying the schedule.

| Plots | Situation |
| --- | --- |
| P-01, 02, 04, 08, 11, 14, 16 | **Sold**: paid in full in two receipts, registered at Khalapur, possession letter issued |
| P-03 | Booked, booking and agreement paid; road instalment due in ~5 days |
| P-07 | Booked, only the booking amount paid; agreement instalment overdue |
| P-12 | Booked last week at **5% discount** (above the 2% limit) - approved by md@srushti.demo |
| P-18 | **Blocked** (held back by the partners) |
| others | Available |

### Step 13 - Demand letters (Workflow 7)
- P-07: agreement letter issued on time (unpaid), and **today's letter for the road milestone**: ₹7,20,000 + ₹4,80,000
  previous dues + ₹20,515 interest at 12% = **₹12,20,515**. Print it (*Demand Letter* format).
- The daily job then **drafts** the upcoming P-03 letter for the accounts team to check and issue.

---

## 3. Using it in the MD demo

| Demo moment | Log in as | Open |
| --- | --- | --- |
| Workspace and icons, number cards | md@ | Sanvidhi EPC workspace (now incl. Overdue Tasks, Margin on Work Done) |
| Budget vs contract, margin to date | md@ | BOQ-…-00001: headline shows planned margin and margin on work done; "Progress and Margin to Date" section |
| Plan and schedule | md@ or pm@ | BOQ → View → Gantt (switch to Week or Month and scroll to Aug); Tasks; Project (56.1%, template EPC Site) |
| Site labour | pm@ | Timesheet list - one per DPR; own vs contractor labour |
| Approve a site request | md@ or pm@ | Material Request (Draft, 300 bags cement) |
| Pay a contractor | accounts@ | Contractor RA Bill CRA-3 → Make Purchase Invoice; print *Contractor RA Bill* |
| Short certification | billing@ | Client RA Bill 1 → Certification; then RA bill 2 → new Certification |
| Site view | site@ | Daily Progress Report → new (today's is done; try a second one to show the one-per-day rule) |
| Evening summary | md@ | Daily Digest for today |
| Plot availability | sales@ | Plot list, filter by layout/status |
| Discount control | sales@ | New booking for P-05 with 5% discount → blocked; MD submits it |
| Collections | accounts@ | Demand Letter for P-07 (print), draft for P-03 |
| Possession | sales@ | Plot Handover for P-01, print *Possession Letter*; try one for P-07 → blocked on dues |

## 4. Starting over

```bash
bench drop-site demo.local --force
```

then repeat sections 0 and 1. There is no partial "undo": submitted accounting documents are meant to be cancelled
in order, so a fresh site is the clean way to reset the demo.
