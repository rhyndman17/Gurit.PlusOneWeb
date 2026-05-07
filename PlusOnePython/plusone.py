from __future__ import annotations

import argparse
import base64
import csv
import fnmatch
import hashlib
import io
import json
import logging
import os
import shutil
import sys
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterable


EXPECTED_INVOICE_HEADERS = [
    "GLDimension1",
    "GLDimension2",
    "SupplierID",
    "DocumentDate",
    "AccountingValueDate",
    "DocumentNo",
    "ImageURL",
    "LedgerCode",
    "LineValueExclGST",
    "LineValueGST",
    "LineDescription",
    "PurchaseOrderNo",
    "PurchaseOrderLineNo",
    "InvoicedQty",
    "GLDimension3",
]

LINE_COLUMN_LIMITS = {
    "GLDimension1": 20,
    "GLDimension2": 20,
    "SupplierID": 15,
    "DocumentNo": 21,
    "ImageURL": 200,
    "FileName": 200,
    "LedgerCode": 50,
    "LineDescription": 30,
    "PurchaseOrderNo": 20,
    "GLDimension3": 50,
}


@dataclass(frozen=True)
class SiteConfig:
    name: str
    values: dict[str, Any]

    def text(self, key: str, default: str = "") -> str:
        value = self.values.get(key, default)
        while isinstance(value, list):
            value = value[0] if value else default
        return "" if value is None else str(value)

    def integer(self, key: str, default: int) -> int:
        value = self.values.get(key, default)
        while isinstance(value, list):
            value = value[0] if value else default
        return int(value or default)

    @property
    def sql_timeout(self) -> int:
        return self.integer("SqlCommandTimeout", 120)

    @property
    def bulk_timeout(self) -> int:
        return self.integer("SqlBulkInsertTimeout", self.sql_timeout)


def configure_logger(log_file: str | None) -> logging.Logger:
    logger = logging.getLogger("plusone")
    logger.handlers.clear()
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s", "%Y-%m-%d %H:%M:%S")

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    if log_file:
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


def load_site_config(config_path: Path, site: str) -> SiteConfig:
    with config_path.open("r", encoding="utf-8") as handle:
        config = json.load(handle)

    sites = config.get("Sites", {})
    site_key = site.upper()
    if site_key not in sites:
        available = ", ".join(sorted(sites.keys()))
        raise ValueError(f"Site '{site}' is not defined in {config_path}. Available sites: {available}")

    return SiteConfig(name=site_key, values=sites[site_key])


def import_optional(module_name: str, install_name: str):
    try:
        return __import__(module_name)
    except ImportError as exc:
        raise RuntimeError(f"Missing dependency '{install_name}'. Install requirements.txt first.") from exc


def set_query_timeout(connection: Any, timeout: int) -> None:
    try:
        connection.timeout = int(timeout)
    except AttributeError:
        pass


class PlusOneHostKeyPolicy:
    def __init__(self, configured_fingerprint: str) -> None:
        self.configured_fingerprint = configured_fingerprint.strip()

    def missing_host_key(self, client: Any, hostname: str, key: Any) -> None:
        if not self.configured_fingerprint:
            raise RuntimeError("HostKeyFingerprint is not configured.")

        expected = self.configured_fingerprint.split()[-1]
        actual = base64.b64encode(hashlib.sha256(key.asbytes()).digest()).decode("ascii")
        if expected.rstrip("=") != actual.rstrip("="):
            raise RuntimeError(
                f"SFTP host key mismatch for {hostname}. Expected {expected}, received SHA256 {actual}."
            )
        client.get_host_keys().add(hostname, key.get_name(), key)


def odbc_connection_string(connection_string: str) -> str:
    parts: dict[str, str] = {}
    for raw_part in connection_string.split(";"):
        if not raw_part.strip() or "=" not in raw_part:
            continue
        key, value = raw_part.split("=", 1)
        parts[key.strip().lower()] = value.strip()

    if "driver" in parts:
        return connection_string

    server = parts.get("server") or parts.get("data source")
    database = parts.get("database") or parts.get("initial catalog")
    user = parts.get("user id") or parts.get("uid")
    password = parts.get("password") or parts.get("pwd")
    trusted = parts.get("trusted_connection") or parts.get("integrated security")
    encrypt = parts.get("encrypt")
    trust_server_certificate = parts.get("trustservercertificate")
    driver = os.environ.get("PLUSONE_ODBC_DRIVER", "ODBC Driver 17 for SQL Server")

    rebuilt = [f"DRIVER={{{driver}}}"]
    if server:
        rebuilt.append(f"SERVER={server}")
    if database:
        rebuilt.append(f"DATABASE={database}")
    if user:
        rebuilt.append(f"UID={user}")
    if password:
        rebuilt.append(f"PWD={password}")
    if trusted:
        rebuilt.append(f"Trusted_Connection={trusted}")
    rebuilt.append(f"Encrypt={encrypt or 'no'}")
    rebuilt.append(f"TrustServerCertificate={trust_server_certificate or 'yes'}")
    return ";".join(rebuilt) + ";"


@contextmanager
def sql_connection(site_config: SiteConfig):
    pyodbc = import_optional("pyodbc", "pyodbc")
    raw = site_config.text("SqlConnectionString")
    if not raw:
        raise ValueError(f"SqlConnectionString is not defined for site '{site_config.name}'.")
    connection = pyodbc.connect(odbc_connection_string(raw), timeout=site_config.sql_timeout)
    set_query_timeout(connection, site_config.sql_timeout)
    try:
        yield connection
    finally:
        connection.close()


def limit_text(value: Any, max_length: int, column: str, truncation_counts: dict[str, int] | None = None) -> str:
    text = "" if value is None else str(value)
    if len(text) <= max_length:
        return text
    if truncation_counts is not None:
        truncation_counts[column] = truncation_counts.get(column, 0) + 1
    return text[:max_length]


def parse_plusone_date(value: str) -> datetime:
    for fmt in ("%Y%m%d", "%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            pass
    raise ValueError(f"'{value}' is invalid")


def parse_decimal(value: str, column_name: str) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{column_name} '{value}' is invalid") from exc


def parse_int(value: str, column_name: str) -> int:
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"{column_name} '{value}' is invalid") from exc


def parse_plusone_csv(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    last_error: UnicodeDecodeError | None = None
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            text = path.read_text(encoding=encoding)
            break
        except UnicodeDecodeError as exc:
            last_error = exc
    else:
        assert last_error is not None
        raise last_error

    reader = csv.DictReader(io.StringIO(text, newline=""))
    actual_headers = reader.fieldnames or []
    missing = [header for header in EXPECTED_INVOICE_HEADERS if header not in actual_headers]
    if missing:
        raise ValueError(f"CSV header mismatch. Missing columns: {', '.join(missing)}")

    rows: list[dict[str, Any]] = []
    errors: list[str] = []
    for row_number, row in enumerate(reader, start=2):
        issues: list[str] = []

        for required in ("SupplierID", "DocumentNo", "LedgerCode"):
            if not (row.get(required) or "").strip():
                issues.append(f"{required} is required.")

        try:
            document_date = parse_plusone_date((row.get("DocumentDate") or "").strip())
        except ValueError:
            issues.append(f"DocumentDate '{row.get('DocumentDate')}' is invalid.")
            document_date = None

        try:
            accounting_date = parse_plusone_date((row.get("AccountingValueDate") or "").strip())
        except ValueError:
            issues.append(f"AccountingValueDate '{row.get('AccountingValueDate')}' is invalid.")
            accounting_date = None

        try:
            line_value_excl_gst = parse_decimal(row.get("LineValueExclGST") or "", "LineValueExclGST")
        except ValueError as exc:
            issues.append(str(exc) + ".")
            line_value_excl_gst = Decimal("0")

        try:
            line_value_gst = parse_decimal(row.get("LineValueGST") or "", "LineValueGST")
        except ValueError as exc:
            issues.append(str(exc) + ".")
            line_value_gst = Decimal("0")

        po_line_text = (row.get("PurchaseOrderLineNo") or "").strip()
        try:
            po_line = parse_int(po_line_text, "PurchaseOrderLineNo") if po_line_text else 0
        except ValueError as exc:
            issues.append(str(exc) + ".")
            po_line = 0

        try:
            invoiced_qty = parse_decimal(row.get("InvoicedQty") or "", "InvoicedQty")
        except ValueError as exc:
            issues.append(str(exc) + ".")
            invoiced_qty = Decimal("0")

        if issues:
            errors.append(f"Line {row_number}: {' '.join(issues)}")
            continue

        rows.append(
            {
                "SourceLineNo": row_number,
                "GLDimension1": (row.get("GLDimension1") or "").strip(),
                "GLDimension2": (row.get("GLDimension2") or "").strip(),
                "SupplierID": (row.get("SupplierID") or "").strip().upper(),
                "DocumentDate": document_date,
                "AccountingValueDate": accounting_date,
                "DocumentNo": (row.get("DocumentNo") or "").strip().upper(),
                "ImageURL": (row.get("ImageURL") or "").strip(),
                "LedgerCode": (row.get("LedgerCode") or "").strip(),
                "LineValueExclGST": line_value_excl_gst,
                "LineValueGST": line_value_gst,
                "LineDescription": (row.get("LineDescription") or "").strip(),
                "PurchaseOrderNo": (row.get("PurchaseOrderNo") or "").strip(),
                "POLine": po_line,
                "InvoicedQty": invoiced_qty,
                "GLDimension3": (row.get("GLDimension3") or "").strip(),
            }
        )

    return rows, errors


def insert_message(site_config: SiteConfig, message_id: str, detail1: str, detail2: str = "", message_state: int = 1) -> None:
    detail_desc1 = limit_text(detail1, 100, "DetailDesc1")
    detail_desc2 = limit_text(detail2, 100, "DetailDesc2")
    message_string1 = limit_text(detail1, 255, "MessageString1")
    message_string2 = limit_text(detail2, 255, "MessageString2")
    sql = """
INSERT INTO dbo.hmlPlusOneMessages
    (MessageDateTime, DetailDesc1, DetailDesc2, MessageID, MessageState, MessageString1, MessageString2)
VALUES
    (GETDATE(), ?, ?, ?, ?, ?, ?)
"""
    with sql_connection(site_config) as connection:
        cursor = connection.cursor()
        cursor.execute(sql, detail_desc1, detail_desc2, message_id, message_state, message_string1, message_string2)
        connection.commit()


def move_file_to_archive(source: Path, archive_root: str, status: str, logger: logging.Logger) -> Path:
    subfolder = "Success" if status == "Success" else "Failed"
    target_dir = Path(archive_root) / subfolder
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / source.name
    if target.exists():
        target = target_dir / f"{source.stem}_{datetime.now():%Y%m%d%H%M%S}{source.suffix}"
    shutil.move(str(source), str(target))
    logger.info("Moved '%s' to '%s'.", source, target)
    return target


def stage_imported_lines(site_config: SiteConfig, rows: list[dict[str, Any]], file_name: str, logger: logging.Logger) -> tuple[uuid.UUID, int, int]:
    import_batch_id = uuid.uuid4()
    truncation_counts: dict[str, int] = {}
    sql = """
INSERT INTO dbo.hmlPlusOneInvoiceLine
    (ImportBatchID, SourceLineNo, GLDimension1, GLDimension2, SupplierID, DocumentDate,
     AccountingValueDate, DocumentNo, ImageURL, FileName, LedgerCode, LineValueExclGST,
     LineValueGST, UnitValueExclGST, UnitValueGST, LineDescription, PurchaseOrderNo,
     POLine, InvoicedQty, GLDimension3)
VALUES
    (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""
    prepared = []
    for row in rows:
        prepared.append(
            (
                str(import_batch_id),
                int(row["SourceLineNo"]),
                limit_text(row["GLDimension1"], LINE_COLUMN_LIMITS["GLDimension1"], "GLDimension1", truncation_counts),
                limit_text(row["GLDimension2"], LINE_COLUMN_LIMITS["GLDimension2"], "GLDimension2", truncation_counts),
                limit_text(row["SupplierID"], LINE_COLUMN_LIMITS["SupplierID"], "SupplierID", truncation_counts),
                row["DocumentDate"],
                row["AccountingValueDate"],
                limit_text(row["DocumentNo"], LINE_COLUMN_LIMITS["DocumentNo"], "DocumentNo", truncation_counts),
                limit_text(row["ImageURL"], LINE_COLUMN_LIMITS["ImageURL"], "ImageURL", truncation_counts),
                limit_text(file_name, LINE_COLUMN_LIMITS["FileName"], "FileName", truncation_counts),
                limit_text(row["LedgerCode"], LINE_COLUMN_LIMITS["LedgerCode"], "LedgerCode", truncation_counts),
                row["LineValueExclGST"],
                row["LineValueGST"],
                Decimal("0"),
                Decimal("0"),
                limit_text(row["LineDescription"], LINE_COLUMN_LIMITS["LineDescription"], "LineDescription", truncation_counts),
                limit_text(row["PurchaseOrderNo"], LINE_COLUMN_LIMITS["PurchaseOrderNo"], "PurchaseOrderNo", truncation_counts),
                int(row["POLine"]),
                row["InvoicedQty"],
                limit_text(row["GLDimension3"], LINE_COLUMN_LIMITS["GLDimension3"], "GLDimension3", truncation_counts),
            )
        )

    for column, count in sorted(truncation_counts.items()):
        logger.warning("Truncated %s value(s) for '%s' to match dbo.hmlPlusOneInvoiceLine column length.", count, column)

    invoice_count = len({(row["SupplierID"], row["DocumentNo"]) for row in rows})
    with sql_connection(site_config) as connection:
        cursor = connection.cursor()
        set_query_timeout(connection, site_config.bulk_timeout)
        if hasattr(cursor, "fast_executemany"):
            cursor.fast_executemany = True
        logger.info("Inserting %s line row(s) from '%s' into dbo.hmlPlusOneInvoiceLine.", len(prepared), file_name)
        try:
            cursor.executemany(sql, prepared)
            set_query_timeout(connection, site_config.sql_timeout)
            cursor.execute("EXEC dbo.hmlPlusOneStageImportedBatch @ImportBatchID = ?", str(import_batch_id))
            connection.commit()
        except Exception:
            connection.rollback()
            raise

    return import_batch_id, invoice_count, len(prepared)


def download_remote_files(site_config: SiteConfig, logger: logging.Logger, what_if: bool) -> None:
    if what_if:
        logger.info("WhatIf mode: not downloading from SFTP.")
        return

    paramiko = import_optional("paramiko", "paramiko")
    remote_dir = site_config.text("RemoteDownloadDirectory")
    remote_filter = site_config.text("RemoteDownloadFilter", "*.csv")
    local_dir = Path(site_config.text("LocalDownloadPath"))
    local_dir.mkdir(parents=True, exist_ok=True)

    client = paramiko.SSHClient()
    client.load_system_host_keys()
    client.set_missing_host_key_policy(PlusOneHostKeyPolicy(site_config.text("HostKeyFingerprint")))
    try:
        client.connect(
            hostname=site_config.text("SftpHost"),
            port=site_config.integer("SftpPort", 22),
            username=site_config.text("Username"),
            password=site_config.text("Password"),
            look_for_keys=False,
        )
        sftp = client.open_sftp()
        try:
            for file_name in sorted(sftp.listdir(remote_dir)):
                if not fnmatch.fnmatch(file_name, remote_filter):
                    continue
                remote_path = f"{remote_dir.rstrip('/')}/{file_name}"
                local_path = local_dir / file_name
                logger.info("Downloading '%s' to '%s'.", remote_path, local_path)
                sftp.get(remote_path, str(local_path))
                sftp.remove(remote_path)
        finally:
            sftp.close()
    finally:
        client.close()


def process_downloaded_file(path: Path, site_config: SiteConfig, logger: logging.Logger) -> None:
    logger.info("Processing downloaded file: %s", path.name)
    try:
        rows, errors = parse_plusone_csv(path)
    except Exception as exc:
        error_message = f"CSV parsing failed for '{path.name}': {exc}"
        logger.error(error_message)
        insert_message(site_config, "CSVERR", path.name, error_message, 9)
        move_file_to_archive(path, site_config.text("DownloadArchivePath"), "Failed", logger)
        return

    if errors:
        error_message = f"Validation failed for '{path.name}': {' | '.join(errors)}"
        logger.error(error_message)
        insert_message(site_config, "CSVERR", path.name, error_message, 9)
        move_file_to_archive(path, site_config.text("DownloadArchivePath"), "Failed", logger)
        return

    try:
        batch_id, invoice_count, line_count = stage_imported_lines(site_config, rows, path.name, logger)
        logger.info("Import succeeded for '%s'. Batch %s staged %s invoice(s) and %s line(s).", path.name, batch_id, invoice_count, line_count)
        insert_message(site_config, "IMPORT", path.name, f"Imported to staging successfully. Batch {batch_id}", 0)
        move_file_to_archive(path, site_config.text("DownloadArchivePath"), "Success", logger)
    except Exception as exc:
        logger.exception("SQL import failed for '%s'.", path.name)
        insert_message(site_config, "SQLERR", path.name, str(exc), 9)
        move_file_to_archive(path, site_config.text("DownloadArchivePath"), "Failed", logger)


def command_download_import(args: argparse.Namespace) -> None:
    site_config = load_site_config(args.config, args.site)
    logger = configure_logger(site_config.text("LogFilePath"))
    logger.info("Starting PlusOne download/import for site '%s'.", site_config.name)

    if not args.skip_download:
        download_remote_files(site_config, logger, args.what_if)

    download_path = Path(site_config.text("LocalDownloadPath"))
    download_path.mkdir(parents=True, exist_ok=True)
    files = sorted(download_path.glob(site_config.text("RemoteDownloadFilter", "*.csv")), key=lambda path: path.stat().st_mtime)
    if not files:
        logger.info("No files found in '%s' matching '%s'.", download_path, site_config.text("RemoteDownloadFilter", "*.csv"))
        return
    if args.what_if:
        for file_path in files:
            logger.info("WhatIf mode: would import '%s'.", file_path)
        return
    for file_path in files:
        process_downloaded_file(file_path, site_config, logger)
    logger.info("Completed PlusOne download/import for site '%s'.", site_config.name)


EXTRACTION_DEFINITIONS = {
    "GLM": {
        "description": "GL code master",
        "query": """
select
    GLAccountCode,
    CodeGroup,
    CodeNumber,
    CodeDescription,
    CodeStatus
from PlusOneGLM
order by GLAccountCode
""",
        "columns": ["GLAccountCode", "CodeGroup", "CodeNumber", "CodeDescription", "CodeStatus"],
        "filename": lambda run_date: f"GLM-GAP-{run_date:%y%m%d}.csv",
        "trim": False,
    },
    "SUP": {
        "description": "Supplier master",
        "query": """
select
    SupplierID,
    SupplierCrossRef as SuppierCrossRef,
    SupplierName,
    SupplierAddressL1,
    SupplierAddressL2,
    SupplierAddressL3,
    SupplierAddressL4,
    SupplierPostcode as SupplierPostCode,
    SupplierCountry,
    SupplierContact,
    SupplierPhone,
    SupplierFax,
    SupplierEmail,
    PaymentMeans,
    Currency,
    CurrencyDesc,
    SupplierAccountName,
    SupplierBankName,
    SupplierBankBranch,
    SupplierAccountNo,
    SupplierTaxID,
    SupplierTaxCode,
    SupplierTaxRate,
    SupplierNotes,
    SupplierDefaultCoding,
    SupplierPOFlag
from PlusOneSUP
order by SupplierID
""",
        "columns": [
            "SupplierID",
            "SuppierCrossRef",
            "SupplierName",
            "SupplierAddressL1",
            "SupplierAddressL2",
            "SupplierAddressL3",
            "SupplierAddressL4",
            "SupplierPostCode",
            "SupplierCountry",
            "SupplierContact",
            "SupplierPhone",
            "SupplierFax",
            "SupplierEmail",
            "PaymentMeans",
            "Currency",
            "CurrencyDesc",
            "SupplierAccountName",
            "SupplierBankName",
            "SupplierBankBranch",
            "SupplierAccountNo",
            "SupplierTaxID",
            "SupplierTaxCode",
            "SupplierTaxRate",
            "SupplierNotes",
            "SupplierDefaultCoding",
            "SupplierPOFlag",
        ],
        "filename": lambda run_date: f"SUP-GAP-{run_date:%y%m%d}.csv",
        "trim": False,
    },
    "PUR": {
        "description": "Purchase orders",
        "query": """
select
    [PayerID],
    [SupplierID],
    [DocumentDate],
    [PONumber],
    [HeaderRefNo],
    [BuyerContact],
    [BuyerEmail],
    [BuyerApproverPrev],
    [BuyerApproverNext],
    [LineNo],
    [LineRefNo1],
    [LineRefNo2],
    [BuyerProductCode],
    [ProductDescription],
    [OrderedQty],
    [OrderedQtyUOM],
    [NetPrice],
    [PerQty],
    [ReceivedQty],
    [CostedQty],
    [ReceivedValue],
    [CostedValue],
    [LineValueExclGST],
    [LineGSTRate],
    [LineGSTValue],
    [Currency]
from PlusOnePUR
order by [PONumber], [ORD]
""",
        "columns": [
            "PayerID",
            "SupplierID",
            "DocumentDate",
            "PONumber",
            "HeaderRefNo",
            "BuyerContact",
            "BuyerEmail",
            "BuyerApproverPrev",
            "BuyerApproverNext",
            "LineNo",
            "LineRefNo1",
            "LineRefNo2",
            "BuyerProductCode",
            "ProductDescription",
            "OrderedQty",
            "OrderedQtyUOM",
            "NetPrice",
            "PerQty",
            "ReceivedQty",
            "CostedQty",
            "ReceivedValue",
            "CostedValue",
            "LineValueExclGST",
            "LineGSTRate",
            "LineGSTValue",
            "Currency",
        ],
        "filename": lambda run_date: f"PUR-GAP-{run_date:%y%m%d}.csv",
        "trim": True,
    },
}


def resolve_extractions(requested: list[str]) -> list[str]:
    if not requested or any(item.lower() == "all" for item in requested):
        return list(EXTRACTION_DEFINITIONS.keys())
    selected = []
    for name in requested:
        key = name.upper()
        if key not in EXTRACTION_DEFINITIONS:
            available = ", ".join(["All"] + list(EXTRACTION_DEFINITIONS.keys()))
            raise ValueError(f"Extraction '{name}' is not defined. Available extractions: {available}.")
        selected.append(key)
    return selected


def csv_value(value: Any, trim: bool = False) -> Any:
    if value is None:
        return ""
    if trim:
        return str(value).strip()
    return value


def export_sql_query_to_csv(site_config: SiteConfig, definition: dict[str, Any], output_path: Path) -> int:
    with sql_connection(site_config) as connection, output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, quoting=csv.QUOTE_ALL, lineterminator="\n")
        columns = definition["columns"]
        writer.writerow(columns)
        cursor = connection.cursor()
        set_query_timeout(connection, site_config.sql_timeout)
        cursor.execute(definition["query"])
        ordinals = {column[0]: index for index, column in enumerate(cursor.description or [])}
        row_count = 0
        trim = bool(definition.get("trim"))
        while True:
            row = cursor.fetchone()
            if row is None:
                break
            writer.writerow([csv_value(row[ordinals[column]], trim) for column in columns])
            row_count += 1
        return row_count


def command_extract(args: argparse.Namespace) -> None:
    site_config = load_site_config(args.config, args.site)
    log_path = site_config.text("ExtractLogFilePath") or site_config.text("UploadLogFilePath") or site_config.text("LogFilePath")
    logger = configure_logger(log_path)
    run_date = datetime.strptime(args.run_date, "%Y-%m-%d") if args.run_date else datetime.now()
    logger.info("Starting PlusOne extraction for site '%s'.", site_config.name)

    upload_path = Path(site_config.text("LocalUploadPath"))
    upload_path.mkdir(parents=True, exist_ok=True)
    for extraction in resolve_extractions(args.extraction):
        definition = EXTRACTION_DEFINITIONS[extraction]
        output_path = upload_path / definition["filename"](run_date)
        logger.info("Extracting '%s' to '%s'.", extraction, output_path)
        if args.what_if:
            logger.info("WhatIf mode: not writing '%s'.", output_path)
            continue
        row_count = export_sql_query_to_csv(site_config, definition, output_path)
        logger.info("Extracted '%s' with %s row(s) to '%s'.", extraction, row_count, output_path)
    logger.info("Completed PlusOne extraction for site '%s'.", site_config.name)


def upload_local_file(site_config: SiteConfig, local_path: Path, logger: logging.Logger, what_if: bool) -> None:
    if what_if:
        logger.info("WhatIf mode: not uploading '%s'.", local_path)
        return

    paramiko = import_optional("paramiko", "paramiko")
    remote_dir = site_config.text("RemoteUploadDirectory").rstrip("/")
    remote_path = f"{remote_dir}/{local_path.name}"
    client = paramiko.SSHClient()
    client.load_system_host_keys()
    client.set_missing_host_key_policy(PlusOneHostKeyPolicy(site_config.text("HostKeyFingerprint")))
    try:
        client.connect(
            hostname=site_config.text("SftpHost"),
            port=site_config.integer("SftpPort", 22),
            username=site_config.text("Username"),
            password=site_config.text("Password"),
            look_for_keys=False,
        )
        sftp = client.open_sftp()
        try:
            logger.info("Uploading '%s' to '%s'.", local_path, remote_path)
            sftp.put(str(local_path), remote_path)
        finally:
            sftp.close()
    finally:
        client.close()


def command_upload(args: argparse.Namespace) -> None:
    site_config = load_site_config(args.config, args.site)
    log_path = site_config.text("UploadLogFilePath") or site_config.text("LogFilePath")
    logger = configure_logger(log_path)
    logger.info("Starting PlusOne upload for site '%s'.", site_config.name)

    upload_path = Path(site_config.text("LocalUploadPath"))
    file_filter = site_config.text("RemoteUploadFilter", "*.csv")
    if not upload_path.exists():
        raise FileNotFoundError(f"Upload folder does not exist: {upload_path}")

    files = sorted(upload_path.glob(file_filter), key=lambda path: path.stat().st_mtime)
    if not files:
        logger.info("No upload files found in '%s' matching '%s'.", upload_path, file_filter)
        return

    for file_path in files:
        try:
            upload_local_file(site_config, file_path, logger, args.what_if)
            if not args.what_if:
                insert_message(site_config, "UPLOAD", file_path.name, "Upload succeeded.", 0)
                move_file_to_archive(file_path, site_config.text("UploadArchivePath"), "Success", logger)
        except Exception as exc:
            logger.exception("Upload failed for '%s'.", file_path)
            insert_message(site_config, "UPLOADERR", file_path.name, str(exc), 9)
            move_file_to_archive(file_path, site_config.text("UploadArchivePath"), "Failed", logger)

    logger.info("Completed PlusOne upload for site '%s'.", site_config.name)


def default_config_path() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / "PlusOneConfig.json"
    return Path(__file__).resolve().parent / "PlusOneConfig.json"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="PlusOne Python integration runner.")
    parser.add_argument("--config", type=Path, default=default_config_path(), help="Path to PlusOneConfig.json.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    download = subparsers.add_parser("download-import", help="Download inbound files and import invoice staging rows.")
    download.add_argument("--site", required=True, choices=["NZ", "AU"])
    download.add_argument("--skip-download", action="store_true", help="Process files already in LocalDownloadPath without SFTP.")
    download.add_argument("--what-if", action="store_true", help="Show intended actions without changing files or SQL.")
    download.set_defaults(func=command_download_import)

    extract = subparsers.add_parser("extract", help="Generate outbound CSV extracts.")
    extract.add_argument("--site", required=True, choices=["NZ", "AU"])
    extract.add_argument("--extraction", nargs="+", default=["All"], help="Extraction names: All, GLM, SUP, PUR.")
    extract.add_argument("--run-date", help="Run date in YYYY-MM-DD format. Defaults to today.")
    extract.add_argument("--what-if", action="store_true", help="Show intended output files without writing them.")
    extract.set_defaults(func=command_extract)

    upload = subparsers.add_parser("upload", help="Upload outbound files and archive the results.")
    upload.add_argument("--site", required=True, choices=["NZ", "AU"])
    upload.add_argument("--what-if", action="store_true", help="Show intended actions without changing files or SQL.")
    upload.set_defaults(func=command_upload)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        args.func(args)
        return 0
    except Exception as exc:
        logger = logging.getLogger("plusone")
        if logger.handlers:
            logger.error("Fatal error: %s", exc)
        else:
            print(f"Fatal error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
