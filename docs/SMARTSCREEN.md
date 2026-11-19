# "Windows protected your PC" (SmartScreen)

Nullpoint is a small open-source app that isn't code-signed yet. Windows SmartScreen shows a blue
**"Windows protected your PC"** box for downloads that are new and unsigned. It doesn't mean a virus was
found: it means Windows hasn't seen this file often enough to trust it.

## Running it anyway (safely)

1. Download `Nullpoint.exe` or `Nullpoint-Setup-x.y.z.exe` **only** from the official releases page:
   https://github.com/yensobased1/nullpoint/releases
2. Check the file (next section). If the checksum doesn't match, delete the file and don't run it.
3. Run it. When SmartScreen appears, click **More info**, check that the app name is the one you downloaded,
   then click **Run anyway**.

## Verify the download (SHA-256)

Every release lists the SHA-256 checksum of each file in its release notes. In PowerShell:

```powershell
Get-FileHash .\Nullpoint-Setup-2.1.0.exe -Algorithm SHA256
```

The `Hash` it prints must match the one in the release notes exactly. Any difference = a different file.

## Why isn't it signed? (options for later)

| Option | Cost (approx.) | Trade-offs |
|---|---|---|
| Stay unsigned + publish checksums | free | SmartScreen warning until enough people have downloaded it. |
| OV code-signing certificate | ~$200-400 / year | Shows the publisher name; the warning still appears until the certificate builds reputation. Needs a hardware token or cloud HSM now. |
| EV code-signing certificate | ~$300-600 / year | Removes the SmartScreen warning almost immediately; requires a registered business. |
| Azure Trusted Signing | ~$10 / month | Cheapest real signing; needs identity verification and (for now) a business or long-standing individual account in supported countries. |
| winget / Microsoft Store | free | Store apps are signed by Microsoft; winget installs still run the same unsigned installer. |
