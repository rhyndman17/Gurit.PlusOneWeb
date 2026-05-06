from __future__ import annotations

import argparse
import getpass
import json
import logging
import re
import socket
import sys
import webbrowser
from datetime import date, datetime
from decimal import Decimal
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse
from urllib.parse import urlencode

import plusone


ROOT = Path(__file__).resolve().parent
WEB_ROOT = Path(getattr(sys, "_MEIPASS", ROOT)) / "PlusOneWebSample"
VALID_SITES = {"NZ", "AU"}
APP_LOCK_NAME = "PlusOneWeb"


def json_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def row_to_dict(cursor: Any, row: Any) -> dict[str, Any]:
    return {
        column[0]: json_value(row[index])
        for index, column in enumerate(cursor.description or [])
    }


def load_documents(config_path: Path, site: str) -> list[dict[str, Any]]:
    site_config = plusone.load_site_config(config_path, site)
    sql = """
SELECT
    InvoiceHeaderID,
    CONVERT(varchar(36), ImportBatchID) AS Batch,
    ? AS Site,
    FileName,
    SupplierID,
    VendorName,
    DocumentNo,
    DocumentDate,
    AccountingValueDate,
    po.PurchaseOrderNo,
    SubtotalExclGST,
    TotalGST,
    DocumentTotal,
    HeaderStatus,
    HeaderStatusDesc
FROM dbo.vw_hmlPlusOneInvoiceHeader
OUTER APPLY (
    SELECT
        CASE
            WHEN COUNT(DISTINCT NULLIF(RTRIM(l.PurchaseOrderNo), '')) = 0 THEN ''
            WHEN COUNT(DISTINCT NULLIF(RTRIM(l.PurchaseOrderNo), '')) = 1 THEN MAX(NULLIF(RTRIM(l.PurchaseOrderNo), ''))
            ELSE 'Multiple'
        END AS PurchaseOrderNo
    FROM dbo.hmlPlusOneInvoiceLine l
    WHERE l.InvoiceHeaderID = dbo.vw_hmlPlusOneInvoiceHeader.InvoiceHeaderID
) po
ORDER BY
    CASE WHEN HeaderStatus = 9 THEN 0 WHEN HeaderStatus = 0 THEN 1 WHEN HeaderStatus = 1 THEN 2 ELSE 3 END,
    DocumentDate DESC,
    DocumentNo
"""
    with plusone.sql_connection(site_config) as connection:
        cursor = connection.cursor()
        cursor.execute(sql, site)
        return [row_to_dict(cursor, row) for row in cursor.fetchall()]


def load_document_lines(config_path: Path, site: str, invoice_header_id: int) -> list[dict[str, Any]]:
    site_config = plusone.load_site_config(config_path, site)
    sql = """
SELECT
    InvoiceHeaderID,
    InvoiceLineID,
    LedgerCode,
    LineValueExclGST,
    LineDescription,
    LineStatus,
    LineStatusDesc
FROM dbo.vw_hmlPlusOneInvoiceLineDetail
WHERE InvoiceHeaderID = ?
ORDER BY SourceLineNo, InvoiceLineID
"""
    with plusone.sql_connection(site_config) as connection:
        cursor = connection.cursor()
        cursor.execute(sql, invoice_header_id)
        return [row_to_dict(cursor, row) for row in cursor.fetchall()]


def lock_table_exists(connection: Any) -> bool:
    cursor = connection.cursor()
    cursor.execute("SELECT OBJECT_ID('dbo.hmlPlusOneAppLock', 'U')")
    return cursor.fetchone()[0] is not None


def lock_row_payload(row: Any) -> dict[str, Any]:
    return {
        "lockId": str(row.LockID),
        "site": row.Site,
        "userName": row.UserName,
        "machineName": row.MachineName,
        "acquiredDateTime": json_value(row.AcquiredDateTime),
        "lastHeartbeatDateTime": json_value(row.LastHeartbeatDateTime),
    }


def acquire_app_lock(config_path: Path, site: str, user_name: str, lock_id: str | None = None) -> dict[str, Any]:
    site_config = plusone.load_site_config(config_path, site)
    machine_name = socket.gethostname()
    stale_minutes = site_config.integer("AppLockStaleMinutes", 480)
    requested_lock_id = lock_id or None

    with plusone.sql_connection(site_config) as connection:
        if not lock_table_exists(connection):
            raise RuntimeError("dbo.hmlPlusOneAppLock has not been deployed.")

        cursor = connection.cursor()
        try:
            cursor.execute(
                """
SELECT
    AppName,
    LockID,
    Site,
    UserName,
    MachineName,
    AcquiredDateTime,
    LastHeartbeatDateTime,
    CASE WHEN LastHeartbeatDateTime < DATEADD(minute, -?, GETDATE()) THEN 1 ELSE 0 END AS IsStale
FROM dbo.hmlPlusOneAppLock WITH (UPDLOCK, HOLDLOCK)
WHERE AppName = ?
""",
                stale_minutes,
                APP_LOCK_NAME,
            )
            row = cursor.fetchone()
            if row is None:
                cursor.execute(
                    """
INSERT INTO dbo.hmlPlusOneAppLock
    (AppName, LockID, Site, UserName, MachineName, AcquiredDateTime, LastHeartbeatDateTime)
VALUES
    (?, NEWID(), ?, ?, ?, GETDATE(), GETDATE())
""",
                    APP_LOCK_NAME,
                    site,
                    user_name,
                    machine_name,
                )
                cursor.execute(
                    """
SELECT LockID, Site, UserName, MachineName, AcquiredDateTime, LastHeartbeatDateTime
FROM dbo.hmlPlusOneAppLock
WHERE AppName = ?
""",
                    APP_LOCK_NAME,
                )
                new_row = cursor.fetchone()
                connection.commit()
                return {"ok": True, "locked": False, "lock": lock_row_payload(new_row)}

            existing = lock_row_payload(row)
            same_lock = requested_lock_id and str(row[1]).lower() == requested_lock_id.lower()
            is_stale = int(row[7]) == 1
            if same_lock or is_stale:
                cursor.execute(
                    """
UPDATE dbo.hmlPlusOneAppLock
SET
    LockID = CASE WHEN ? IS NULL THEN NEWID() ELSE CONVERT(uniqueidentifier, ?) END,
    Site = ?,
    UserName = ?,
    MachineName = ?,
    AcquiredDateTime = CASE WHEN ? IS NULL THEN GETDATE() ELSE AcquiredDateTime END,
    LastHeartbeatDateTime = GETDATE()
WHERE AppName = ?
""",
                    requested_lock_id,
                    requested_lock_id,
                    site,
                    user_name,
                    machine_name,
                    requested_lock_id,
                    APP_LOCK_NAME,
                )
                cursor.execute(
                    """
SELECT LockID, Site, UserName, MachineName, AcquiredDateTime, LastHeartbeatDateTime
FROM dbo.hmlPlusOneAppLock
WHERE AppName = ?
""",
                    APP_LOCK_NAME,
                )
                updated_row = cursor.fetchone()
                connection.commit()
                return {"ok": True, "locked": False, "lock": lock_row_payload(updated_row)}

            connection.commit()
            return {"ok": True, "locked": True, "lock": existing}
        except Exception:
            connection.rollback()
            raise


def heartbeat_app_lock(config_path: Path, site: str, lock_id: str) -> dict[str, Any]:
    site_config = plusone.load_site_config(config_path, site)
    with plusone.sql_connection(site_config) as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
UPDATE dbo.hmlPlusOneAppLock
SET LastHeartbeatDateTime = GETDATE()
WHERE AppName = ? AND LockID = CONVERT(uniqueidentifier, ?)
""",
            APP_LOCK_NAME,
            lock_id,
        )
        connection.commit()
        return {"ok": cursor.rowcount == 1}


def verify_app_lock(config_path: Path, site: str, lock_id: str) -> bool:
    site_config = plusone.load_site_config(config_path, site)
    with plusone.sql_connection(site_config) as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
SELECT 1
FROM dbo.hmlPlusOneAppLock
WHERE AppName = ? AND LockID = CONVERT(uniqueidentifier, ?)
""",
            APP_LOCK_NAME,
            lock_id,
        )
        return cursor.fetchone() is not None


def release_app_lock(config_path: Path, site: str, lock_id: str) -> dict[str, Any]:
    site_config = plusone.load_site_config(config_path, site)
    with plusone.sql_connection(site_config) as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
DELETE dbo.hmlPlusOneAppLock
WHERE AppName = ? AND LockID = CONVERT(uniqueidentifier, ?)
""",
            APP_LOCK_NAME,
            lock_id,
        )
        connection.commit()
        return {"ok": True, "released": cursor.rowcount == 1}


class ListHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.records: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(self.format(record))


def run_download_import(config_path: Path, site: str) -> dict[str, Any]:
    site_config = plusone.load_site_config(config_path, site)
    logger = plusone.configure_logger(site_config.text("LogFilePath"))
    capture = ListHandler()
    capture.setFormatter(logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s", "%Y-%m-%d %H:%M:%S"))
    logger.addHandler(capture)

    try:
        logger.info("Starting PlusOne download/import for site '%s'.", site_config.name)
        plusone.download_remote_files(site_config, logger, what_if=False)

        download_path = Path(site_config.text("LocalDownloadPath"))
        download_path.mkdir(parents=True, exist_ok=True)
        files = sorted(
            download_path.glob(site_config.text("RemoteDownloadFilter", "*.csv")),
            key=lambda path: path.stat().st_mtime,
        )
        if not files:
            logger.info("No files found in '%s' matching '%s'.", download_path, site_config.text("RemoteDownloadFilter", "*.csv"))
        else:
            for file_path in files:
                plusone.process_downloaded_file(file_path, site_config, logger)
            logger.info("Completed PlusOne download/import for site '%s'.", site_config.name)
        return {"ok": True, "log": capture.records}
    except Exception as exc:
        logger.exception("Download/import failed for site '%s'.", site_config.name)
        return {"ok": False, "error": str(exc), "log": capture.records}
    finally:
        logger.removeHandler(capture)


class PlusOneWebHandler(SimpleHTTPRequestHandler):
    config_path: Path
    launch_user: str

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(WEB_ROOT), **kwargs)

    def log_message(self, format: str, *args: Any) -> None:
        print(f"[web] {self.address_string()} - {format % args}", file=sys.stderr)

    def send_json(self, payload: Any, status: HTTPStatus = HTTPStatus.OK) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def send_error_json(self, status: HTTPStatus, message: str) -> None:
        self.send_json({"ok": False, "error": message}, status)

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()

    def site_from_query(self, query: dict[str, list[str]]) -> str:
        site = (query.get("site", ["NZ"])[0] or "NZ").upper()
        if site not in VALID_SITES:
            raise ValueError("Site must be NZ or AU.")
        return site

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)

        if parsed.path == "/api/documents":
            try:
                site = self.site_from_query(query)
                self.send_json({"ok": True, "documents": load_documents(self.config_path, site)})
            except Exception as exc:
                self.send_error_json(HTTPStatus.INTERNAL_SERVER_ERROR, str(exc))
            return

        match = re.fullmatch(r"/api/documents/(\d+)/lines", parsed.path)
        if match:
            try:
                site = self.site_from_query(query)
                invoice_header_id = int(match.group(1))
                self.send_json({"ok": True, "lines": load_document_lines(self.config_path, site, invoice_header_id)})
            except Exception as exc:
                self.send_error_json(HTTPStatus.INTERNAL_SERVER_ERROR, str(exc))
            return

        if parsed.path == "/":
            self.path = "/index.html"
        super().do_GET()

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path not in {"/api/download", "/api/lock/acquire", "/api/lock/heartbeat", "/api/lock/release"}:
            self.send_error_json(HTTPStatus.NOT_FOUND, "Unknown endpoint.")
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length).decode("utf-8") if length else "{}"
            payload = json.loads(body)
            site = str(payload.get("site", "NZ")).upper()
            if site not in VALID_SITES:
                raise ValueError("Site must be NZ or AU.")

            if parsed.path == "/api/lock/acquire":
                result = acquire_app_lock(
                    self.config_path,
                    site,
                    str(payload.get("userName") or self.launch_user),
                    payload.get("lockId"),
                )
                self.send_json(result)
                return

            if parsed.path == "/api/lock/heartbeat":
                result = heartbeat_app_lock(self.config_path, site, str(payload.get("lockId") or ""))
                self.send_json(result, HTTPStatus.OK if result.get("ok") else HTTPStatus.CONFLICT)
                return

            if parsed.path == "/api/lock/release":
                result = release_app_lock(self.config_path, site, str(payload.get("lockId") or ""))
                self.send_json(result)
                return

            if not verify_app_lock(self.config_path, site, str(payload.get("lockId") or "")):
                self.send_error_json(HTTPStatus.CONFLICT, "The PlusOne application lock is not held by this session.")
                return

            result = run_download_import(self.config_path, site)
            self.send_json(result, HTTPStatus.OK if result.get("ok") else HTTPStatus.INTERNAL_SERVER_ERROR)
        except Exception as exc:
            self.send_error_json(HTTPStatus.BAD_REQUEST, str(exc))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="PlusOne production web UI.")
    parser.add_argument("--config", type=Path, default=plusone.default_config_path(), help="Path to PlusOneConfig.json.")
    parser.add_argument("--host", default="127.0.0.1", help="Host/interface to bind.")
    parser.add_argument("--port", type=int, default=8088, help="Port to listen on.")
    parser.add_argument("--site", choices=["NZ", "AU"], default="NZ", help="Initial site to show when opening the browser.")
    parser.add_argument("--user", default=getpass.getuser(), help="User name to record in the application lock.")
    parser.add_argument("--open-browser", action="store_true", help="Open the PlusOne UI in the default browser after starting.")
    return parser


def is_server_running(host: str, port: int) -> bool:
    connect_host = "127.0.0.1" if host in ("0.0.0.0", "") else host
    try:
        with socket.create_connection((connect_host, port), timeout=1):
            return True
    except OSError:
        return False


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    PlusOneWebHandler.config_path = args.config
    PlusOneWebHandler.launch_user = args.user
    browser_host = "127.0.0.1" if args.host in ("0.0.0.0", "") else args.host
    url = f"http://{browser_host}:{args.port}/?{urlencode({'site': args.site})}"
    if is_server_running(args.host, args.port):
        print(f"PlusOne web UI is already running at {url}")
        if args.open_browser:
            webbrowser.open(url)
        return 0

    try:
        server = ThreadingHTTPServer((args.host, args.port), PlusOneWebHandler)
    except OSError as exc:
        if args.open_browser:
            webbrowser.open(url)
            return 0
        print(f"Unable to start PlusOne web UI on {url}: {exc}", file=sys.stderr)
        return 1

    print(f"PlusOne web UI running at {url}")
    print(f"Using config: {args.config}")
    if args.open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping PlusOne web UI.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
