# Build the MIR MEDIA LABS Android app.
#   -Bump                 increment versionCode / minor versionName first
#   -Publish -Notes ".."  publish APK + version.json to the Media Lab's OWN update server
#                         (C:\AiMir-Tools\MirMediaLabs\updates  ->  http://<pc>:5400/updates/)
#   -Install              adb install + launch on a connected phone / emulator
#   -Release              signed, R8-shrunk release APK (MirCorp key from app\keystore.properties) for GitHub
param([switch]$Install, [switch]$Publish, [switch]$Bump, [switch]$Release, [string]$Notes = "")
$env:JAVA_HOME = "C:\Program Files\Java\jdk-21.0.10"
$env:ANDROID_HOME = "C:\AiMir-Tools\android-sdk"
$proj = Join-Path $PSScriptRoot "app"
$gradle = Join-Path $proj "app\build.gradle"
$updateDir = Join-Path $PSScriptRoot "updates"

if ($Bump) {
    $g = Get-Content $gradle -Raw
    $code = [int]([regex]::Match($g, 'versionCode (\d+)').Groups[1].Value) + 1
    $name = [regex]::Match($g, 'versionName "(\d+)\.(\d+)"')
    $newName = "$($name.Groups[1].Value).$([int]$name.Groups[2].Value + 1)"
    $g = $g -replace 'versionCode \d+', "versionCode $code" -replace 'versionName "[^"]+"', "versionName `"$newName`""
    Set-Content -Path $gradle -Value $g -NoNewline -Encoding ascii
    "bumped to v$newName ($code)"
}

$task = if ($Release) { "assembleRelease" } else { "assembleDebug" }
$apk = if ($Release) { Join-Path $proj "app\build\outputs\apk\release\app-release.apk" } else { Join-Path $proj "app\build\outputs\apk\debug\app-debug.apk" }
Remove-Item $apk -ErrorAction SilentlyContinue   # a failed build must never publish the previous APK
& cmd /c "cd /d `"$proj`" && `"$proj\gradlew.bat`" $task --console=plain 2>&1" | Select-String -Pattern "error|warning: |BUILD|\.java:\d+" | ForEach-Object { $_.Line }
if (-not (Test-Path $apk)) { "BUILD FAILED - no APK"; exit 1 }
Copy-Item $apk (Join-Path $PSScriptRoot $(if ($Release) { "MirMediaLabs-release.apk" } else { "MirMediaLabs.apk" })) -Force

if ($Publish) {
    $g = Get-Content $gradle -Raw
    $code = [int]([regex]::Match($g, 'versionCode (\d+)').Groups[1].Value)
    $name = [regex]::Match($g, 'versionName "([^"]+)"').Groups[1].Value
    New-Item -ItemType Directory -Force $updateDir | Out-Null
    Copy-Item $apk (Join-Path $updateDir "MirMediaLabs.apk") -Force
    $sha = (Get-FileHash $apk -Algorithm SHA256).Hash.ToLower()
    $json = [ordered]@{ versionCode = $code; versionName = $name; notes = $Notes; apk = "MirMediaLabs.apk"; sha256 = $sha;
                        published = (Get-Date).ToString("s") } | ConvertTo-Json
    [IO.File]::WriteAllText((Join-Path $updateDir "version.json"), $json)
    "published v$name ($code) -> $updateDir"
}

if ($Install) {
    $adb = "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe"
    & $adb install -r $apk
    & $adb shell am start -n com.mirmedialabs.app/.MainActivity | Out-Null
}
