# Build the MIR MEDIA LABS Android app.
#   -Bump                  increment versionCode / minor versionName first
#   -Release               signed, R8-shrunk release APK (MirCorp key from app\keystore.properties)
#   -Publish -Notes ".."   publish to the Media Lab's OWN update server (updates\ -> http://<pc>:5400/updates/):
#                          android.json + .sig (Ed25519, read by app 2.0+) and version.json (pre-2.0 apps)
#   -GitHub [-Tag vX.Y.Z]  (implies -Release) upload MirMediaLabs.apk + signed android.json to a GitHub release
#                          (default: the current latest release) - the official update channel of every app
#   -Install               adb install + launch on a connected phone / emulator
#   -Play                  Google Play edition: signed release App Bundle -> MirMediaLabs-play.aab for Play Console
#                          (never sent to GitHub / the lab). Same code + version as the direct app.
# Manifests are signed with installer\signing\update_ed25519.key (same key as the PC edition - never commit it).
param([switch]$Play, [switch]$Install, [switch]$Publish, [switch]$Bump, [switch]$Release, [switch]$GitHub, [string]$Tag = "", [string]$Notes = "")
$env:JAVA_HOME = "C:\Program Files\Java\jdk-21.0.10"
$env:ANDROID_HOME = "C:\AiMir-Tools\android-sdk"
if ($GitHub) { $Release = $true }
$proj = Join-Path $PSScriptRoot "app"
$gradle = Join-Path $proj "app\build.gradle"
$updateDir = Join-Path $PSScriptRoot "updates"
$tool = Join-Path $PSScriptRoot "installer\build_tool.py"
$py = Join-Path $PSScriptRoot "installer\build\nvenv\Scripts\python.exe"
if (-not (Test-Path $py)) { $py = "python" }
$gh = "C:\AiMir-Tools\gh\bin\gh.exe"
$repo = "MirCorp85/MirMediaLabs"

if ($Bump) {
    $g = Get-Content $gradle -Raw
    $code = [int]([regex]::Match($g, 'versionCode (\d+)').Groups[1].Value) + 1
    $name = [regex]::Match($g, 'versionName "(\d+)\.(\d+)"')
    $newName = "$($name.Groups[1].Value).$([int]$name.Groups[2].Value + 1)"
    $g = $g -replace 'versionCode \d+', "versionCode $code" -replace 'versionName "[^"]+"', "versionName `"$newName`""
    Set-Content -Path $gradle -Value $g -NoNewline -Encoding ascii
    "bumped to v$newName ($code)"
}

if ($Play) {
    $aab = Join-Path $proj "app\build\outputs\bundle\playRelease\app-play-release.aab"
    Remove-Item $aab -ErrorAction SilentlyContinue
    & cmd /c "cd /d `"$proj`" && `"$proj\gradlew.bat`" bundlePlayRelease --console=plain 2>&1" | Select-String -Pattern "error|warning: |BUILD|\.java:\d+" | ForEach-Object { $_.Line }
    if (-not (Test-Path $aab)) { "BUILD FAILED - no AAB"; exit 1 }
    Copy-Item $aab (Join-Path $PSScriptRoot "MirMediaLabs-play.aab") -Force
    "Play bundle ready: $(Join-Path $PSScriptRoot 'MirMediaLabs-play.aab')"
    exit 0
}
$task = if ($Release) { "assembleDirectRelease" } else { "assembleDirectDebug" }
$apk = if ($Release) { Join-Path $proj "app\build\outputs\apk\direct\release\app-direct-release.apk" } else { Join-Path $proj "app\build\outputs\apk\direct\debug\app-direct-debug.apk" }
Remove-Item $apk -ErrorAction SilentlyContinue   # a failed build must never publish the previous APK
& cmd /c "cd /d `"$proj`" && `"$proj\gradlew.bat`" $task --console=plain 2>&1" | Select-String -Pattern "error|warning: |BUILD|\.java:\d+" | ForEach-Object { $_.Line }
if (-not (Test-Path $apk)) { "BUILD FAILED - no APK"; exit 1 }
Copy-Item $apk (Join-Path $PSScriptRoot $(if ($Release) { "MirMediaLabs-release.apk" } else { "MirMediaLabs.apk" })) -Force

$g = Get-Content $gradle -Raw
$code = [int]([regex]::Match($g, 'versionCode (\d+)').Groups[1].Value)
$name = [regex]::Match($g, 'versionName "([^"]+)"').Groups[1].Value

function Get-Cert($file) {
    # SHA-256 of the APK signing certificate: the app only accepts updates signed by the same key
    $out = & "$env:ANDROID_HOME\build-tools\34.0.0\apksigner.bat" verify --print-certs $file 2>&1 | Out-String
    $m = [regex]::Match($out, 'Signer #1 certificate SHA-256 digest: ([0-9a-fA-F]+)')
    if (-not $m.Success) { throw "apksigner could not read the signing certificate:`n$out" }
    $m.Groups[1].Value.ToLower()
}

if ($Publish -or $GitHub) {
    $cert = Get-Cert $apk
    $env:MML_NOTES = $Notes
    "signer certificate sha256 $cert"
}

if ($Publish) {
    New-Item -ItemType Directory -Force $updateDir | Out-Null
    Copy-Item $apk (Join-Path $updateDir "MirMediaLabs.apk") -Force
    & $py $tool android $apk $code $name $cert "-" $updateDir
    if ($LASTEXITCODE -ne 0) { "SIGNING FAILED"; exit 1 }
    $sha = (Get-FileHash $apk -Algorithm SHA256).Hash.ToLower()
    $json = [ordered]@{ versionCode = $code; versionName = $name; notes = $Notes; apk = "MirMediaLabs.apk"; sha256 = $sha;
                        published = (Get-Date).ToString("s") } | ConvertTo-Json
    [IO.File]::WriteAllText((Join-Path $updateDir "version.json"), $json)
    "published v$name ($code) -> $updateDir"
}

if ($GitHub) {
    if (-not $Tag) { $Tag = (& $gh release view -R $repo --json tagName -q .tagName) }
    if (-not $Tag) { "no GitHub release found - pass -Tag"; exit 1 }
    $stage = Join-Path $env:TEMP "mml_gh_android"
    Remove-Item $stage -Recurse -Force -ErrorAction SilentlyContinue
    New-Item -ItemType Directory -Force $stage | Out-Null
    Copy-Item $apk (Join-Path $stage "MirMediaLabs.apk")
    & $py $tool android $apk $code $name $cert $Tag $stage
    if ($LASTEXITCODE -ne 0) { "SIGNING FAILED"; exit 1 }
    $exists = $true
    & $gh release view $Tag -R $repo --json tagName 2>$null | Out-Null
    if ($LASTEXITCODE -ne 0) { $exists = $false }
    if (-not $exists) {
        & $gh release create $Tag -R $repo --title "MIR MEDIA LABS $Tag" --notes $(if ($Notes) { $Notes } else { "Android app v$name" })
        if ($LASTEXITCODE -ne 0) { "RELEASE CREATE FAILED"; exit 1 }
    }
    # keep SHA256SUMS.txt in step with the new APK (other lines untouched)
    $sums = Join-Path $stage "SHA256SUMS.txt"
    & $gh release download $Tag -R $repo -p "SHA256SUMS.txt" -D $stage --clobber 2>$null
    $apkSha = (Get-FileHash $apk -Algorithm SHA256).Hash.ToLower()
    $lines = @()
    if (Test-Path $sums) { $lines = @(Get-Content $sums | Where-Object { $_ -notmatch 'MirMediaLabs\.apk\s*$' -and $_.Trim() }) }   # @(): a single line must stay a list
    $lines += "$apkSha  MirMediaLabs.apk"
    [IO.File]::WriteAllText($sums, (($lines -join "`n") + "`n"))
    & $gh release upload $Tag -R $repo --clobber (Join-Path $stage "MirMediaLabs.apk") (Join-Path $stage "android.json") (Join-Path $stage "android.json.sig") $sums
    if ($LASTEXITCODE -ne 0) { "UPLOAD FAILED"; exit 1 }
    "GitHub release $Tag now carries v$name ($code)"
}

if ($Install) {
    $adb = "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe"
    & $adb install -r $apk
    & $adb shell am start -n com.mirmedialabs.app/.MainActivity | Out-Null
}
