# PlusOne Workflow Documentation

## Purpose

This document explains the current PlusOne integration workflow across:

- inbound invoice download and staging
- assumed Dynamics GP user interface processing
- SQL processing into Dynamics GP Payables
- outbound extract generation
- outbound file upload back to PlusOne
- supporting logs, messages, configuration, and archive behavior

This document is written as if the Dynamics GP user interface is complete, even though the UI build is still in progress.

## Scope And Assumptions

- Two sites are supported: `NZ` and `AU`.
- Each site has its own SFTP credentials, local working folders, and SQL database.
- PowerShell handles file transfer and file staging.
- SQL Server handles staging, processing state, and GP integration procedures.
- The GP UI is assumed to provide a header-level browse, line-level drilldown, and process actions.
- WinSCP command-line is the SFTP engine used by the PowerShell scripts.

## High-Level Architecture

There are two main flows:

1. Inbound invoice flow
   PlusOne SFTP outbound folder -> PowerShell download/import -> SQL staging header/line tables -> GP UI review/process -> Dynamics GP PM transaction creation

2. Outbound master data / purchasing flow
   SQL extract queries -> local CSV output files -> PowerShell upload -> PlusOne SFTP inbound folder

## Site Separation

Site-specific configuration is stored in:

- `Source Process Folders/PlusOneWorkspace/Scripts/PlusOneConfig.json`
- `Source Process Folders/PlusOneWorkspace/Scripts/PlusOneConfig.json.template`

Each site entry defines:

- SFTP host, port, username, password, host key fingerprint
- remote download and upload folders
- local download, upload, log, and archive paths
- SQL connection string
- SQL command and bulk copy timeouts

The runtime `PlusOneConfig.json` contains live credentials and should be protected. The template is the safer reference for deployment packaging.

## Inbound Invoice Workflow

### 1. Download And Import

The main inbound engine is:

- `Source Process Folders/PlusOneWorkspace/Scripts/PlusOne-Download-Import.ps1`

Site wrapper scripts are:

- `Source Process Folders/PlusOneWorkspace/Scripts/Download-NZ.ps1`
- `Source Process Folders/PlusOneWorkspace/Scripts/Download-AU.ps1`

The download/import script performs these steps:

1. Load the site configuration.
2. Connect to the PlusOne SFTP endpoint using WinSCP.
3. Download matching CSV files from the configured remote outbound folder.
4. Validate the CSV structure and data types.
5. Bulk insert imported rows into `dbo.hmlPlusOneInvoiceLine`.
6. Call `dbo.hmlPlusOneStageImportedBatch` to create grouped header rows in `dbo.hmlPlusOneInvoiceHeader`.
7. Write operational messages to `dbo.hmlPlusOneMessages`.
8. Move the downloaded file into archive subfolders.

### 2. CSV Validation

Inbound CSV validation is handled inside `PlusOne-Download-Import.ps1`.

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

This split staging model is the basis for the GP UI.

### 4. GP UI Review

The GP UI is assumed to expose the staging data like this:

- a header browse bound to `dbo.vw_hmlPlusOneInvoiceHeader`
- a line drilldown bound to `dbo.vw_hmlPlusOneInvoiceLineDetail`
- a process button that calls `dbo.hmlPlusOneProcessInvoiceHeader`
- an optional process-all action that calls `dbo.hmlPlusOneCreateNonPOInvoice`

The intended user workflow is:

1. Open the PlusOne invoice staging screen in GP.
2. Review header-level invoices waiting in `Ready` status.
3. Open line drilldown if the invoice has line errors or needs review.
4. Process one invoice header at a time.
5. Review success or error feedback directly in the same screen.

### 5. SQL Processing Into GP

The processing flow is centered around:

- `dbo.hmlPlusOneProcessInvoiceHeader`

This procedure:

1. Locks the selected header.
2. Resets header and line processing messages for that invoice.
3. Checks for duplicate document numbers already in GP.
4. Validates the supplier and currency setup in GP.
5. Sums line amounts into a document total.
6. Creates the PM voucher number.
7. Creates the PM tax record.
8. Creates the PM transaction header.
9. Writes the PlusOne image URL into GP notes.
10. Deletes the default GP expense distribution.
11. Rebuilds distributions from the staged invoice lines.
12. Marks the header and lines as processed on success.
13. Marks the header and offending line as error on failure.
14. Writes an audit message to `dbo.hmlPlusOneMessages`.

The process-all wrapper is:

- `dbo.hmlPlusOneCreateNonPOInvoice`

This wrapper finds all header rows in `Status = 0` and processes them one by one using the single-header procedure.

## Outbound Extract And Upload Workflow

### 1. Extract Generation

The main extract engine is:

- `Source Process Folders/PlusOneWorkspace/Scripts/PlusOne-Extract.ps1`

Site wrapper scripts are:

- `Source Process Folders/PlusOneWorkspace/Scripts/Extract-NZ.ps1`
- `Source Process Folders/PlusOneWorkspace/Scripts/Extract-AU.ps1`

The extract script currently supports these data sets:

- `GLM` for GL code master
- `SUP` for supplier master
- `PUR` for purchase orders

The extract definitions are embedded inside `Get-ExtractionDefinitions` in `PlusOne-Extract.ps1`.

For each requested extract, the script:

1. loads the site configuration
2. runs the configured SQL query
3. writes the result to CSV in the site upload folder
4. writes an extract log entry

### 2. Upload

The main upload engine is:

- `Source Process Folders/PlusOneWorkspace/Scripts/PlusOne-Upload.ps1`

Site wrapper scripts are:

- `Source Process Folders/PlusOneWorkspace/Scripts/Upload-NZ.ps1`
- `Source Process Folders/PlusOneWorkspace/Scripts/Upload-AU.ps1`

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

- `InvoiceHeaderID`: primary key used by the GP UI and processing procedure
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

- bulk loaded by `PlusOne-Download-Import.ps1`
- grouped into headers by `dbo.hmlPlusOneStageImportedBatch`
- read by `dbo.hmlPlusOneProcessInvoiceHeader` to build GP distributions
- shown to the user through the line detail view

### `dbo.vw_hmlPlusOneInvoiceHeader`

Purpose:
Header-only browse view for the GP UI.

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
Detailed line drilldown view for the GP UI.

Provides:

- all staged invoice lines for a selected header
- line status and line error message
- header status and header message
- GP voucher and batch references

Recommended use:

- error review window
- line inquiry window

### `dbo.hmlPlusOneStageImportedBatch`

Purpose:
Converts newly imported line rows into grouped header rows.

Responsibilities:

- validate that the batch exists
- create header rows for each unique `SupplierID + DocumentNo`
- normalize `DocumentNo`
- link line rows to the created header rows
- reset line processing state for the imported batch

### `dbo.hmlPlusOneProcessInvoiceHeader`

Purpose:
Process one selected staged invoice into Dynamics GP.

Responsibilities:

- enforce one-header-at-a-time processing
- validate duplicates and supplier setup
- create PM tax, header, notes, and distributions
- preserve error context at header and line level
- update statuses and audit trail

### `dbo.hmlPlusOneCreateNonPOInvoice`

Purpose:
Legacy-compatible batch wrapper around the new single-header process.

Responsibilities:

- select all `Ready` headers
- call `dbo.hmlPlusOneProcessInvoiceHeader` for each one

Recommended use:

- optional unattended or bulk process option
- backward compatibility where older automation expects this procedure name

### `dbo.hmlPlusOneMessages`

Purpose:
Simple operational message and audit table used by PowerShell and SQL procedures.

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

## PowerShell Scripts

### `PlusOne-Download-Import.ps1`

Shared inbound invoice engine.

Responsibilities:

- download invoice CSV files from SFTP
- validate file contents
- bulk load line staging rows
- call the batch header staging procedure
- log messages
- archive processed source files

### `Download-NZ.ps1` and `Download-AU.ps1`

Thin wrappers for the shared download/import engine.

Responsibilities:

- call `PlusOne-Download-Import.ps1` with the correct site parameter

### `PlusOne-Extract.ps1`

Shared outbound extract engine.

Responsibilities:

- define supported SQL extracts
- execute extract queries
- write CSV output files
- log extract activity

### `Extract-NZ.ps1` and `Extract-AU.ps1`

Thin wrappers for the shared extract engine.

Responsibilities:

- call `PlusOne-Extract.ps1` with the correct site parameter

### `PlusOne-Upload.ps1`

Shared outbound upload engine.

Responsibilities:

- scan upload folders
- upload matching files to SFTP
- write success or failure messages
- archive uploaded files

### `Upload-NZ.ps1` and `Upload-AU.ps1`

Thin wrappers for the shared upload engine.

Responsibilities:

- call `PlusOne-Upload.ps1` with the correct site parameter

## Status Model

The staging tables currently use these status meanings:

- `0`: Ready
- `1`: Processing
- `2`: Processed
- `9`: Error

These values are surfaced in both views with human-readable descriptions.

## Error Handling Model

### Import Errors

Handled in PowerShell before staging completes.

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

Handled in `dbo.hmlPlusOneProcessInvoiceHeader`.

Examples:

- duplicate document number already in GP
- missing supplier
- blank or invalid currency setup
- missing GL account
- GP eConnect or ta procedure failures

Result:

- SQL transaction rolls back
- header status becomes `Error`
- offending line is marked `Error` when identifiable
- error text is stored in `HeaderMessage` and/or `LineMessage`
- audit message is written to `hmlPlusOneMessages`

### Upload Errors

Handled in `PlusOne-Upload.ps1`.

Examples:

- no connection to SFTP
- WinSCP failures
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

Logs are plain text PowerShell log files written to the configured paths in `PlusOneConfig.json`.

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

### Line Detail Window

Primary data source:

- `dbo.vw_hmlPlusOneInvoiceLineDetail`

Required fields:

- ledger code shown as account code
- line value excluding GST shown as amount
- line description
- line status

### Message Window

Primary data source:

- `dbo.hmlPlusOneMessages`

Suggested purpose:

- operational history
- failed import and failed upload review
- quick support diagnostics

## End-To-End Sequence Summary

### Inbound

1. User or schedule runs `Download-NZ.ps1` or `Download-AU.ps1`.
2. The shared download/import script downloads invoice CSV files.
3. The script validates and bulk loads lines into `hmlPlusOneInvoiceLine`.
4. The script calls `hmlPlusOneStageImportedBatch`.
5. Header rows are created in `hmlPlusOneInvoiceHeader`.
6. The GP user reviews staged invoices in the assumed GP header window.
7. The user processes one invoice by calling `hmlPlusOneProcessInvoiceHeader`.
8. SQL creates the GP PM transaction and updates staging status.
9. Errors are shown back to the user through the assumed GP browse and drilldown views.

### Outbound

1. User or schedule runs `Extract-NZ.ps1` or `Extract-AU.ps1`.
2. The shared extract script writes CSV files to the local upload folder.
3. User or schedule runs `Upload-NZ.ps1` or `Upload-AU.ps1`.
4. The shared upload script sends files to the PlusOne SFTP inbound folder.
5. Success or failure is logged and the source file is archived.

## Deployment Order

Recommended SQL deployment order:

1. `table hmlPlusOneMessages.sql`
2. `table hmlPlusOneAppLock.sql`
3. `table hmlPlusOneInvoiceHeader.sql`
4. `table hmlPlusOneInvoiceLine.sql`
5. `proc hmlPlusOneStageImportedBatch.txt`
6. `proc hmlPlusOneProcessInvoiceHeader.txt`
7. `proc hmlPlusOneCreateNonPOInvoice.txt`
8. `view hmlPlusOneInvoiceHeader.sql`
9. `view hmlPlusOneInvoiceLineDetail.sql`

Recommended script deployment:

1. `PlusOneConfig.json.template`
2. `PlusOne-Download-Import.ps1`
3. `PlusOne-Extract.ps1`
4. `PlusOne-Upload.ps1`
5. wrapper scripts for NZ and AU
6. site-specific `PlusOneConfig.json`

## Operational Notes

- The split header/line model is the correct fit for a GP review-and-process screen.
- `SourceLineNo` is important because it lets the user identify the exact source CSV line that failed.
- The current process is safest when the GP UI processes one invoice header at a time.
- The process-all wrapper remains useful for batch operations, but the UI should still expose individual processing and line review.
- The repository still contains legacy artifacts from the single-table design for reference and transition support.

## Future UI Completion Notes

When the GP UI is finished, it should align to this document by:

- using the new header and line views instead of the legacy single table
- exposing the production header columns listed above
- showing the matching line rows when a user selects an invoice header
- using download/import as the only executable integration action in this screen
- optionally exposing `hmlPlusOneMessages` as a support inquiry area
