# PlusOne Python Runner

This is a side-by-side Python replacement for the PlusOne PowerShell orchestration layer.

It leaves the Dynamics GP UI, SQL tables, views, and stored procedures unchanged.

## Setup

Install Python 3.11 or later, then install dependencies:

```powershell
python -m pip install -r requirements.txt
```

The SQL Server ODBC driver must also be installed on the machine running this app.
By default the app uses `ODBC Driver 17 for SQL Server`.

To use a different driver:

```powershell
$env:PLUSONE_ODBC_DRIVER = 'ODBC Driver 18 for SQL Server'
```

## Commands

Run from the `PlusOnePython` folder:

```powershell
python plusone.py download-import --site NZ
python plusone.py download-import --site AU

python plusone.py extract --site NZ --extraction All
python plusone.py extract --site AU --extraction GLM SUP PUR

python plusone.py upload --site NZ
python plusone.py upload --site AU
```

Run the production web UI:

```powershell
python plusone_web.py
```

Then open:

```text
http://127.0.0.1:8088/
```

Use a specific config or port:

```powershell
python plusone_web.py --config .\PlusOneConfig.json --port 8090
```

Build the web UI executable:

```powershell
.\Build-PlusOneWeb.ps1
```

The build output is:

```text
.\Compiled\PlusOneWeb.exe
```

Launch the compiled UI and open the browser:

```powershell
.\Compiled\Run-PlusOneWeb.ps1 -Site NZ
.\Compiled\Run-PlusOneWeb.ps1 -Site AU
```

Dynamics GP can launch `Run-PlusOneWeb.ps1` or `PlusOneWeb.exe` with:

```powershell
PlusOneWeb.exe --config PlusOneConfig.json --host 127.0.0.1 --port 8088 --site NZ --open-browser
```

The production UI requires `dbo.hmlPlusOneAppLock` in each site database used by the UI.
Deploy `table hmlPlusOneAppLock.sql` with the other PlusOne SQL objects.

Run extraction followed by upload for both sites:

```powershell
python run_extract_upload.py
```

Test the combined NZ/AU run without writing files, changing SQL, or uploading:

```powershell
python run_extract_upload.py --what-if
```

If Python is not installed, use the compiled runner instead:

```powershell
cd .\Compiled
.\Run-ExtractUpload.ps1 -WhatIf
```

Use a local/test config file:

```powershell
Copy-Item .\PlusOneConfig.local.template.json .\PlusOneConfig.local.json
python plusone.py --config .\PlusOneConfig.local.json download-import --site NZ --skip-download
python run_extract_upload.py --config .\PlusOneConfig.local.json --what-if
```

If `--config` is not supplied, the runner uses the existing script configuration at:

```text
..\Source Process Folders\PlusOneWorkspace\Scripts\PlusOneConfig.json
```

## Local Database Testing

For local import testing, place CSV files in the configured `LocalDownloadPath` and use:

```powershell
python plusone.py download-import --site NZ --skip-download
```

`--skip-download` avoids SFTP and processes local files only.

`--what-if` logs intended actions without changing files or SQL:

```powershell
python plusone.py extract --site NZ --extraction All --what-if
python plusone.py upload --site NZ --what-if
python plusone.py download-import --site NZ --skip-download --what-if
```

## Packaging

After testing, this can be packaged as a single executable with PyInstaller:

```powershell
python -m pip install pyinstaller
pyinstaller --onefile --name plusone plusone.py
```

Keep `PlusOneConfig.json` external to the executable so credentials and environment-specific paths are not compiled into the binary.
