# Google Drive Ingest Option

For field use, the probe should not contain a Google user OAuth refresh token.
Use a small server-side endpoint instead:

```text
kapa-probe.exe
  -> HTTPS POST json-base64
  -> Google Apps Script Web App or private relay
  -> Google Drive folder
```

## Probe Build

Build with `json-base64`:

```powershell
cd windows-agent\scripts
.\build-probe-exe.ps1 `
  -ProbePushUrl "https://script.google.com/macros/s/DEPLOYMENT_ID/exec" `
  -ProbePushToken "change-this" `
  -ProbePushFormat json-base64
```

The EXE sends JSON with:

- `filename`
- `content_type`
- `token`
- `captured_at`
- `host`
- `assessment`
- `bundle_base64`

## Apps Script Sketch

Create a Google Apps Script Web App that receives the JSON, validates `token`,
decodes `bundle_base64`, and writes the ZIP to a Drive folder.

```javascript
const FOLDER_ID = "DRIVE_FOLDER_ID";
const TOKEN = "change-this";

function doPost(e) {
  const payload = JSON.parse(e.postData.contents);
  if (payload.token !== TOKEN) {
    return ContentService
      .createTextOutput(JSON.stringify({ ok: false, error: "unauthorized" }))
      .setMimeType(ContentService.MimeType.JSON);
  }

  const bytes = Utilities.base64Decode(payload.bundle_base64);
  const blob = Utilities.newBlob(bytes, payload.content_type, payload.filename);
  const file = DriveApp.getFolderById(FOLDER_ID).createFile(blob);

  return ContentService
    .createTextOutput(JSON.stringify({ ok: true, file_id: file.getId(), name: file.getName() }))
    .setMimeType(ContentService.MimeType.JSON);
}
```

## When To Use This

Use Drive ingest when:

- there is no always-on private controller server
- the operator can access Google infrastructure
- the uploaded bundle size is small enough for the chosen web endpoint

Use the private ingest server when:

- bundles may be large
- network is private through Tailscale/VPN
- you need full control over retention and audit logs
