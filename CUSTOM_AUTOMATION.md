# Custom Android update automation

This branch follows `rustdesk/rustdesk` `master`. The scheduled workflow merges
upstream every day at 03:17 UTC. A successful push to `custom-nav-controls`
starts the existing RustDesk build workflow, signs Android APKs, and publishes
a prerelease named `custom-<GitHub run id>`.

## Repository secrets

Set these repository secrets before enabling the workflows:

- `CUSTOM_REPO_TOKEN`: a fine-grained personal access token for this repository
  with **Contents: Read and write**. It is used only by the sync workflow. A
  personal token is needed because pushes made with `GITHUB_TOKEN` do not
  trigger the APK build workflow.
- `ANDROID_SIGNING_KEY`: Base64 form of the custom `.jks` keystore.
- `ANDROID_ALIAS`: keystore alias.
- `ANDROID_KEY_STORE_PASSWORD`: keystore password.
- `ANDROID_KEY_PASSWORD`: key password.

Create the Base64 value in PowerShell without writing it to a tracked file:

```powershell
[Convert]::ToBase64String([IO.File]::ReadAllBytes('C:\secure\release-keystore.jks'))
```

Never commit the keystore or `flutter/android/key.properties`.

## First run

1. Fork `rustdesk/rustdesk` on GitHub.
2. Set this clone's `origin` to your fork and push `custom-nav-controls`.
3. Add the secrets above in **Settings → Secrets and variables → Actions**.
4. Run **Build custom RustDesk APK** manually once. The signed APK is attached
   to the workflow's prerelease after a successful build.

An upstream merge conflict or build failure intentionally stops automation;
resolve it on `custom-nav-controls`, then push the fix.
