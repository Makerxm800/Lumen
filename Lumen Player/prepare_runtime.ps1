$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$runtime = Join-Path $here 'runtime'
$temp = Join-Path $env:TEMP ("lumen-mpv-" + [guid]::NewGuid().ToString('N'))
$extract = Join-Path $temp 'extract'
New-Item -ItemType Directory -Path $extract -Force | Out-Null

try {
    $sevenZipPath = $null
    $sevenZip = Get-Command '7z.exe' -ErrorAction SilentlyContinue
    if ($sevenZip) { $sevenZipPath = $sevenZip.Source }
    if (-not $sevenZipPath) {
        $candidate = Join-Path $env:ProgramFiles '7-Zip\7z.exe'
        if (Test-Path $candidate) { $sevenZipPath = $candidate }
    }
    if (-not $sevenZipPath) {
        throw '7-Zip is required to extract the portable mpv archive. Install 7-Zip, then run this script again.'
    }

    Write-Host 'Looking up the latest baseline x64 mpv build from shinchiro/mpv-winbuild-cmake...'
    $release = Invoke-RestMethod -Uri 'https://api.github.com/repos/shinchiro/mpv-winbuild-cmake/releases/latest'
    $asset = $release.assets | Where-Object { $_.name -match '^mpv-x86_64-[0-9].*\.7z$' -and $_.name -notmatch '-v3-' } | Select-Object -First 1
    if (-not $asset) { throw 'No baseline x64 mpv archive was found in the latest release.' }

    $archive = Join-Path $temp $asset.name
    Write-Host "Downloading $($asset.name) ($([math]::Round($asset.size / 1MB)) MB)..."
    Invoke-WebRequest -Uri $asset.browser_download_url -OutFile $archive
    & $sevenZipPath x $archive "-o$extract" -y | Out-Host
    if ($LASTEXITCODE -ne 0) { throw '7-Zip could not extract the mpv runtime archive.' }

    $mpv = Get-ChildItem -Path $extract -Filter 'mpv.exe' -File -Recurse | Select-Object -First 1
    if (-not $mpv) { throw 'The extracted archive did not contain mpv.exe.' }
    $stage = Join-Path $temp 'runtime'
    New-Item -ItemType Directory -Path $stage | Out-Null
    Copy-Item -Path (Join-Path $mpv.Directory.FullName '*') -Destination $stage -Recurse -Force
    if (-not (Test-Path (Join-Path $stage 'mpv.exe'))) { throw 'Could not stage mpv.exe and its adjacent runtime files.' }

    if (Test-Path $runtime) { Remove-Item -Path $runtime -Recurse -Force }
    Move-Item -Path $stage -Destination $runtime
    Write-Host "mpv runtime prepared in $runtime"
    Write-Host 'The complete archive contents (including any bundled notices/licenses) are retained.'
}
finally {
    if (Test-Path $temp) { Remove-Item -Path $temp -Recurse -Force }
}
