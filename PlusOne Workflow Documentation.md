# PlusOne Workflow Documentation

## Purpose

This document explains the current PlusOne integration workflow across:

- inbound invoice download and staging
- PlusOne web application review and processing
- SQL processing into Dynamics GP Payables
- outbound extract generation
- outbound file upload back to PlusOne
- supporting logs, messages, configuration, and archive behavior

The production review screen is the PlusOne web application launched from Dynamics GP.

## Scope And Assumptions

- Two sites are supported: `NZ` and `AU`.
- Each site has its own SFTP credentials, local working folders, and SQL database.
- Python handles file transfer and file staging.
- SQL Server handles staging, processing state, and GP integration procedures.
- The PlusOne web application provides a header-level browse, line-level drilldown, download/import, and selected-document processing actions.
- Paramiko is the SFTP engine used by the Python integration layer.

## High-Level Architecture

There are two main flows:

1. Inbound invoice flow
   PlusOne SFTP outbound folder -> download/import -> SQL staging header/line tables -> web review/process -> Dynamics GP PM transaction creation

2. Outbound master data / purchasing flow
   SQL extract queries -> local CSV output files -> Python upload -> PlusOne SFTP inbound folder

## Site Separation

Site-specific configuration is stored in:

- `PlusOnePython/PlusOneConfig.json`
- `PlusOnePython/PlusOneConfig.local.template.json`
- `PlusOnePython/Compiled/PlusOneConfig.json`

Each site entry defines:

- SFTP host, port, username, password, host key fingerprint
- remote download and upload folders
- local download, upload, log, and archive paths
- SQL connection string
- SQL command and bulk copy timeouts

The runtime `PlusOneConfig.json` contains live credentials and should be protected. The template is the safer reference for deployment packaging.

## Database Collation Notes

The site databases may use a binary/case-sensitive collation such as `Latin1_General_BIN`.

To avoid missed joins or false validation errors:

- inbound `SupplierID` values are normalized to uppercase during import
- batch staging uppercases `SupplierID` and `DocumentNo` when grouping and linking headers/lines
- processing uppercases the selected header supplier/document values before GP lookups
- the header view joins `PM00200` using the uppercased staged supplier ID
- line account validation compares staged `LedgerCode` to `GL00105.ACTNUMST` using an uppercased staged value

GP vendor IDs and GL account strings are expected to match the normalized uppercase form used by the integration.

## Inbound Invoice Workflow

### 1. Download And Import

The main inbound engine is implemented in:

- `PlusOnePython/plusone.py`

The compiled web application can run the same download/import workflow through:

- `POST /api/download`

Compiled helper scripts include:

- `PlusOnePython/Compiled/Run-PlusOne.ps1`
- `PlusOnePython/Compiled/Run-PlusOneWeb.ps1`

The download/import script performs these steps:

1. Load the site configuration.
2. Connect to the PlusOne SFTP endpoint using Paramiko.
3. Download matching CSV files from the configured remote outbound folder.
4. Validate the CSV structure and data types.
5. Bulk insert imported rows into `dbo.hmlPlusOneInvoiceLine`.
6. Call `dbo.hmlPlusOneStageImportedBatch` to create grouped header rows in `dbo.hmlPlusOneInvoiceHeader`.
7. Write operational messages to `dbo.hmlPlusOneMessages`.
8. Move the downloaded file into archive subfolders.

### 2. CSV Validation

Inbound CSV validation is handled inside `PlusOnePython/plusone.py`.

The script validates:

- required header columns
- required values such as `SupplierID`, `DocumentNo`, and `LedgerCode`
- date formats
- numeric values such as line amounts and quantity

If validation fails:

- the file is not staged into SQL
- a `CSVERR` message is written to `dbo.hmlPlusOneMessages`
- the file is moved to the failed archive folder

### 3. Batch Staging

Each successful import run generates one `ImportBatchID`.

All imported lines from the same source file batch are written to:

- `dbo.hmlPlusOneInvoiceLine`

The batch staging procedure then groups those lines by:

- `SupplierID`
- `DocumentNo`

and creates one row per invoice in:

- `dbo.hmlPlusOneInvoiceHeader`

This split staging model is the basis for the PlusOne web review UI.

### 4. Web UI Review

The PlusOne web application exposes the staging data like this:

- a header browse bound to `dbo.vw_hmlPlusOneInvoiceHeader`
- a line drilldown bound to `dbo.vw_hmlPlusOneInvoiceLineDetail`
- a Process Selected action that calls the web API endpoint `/api/process`
- `/api/process` calls `dbo.hmlPlusOneProcessInvoice` once for each selected `InvoiceHeaderID`
- a Cancel Selected action that calls the web API endpoint `/api/cancel`
- `/api/cancel` calls `dbo.hmlPlusOneCancelInvoice` once for each selected cancellable `InvoiceHeaderID`
- an optional process-all action that calls `dbo.hmlPlusOneCreateNonPOInvoice`
- an application lock backed by `dbo.hmlPlusOneAppLock`

The intended user workflow is:

1. Launch the PlusOne web application from GP.
2. Review header-level invoices waiting in `Ready` status.
3. Open line drilldown if the invoice has line errors or needs review.
4. Select one or more processable invoice headers.
5. Process selected documents.
6. The web app submits selected headers one at a time for best error isolation.
7. Review success or error feedback directly in the same screen.

Users can also cancel selected `Ready` or `Error` invoices. Cancelled records are retained in staging with `Status = 8`, but the `Cancelled` status filter is not selected by default. The UI prompts for confirmation before cancellation.

Error feedback is surfaced through status badges:

- header status badges show `HeaderMessage` in an in-app hover tooltip when a message exists
- line status badges show `LineMessage`, falling back to `HeaderMessage`, in an in-app hover tooltip
- detailed line messages remain available in `dbo.vw_hmlPlusOneInvoiceLineDetail`

### 5. SQL Processing Into GP

The processing flow is centered around:

- `dbo.hmlPlusOneProcessInvoice`

This procedure:

1. Locks the selected header.
2. Resets header and line processing messages for that invoice.
3. Checks for duplicate document numbers already in GP.
4. Validates the supplier exists in `PM00200`.
5. Reads vendor currency from `PM00200.CURNCYID`.
6. Reads vendor tax schedule from `PM00200.TAXSCHID` and errors if it is blank.
7. Reads company functional currency from `MC40000.FUNLCURR`.
8. Pre-validates line account codes against `GL00105.ACTNUMST`.
9. Marks every invalid line with its own `LineMessage`.
10. Writes a combined header validation summary to `HeaderMessage` and stops before GP creation if pre-validation fails.
11. Sums line amounts into a document total.
12. Creates the PM voucher number.
13. Creates the PM tax record.
14. Creates the PM transaction header.
15. Writes the PlusOne image URL into GP notes.
16. Deletes the default GP expense distribution.
17. Rebuilds distributions from the staged invoice lines.
18. Uses standard distribution logic when vendor/PM currency matches functional currency.
19. Uses multicurrency distribution logic when vendor/PM currency differs from functional currency.
20. Marks the header and lines as processed on success.
21. Marks the header and offending line as error on failure when the failing line is identifiable.
22. Writes an audit message to `dbo.hmlPlusOneMessages`.

The process-all wrapper is:

- `dbo.hmlPlusOneCreateNonPOInvoice`

This wrapper finds all header rows in `Status = 0` and processes them one by one using the single-header procedure.

The web application does not use this wrapper for selected processing. It calls `dbo.hmlPlusOneProcessInvoice` once per selected header so each document can succeed or fail independently.

### 6. SQL Cancellation

Cancellation is centered around:

- `dbo.hmlPlusOneCancelInvoice`

This procedure:

1. Locks the selected header.
2. Allows cancellation only when the header is `Ready` or `Error`.
3. Blocks cancellation for `Processing`, `Processed`, and already `Cancelled` headers.
4. Sets the header status to `8`.
5. Sets all matching line statuses to `8`.
6. Writes the cancelling user, date/time, and previous status into `HeaderMessage`.
7. Writes an audit message to `dbo.hmlPlusOneMessages`.

The web UI presents cancellation as a separate action from processing:

- `Process Selected` appears before `Cancel Selected`
- `Cancel Selected` uses a red danger-style button
- the user must confirm before `/api/cancel` is called
- cancelled records remain available through the `Cancelled` status filter

### 7. Web Review UI

The web UI uses the invoice header grid as the main review surface.

Current header-grid behavior:

- headers are sorted by source file name by default
- users can sort visible columns by clicking the column header
- the visible header grid omits site and PO number to keep the review surface compact
- the accounting date is editable for `Ready` and `Error` invoices
- the document date is displayed using the same browser date format as accounting date, but remains read-only
- invoice lines are shown inline by expanding the document number instead of using a separate line grid

Inline line detail behavior:

- clicking the expand control beside the document number loads lines on demand
- lines are retrieved from `GET /api/documents/{InvoiceHeaderID}/lines`
- line data is cached in the browser once loaded
- only visible matching invoice rows are shown after filtering and sorting
- header and line status badges continue to expose error messages through tooltips

## Outbound Extract And Upload Workflow

### 1. Extract Generation

The main extract engine is implemented in:

- `PlusOnePython/plusone.py`

Compiled helper scripts include:

- `PlusOnePython/Compiled/Run-ExtractUpload.ps1`

The extract script currently supports these data sets:

- `GLM` for GL code master
- `SUP` for supplier master
- `PUR` for purchase orders

The extract definitions are embedded in the Python extraction definitions in `PlusOnePython/plusone.py`.

For each requested extract, the script:

1. loads the site configuration
2. runs the configured SQL query
3. writes the result to CSV in the site upload folder
4. writes an extract log entry

### 2. Upload

The main upload engine is implemented in:

- `PlusOnePython/plusone.py`

Compiled helper scripts include:

- `PlusOnePython/Compiled/Run-ExtractUpload.ps1`

The upload script:

1. loads the site configuration
2. scans the local upload folder for matching files
3. uploads each file to the PlusOne inbound SFTP folder
4. writes success or failure messages to `dbo.hmlPlusOneMessages`
5. archives the uploaded file into success or failed archive folders

## SQL Objects

### `dbo.hmlPlusOneInvoiceHeader`

Purpose:
Stores one row per staged invoice for UI review and processing control.

Key columns:

- `InvoiceHeaderID`: primary key used by the web UI and processing procedure
- `ImportBatchID`: links related imported headers and lines back to one import batch
- `SupplierID`
- `DocumentNo`
- `DocumentDate`
- `AccountingValueDate`
- `ImageURL`
- `Status`
- `Processed`
- `FileName`
- `GPVoucherNumber`
- `GPBatchID`
- `HeaderMessage`

Behavior:

- created by `dbo.hmlPlusOneStageImportedBatch`
- updated during invoice processing
- used as the main UI browse source through the header view

### `dbo.hmlPlusOneInvoiceLine`

Purpose:
Stores one row per imported invoice line.

Key columns:

- `InvoiceLineID`
- `InvoiceHeaderID`
- `ImportBatchID`
- `SourceLineNo`
- `SupplierID`
- `DocumentNo`
- `LedgerCode`
- `LineValueExclGST`
- `LineValueGST`
- `LineDescription`
- `PurchaseOrderNo`
- `POLine`
- `InvoicedQty`
- `Status`
- `Processed`
- `ErrorState`
- `LineMessage`

Behavior:

- bulk loaded by `PlusOnePython/plusone.py`
- grouped into headers by `dbo.hmlPlusOneStageImportedBatch`
- read by `dbo.hmlPlusOneProcessInvoice` to build GP distributions
- shown to the user through expandable line detail rows in the header grid

### `dbo.vw_hmlPlusOneInvoiceHeader`

Purpose:
Header-only browse view for the web UI.

Provides:

- one row per staged invoice header
- totals rolled up from the line table
- line counts
- status description
- error indicators
- first error line number
- GP voucher and batch references

Recommended use:

- main scrolling window in GP

### `dbo.vw_hmlPlusOneInvoiceLineDetail`

Purpose:
Detailed line drilldown view for the web UI.

Provides:

- all staged invoice lines for a selected header
- line status and line error message
- header status and header message
- GP voucher and batch references

Recommended use:

- expandable line detail under the selected header row
- error review and line inquiry

### `dbo.hmlPlusOneStageImportedBatch`

Purpose:
Converts newly imported line rows into grouped header rows.

Responsibilities:

- validate that the batch exists
- create header rows for each unique `SupplierID + DocumentNo`
- normalize `DocumentNo`
- link line rows to the created header rows
- reset line processing state for the imported batch

### `dbo.hmlPlusOneProcessInvoice`

Purpose:
Process one selected staged invoice into Dynamics GP.

Responsibilities:

- enforce one-header-at-a-time processing
- validate duplicates, supplier setup, vendor tax schedule, vendor currency, functional currency, and line account codes
- write all pre-validation line account errors back to the matching line rows
- write a combined pre-validation summary to the header row
- create PM tax, header, notes, and distributions
- preserve error context at header and line level
- update statuses and audit trail

### `dbo.hmlPlusOneCreateNonPOInvoice`

Purpose:
Legacy-compatible batch wrapper around the new single-header process.

Responsibilities:

- select all `Ready` headers
- call `dbo.hmlPlusOneProcessInvoice` for each one

Recommended use:

- optional unattended or bulk process option
- backward compatibility where older automation expects this procedure name

### `dbo.hmlPlusOneCancelInvoice`

Purpose:
Cancel one selected staged invoice while retaining the imported header and line records for audit.

Responsibilities:

- allow cancellation of `Ready` and `Error` headers
- prevent cancellation of `Processing`, `Processed`, and already `Cancelled` headers
- set the header and all lines to `Status = 8`
- record the cancelling user, date/time, and previous status in `HeaderMessage`
- write an audit entry to `dbo.hmlPlusOneMessages`

### `dbo.hmlPlusOneMessages`

Purpose:
Simple operational message and audit table used by Python and SQL procedures.

Typical message IDs include:

- `IMPORT`
- `CSVERR`
- `SQLERR`
- `UPLOAD`
- `UPLOADERR`
- `P1PROC`
- `PLUSONE`
- `FATAL`

Recommended use:

- troubleshooting
- GP message review window
- lightweight audit history

### Legacy `dbo.hmlPlusOneInvoice`

The original single-table staging design still exists in the repository as:

- `table hmlPlusOneInvoice.sql`

It is now considered legacy. The new split staging design uses `hmlPlusOneInvoiceHeader` and `hmlPlusOneInvoiceLine` instead.

## Web Application

The production review and processing UI is implemented in:

- `PlusOnePython/plusone_web.py`
- `PlusOnePython/PlusOneWeb/index.html`
- `PlusOnePython/Compiled/PlusOneWeb.exe`

The compiled executable is built by:

- `PlusOnePython/Build-PlusOneWeb.ps1`

The compiled build is a PyInstaller one-folder build. The executable remains:

- `PlusOnePython/Compiled/PlusOneWeb.exe`

Supporting runtime files are copied under:

- `PlusOnePython/Compiled/_internal`

### Web API Endpoints

The web application exposes these main endpoints:

- `GET /api/documents?site=NZ|AU`
  Returns header browse rows from `dbo.vw_hmlPlusOneInvoiceHeader`, including `HeaderMessage`.

- `GET /api/documents/{InvoiceHeaderID}/lines?site=NZ|AU`
  Returns line detail rows from `dbo.vw_hmlPlusOneInvoiceLineDetail`, including `LineMessage` and `HeaderMessage`.

- `POST /api/download`
  Runs the download/import workflow for the selected site.

- `POST /api/process`
  Accepts selected `InvoiceHeaderID` values and calls `dbo.hmlPlusOneProcessInvoice` once per selected document.

- `POST /api/documents/{InvoiceHeaderID}/accounting-date`
  Updates `dbo.hmlPlusOneInvoiceHeader.AccountingValueDate` for `Ready` or `Error` invoices. The request requires the current application lock.

- `POST /api/cancel`
  Accepts selected cancellable `InvoiceHeaderID` values and calls `dbo.hmlPlusOneCancelInvoice` once per selected document.

- `POST /api/lock/acquire`, `POST /api/lock/heartbeat`, and `POST /api/lock/release`
  Manage the application lock in `dbo.hmlPlusOneAppLock`.

### Application Lock

The web app uses `dbo.hmlPlusOneAppLock` to prevent two active users from processing the same site workflow at the same time.

The lock row stores:

- app name
- lock ID
- site
- user name
- machine name
- acquired date/time
- last heartbeat date/time

If a previous session leaves a lock behind, the same user on the same machine can reclaim the lock. An administrator can also clear a stuck lock with:

```sql
DELETE dbo.hmlPlusOneAppLock
WHERE AppName = 'PlusOneWeb';
```

Run this in the affected site database.

## Runtime Scripts

### `PlusOnePython/plusone.py`

Shared integration engine.

Responsibilities:

- download invoice CSV files from SFTP
- validate file contents
- bulk load line staging rows
- call the batch header staging procedure
- define supported outbound extracts
- execute extract queries
- write outbound CSV files
- upload outbound files to SFTP
- write operational messages
- archive processed files

### `PlusOnePython/plusone_web.py`

Production web service and UI host.

Responsibilities:

- serve the browser UI from `PlusOneWeb`
- expose document and line API endpoints
- run download/import from the web UI
- process selected invoice headers one at a time
- update editable accounting dates before processing
- manage application locking

### Compiled PowerShell Helpers

The compiled folder includes helper scripts used to launch packaged workflows:

- `PlusOnePython/Compiled/Run-PlusOneWeb.ps1`
- `PlusOnePython/Compiled/Run-PlusOne.ps1`
- `PlusOnePython/Compiled/Run-ExtractUpload.ps1`

## Status Model

The staging tables currently use these status meanings:

- `0`: Ready
- `1`: Processing
- `2`: Processed
- `8`: Cancelled
- `9`: Error

These values are surfaced in both views with human-readable descriptions.

The UI displays the status description as a badge. If the row has an error message, hovering over the status badge opens an in-app tooltip:

- header badge tooltip: `HeaderMessage`
- expanded line badge tooltip: `LineMessage`, falling back to `HeaderMessage`

The `Cancelled` filter option is available but not selected by default. Cancelled badges use a neutral grey style so they are visually distinct from actionable error rows.

## Error Handling Model

### Import Errors

Handled in Python before staging completes.

Examples:

- bad CSV headers
- invalid dates
- invalid numeric values
- SQL bulk insert failures

Result:

- message written to `hmlPlusOneMessages`
- file archived to failed folder
- no usable staged header is created

### Processing Errors

Handled in `dbo.hmlPlusOneProcessInvoice`.

Examples:

- duplicate document number already in GP
- missing supplier
- blank vendor tax schedule
- blank or invalid vendor currency setup
- blank company functional currency setup
- missing or blank GL account on one or more lines
- GP eConnect or ta procedure failures

Result:

- GP transaction work rolls back when a failure occurs after GP creation begins
- header status becomes `Error`
- pre-validation line account errors are written to every invalid line before GP creation begins
- the header message combines all pre-validation line account messages into one summary
- processing-time line failures mark the offending line when identifiable
- error text is stored in `HeaderMessage` and/or `LineMessage`
- audit message is written to `hmlPlusOneMessages`

### Currency And Tax Handling

Currency and tax setup is driven by GP vendor/company setup:

- vendor currency comes from `PM00200.CURNCYID`
- vendor tax schedule comes from `PM00200.TAXSCHID`
- company functional currency comes from `MC40000.FUNLCURR`

The processing procedure uses the normal distribution path when the PM transaction currency matches the company functional currency. It uses the multicurrency distribution path when the PM transaction currency differs from the company functional currency.

The procedure does not hardcode NZ or AU tax schedules. If `PM00200.TAXSCHID` is blank, processing stops with a header error before GP transaction creation.

### Upload Errors

Handled in `PlusOnePython/plusone.py`.

Examples:

- no connection to SFTP
- SFTP transfer failures
- file transfer failures

Result:

- message written to `hmlPlusOneMessages`
- file moved to failed upload archive folder

## Logging And Archive Model

### Logs

Each site can write:

- download/import log
- extract log
- upload log

Logs are plain text log files written to the configured paths in `PlusOneConfig.json`.

### Archives

Inbound and outbound file archives are folder-based.

The current pattern is:

- `Success` subfolder
- `Failed` subfolder

This keeps the original files available for operational review and support investigations.

## Production UI Design

The production UI is focused on inbound invoice download, staging review, and processing status.
It is not intended to run outbound extract or upload jobs.

Primary action:

- download and import invoices for the selected site
- process selected ready/error invoice headers into Dynamics GP
- cancel selected ready/error invoice headers while retaining audit history

### Header Window

Primary data source:

- `dbo.vw_hmlPlusOneInvoiceHeader`

Required fields:

- batch
- site
- supplier ID
- supplier name
- document number
- document date
- accounting date
- PO number
- subtotal
- tax
- total
- current status

Suggested supporting actions:

- refresh
- view lines
- process selected
- cancel selected

Action layout:

- `Process Selected` is placed before `Cancel Selected`
- `Cancel Selected` uses a red danger-style button to distinguish it from normal processing
- cancellation requires a confirmation prompt before any selected records are updated

Error behavior:

- header status shows a tooltip when `HeaderMessage` has a value
- line error count and first error line are provided by the header view

### Line Detail Window

Primary data source:

- `dbo.vw_hmlPlusOneInvoiceLineDetail`

Required fields:

- ledger code shown as account code
- line value excluding GST shown as amount
- line description
- line status

Error behavior:

- line status shows a tooltip when `LineMessage` has a value
- if no line message exists but the header has a message, the line status tooltip can fall back to the header message

### Message Window

Primary data source:

- `dbo.hmlPlusOneMessages`

Suggested purpose:

- operational history
- failed import and failed upload review
- quick support diagnostics

## End-To-End Sequence Summary

### Inbound

1. User opens the web application or runs the integration helper.
2. The shared Python download/import workflow downloads invoice CSV files.
3. The script validates and bulk loads lines into `hmlPlusOneInvoiceLine`.
4. The script calls `hmlPlusOneStageImportedBatch`.
5. Header rows are created in `hmlPlusOneInvoiceHeader`.
6. The GP user launches the PlusOne web application.
7. The user reviews staged invoices in the sortable header grid.
8. The user expands a document number when line detail is needed.
9. If needed, the user edits `AccountingValueDate` before processing.
10. The user selects one or more processable invoices.
11. The web app calls `/api/process`.
12. `/api/process` calls `hmlPlusOneProcessInvoice` once per selected invoice header.
13. SQL pre-validates the invoice and, if valid, creates the GP PM transaction.
14. The document date is used as the GP document date, and `AccountingValueDate` is used as the GP posting date.
15. SQL updates staging status, voucher references, and error messages.
16. Errors are shown back through header and expanded line status tooltips.
17. If a user cancels a `Ready` or `Error` invoice, `/api/cancel` marks the header and lines as `Cancelled` and records who cancelled it in `HeaderMessage`.

### Outbound

1. User or schedule runs the extract workflow through `PlusOnePython/plusone.py` or `Run-ExtractUpload.ps1`.
2. The shared extract script writes CSV files to the local upload folder.
3. User or schedule runs the upload workflow through `PlusOnePython/plusone.py` or `Run-ExtractUpload.ps1`.
4. The shared upload script sends files to the PlusOne SFTP inbound folder.
5. Success or failure is logged and the source file is archived.

## Deployment Order

Recommended SQL deployment order:

1. `table hmlPlusOneMessages.sql`
2. `table hmlPlusOneAppLock.sql`
3. `table hmlPlusOneInvoiceHeader.sql`
4. `table hmlPlusOneInvoiceLine.sql`
5. `proc hmlPlusOneStageImportedBatch.txt`
6. `proc hmlPlusOneProcessInvoice.txt`
7. `proc hmlPlusOneCancelInvoice.txt`
8. `proc hmlPlusOneCreateNonPOInvoice.txt`
9. `view hmlPlusOneInvoiceHeader.sql`
10. `view hmlPlusOneInvoiceLineDetail.sql`

Recommended script deployment:

1. `PlusOnePython/PlusOneConfig.local.template.json`
2. site-specific `PlusOnePython/PlusOneConfig.json`
3. `PlusOnePython/plusone.py`
4. `PlusOnePython/plusone_web.py`
5. `PlusOnePython/PlusOneWeb/index.html`
6. `PlusOnePython/Build-PlusOneWeb.ps1`
7. compiled output under `PlusOnePython/Compiled`

Build the web application with:

```powershell
powershell -ExecutionPolicy Bypass -File PlusOnePython\Build-PlusOneWeb.ps1
```

Launch the compiled web application with:

```powershell
PlusOnePython\Compiled\PlusOneWeb.exe --config PlusOnePython\Compiled\PlusOneConfig.json --host 127.0.0.1 --port 8091
```

## Operational Notes

- The split header/line model is the correct fit for a GP review-and-process screen.
- `SourceLineNo` is important because it lets the user identify the exact source CSV line that failed.
- The current process is safest when SQL processes one invoice header at a time.
- The web UI may submit multiple selected invoices, but the backend still calls the processing procedure once per header.
- The web UI uses inline expandable line detail rows rather than a separate line grid.
- `AccountingValueDate` is editable in the web UI for `Ready` and `Error` invoices and is used as the GP posting date.
- The process-all wrapper remains useful for batch operations, but the UI should still expose individual processing and line review.
- The repository still contains legacy artifacts from the single-table design for reference and transition support.
- SQL procedure changes are not automatically deployed by rebuilding the web application. Deploy changed `.txt` SQL scripts separately to each site database.

## Future UI Completion Notes

Future UI changes should preserve these patterns:

- using the new header and line views instead of the legacy single table
- exposing the production header columns listed above
- showing the matching line rows when a user selects an invoice header
- using download/import and selected-document processing as the executable integration actions in this screen
- preserving selected-document cancellation for `Ready` and `Error` invoices
- preserving one-header-at-a-time backend processing even when multiple headers are selected
- showing header and line processing messages close to the status fields
- optionally exposing `hmlPlusOneMessages` as a support inquiry area
