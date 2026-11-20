# Code signing (Azure Trusted Signing)

Signing `Nullpoint.exe` and the installer removes most SmartScreen warnings over time and lets the in-app updater
check that an update really comes from you. `build.bat` already signs both files **when it's set up**, and skips
signing (with a note) when it isn't. Nothing here creates accounts or costs money by itself.

## Costs and eligibility to check first

- Azure Trusted Signing is a paid monthly Azure service (the Basic tier was about US$10/month when this was
  written). Check the current price on the Azure pricing page before you start.
- Identity validation is required. Check who is eligible (organizations / individual developers, and which
  countries) on Microsoft's Trusted Signing documentation: it has changed over time.
- An Azure account needs a payment method.

## One-time setup

1. Create an Azure account at https://azure.microsoft.com (or sign in).
2. In the Azure portal, create a **Trusted Signing account** (resource). Note its **region endpoint**
   (e.g. `https://eus.codesigning.azure.net`) and the **account name**.
3. In that account, start **Identity validation** (Public Trust) and wait until it's approved.
4. Create a **Certificate profile** (type: Public Trust) linked to the validated identity. Note the **profile name**.
5. In **Access control (IAM)** of the account, give your own user the role
   **Trusted Signing Certificate Profile Signer**.
6. On this PC:
   - Install the Windows SDK signing tools (they include `signtool.exe`):
     `winget install Microsoft.WindowsSDK.10.0.22621`
   - Install the Trusted Signing client (the signing DLL):
     `winget install -e --id Microsoft.Azure.TrustedSigningClientTools`
   - Install the Azure CLI and sign in once: `winget install -e --id Microsoft.AzureCLI`, then `az login`.
7. Create `C:\Users\<you>\nullpoint-signing\metadata.json` (outside the repo, never commit it):

   ```json
   {
     "Endpoint": "https://eus.codesigning.azure.net",
     "CodeSigningAccountName": "<your account name>",
     "CertificateProfileName": "<your profile name>"
   }
   ```

8. Tell `build.bat` where things are (User environment variables, or in the terminal before building):

   ```powershell
   setx NULLPOINT_SIGN_DLIB "C:\Program Files\Microsoft\Azure Code Signing\Azure.CodeSigning.Dlib.dll"
   setx NULLPOINT_SIGN_METADATA "C:\Users\<you>\nullpoint-signing\metadata.json"
   ```

   (Check the real DLL path after installing the client tools; it can differ by version.)

## Every release

Run `build.bat`. It signs `dist\Nullpoint.exe`, builds the installer, signs it, and checks both with
`signtool verify /pa`. Then publish as usual (the SHA-256 checksums are for the signed files).

## Turn on signature checks in the updater

Once every release you publish is signed, set `REQUIRE_SIGNATURE = True` in `crosshair/updates.py` for the next
release. From then on the updater refuses installers that don't carry a valid Authenticode signature, in addition
to the SHA-256 check.
