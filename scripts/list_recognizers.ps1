param(
    [Parameter(Mandatory = $true)]
    [string]$OutputFile
)

$ErrorActionPreference = "Stop"
$payload = @{
    ok = $false
    recognizers = @()
    error = ""
}

try {
    Add-Type -AssemblyName System.Speech
    $items = @()
    foreach ($recognizer in [System.Speech.Recognition.SpeechRecognitionEngine]::InstalledRecognizers()) {
        $items += @{
            culture = $recognizer.Culture.Name
            name = $recognizer.Name
            description = $recognizer.Description
        }
    }
    $payload.ok = $true
    $payload.recognizers = $items
}
catch {
    $payload.error = $_.Exception.Message
}

$json = $payload | ConvertTo-Json -Depth 5 -Compress
$utf8 = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($OutputFile, $json, $utf8)

