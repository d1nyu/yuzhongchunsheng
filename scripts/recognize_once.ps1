param(
    [Parameter(Mandatory = $true)]
    [string]$Culture,
    [int]$TimeoutSeconds = 20,
    [Parameter(Mandatory = $true)]
    [string]$OutputFile
)

$ErrorActionPreference = "Stop"
$payload = @{
    ok = $false
    text = ""
    confidence = 0.0
    error = ""
}
$engine = $null

try {
    Add-Type -AssemblyName System.Speech
    $recognizers = [System.Speech.Recognition.SpeechRecognitionEngine]::InstalledRecognizers()
    $matched = $recognizers | Where-Object { $_.Culture.Name -eq $Culture } | Select-Object -First 1
    if ($null -eq $matched) {
        throw "Speech recognizer not installed for culture: $Culture"
    }

    $engine = [System.Speech.Recognition.SpeechRecognitionEngine]::new(
        [System.Speech.Recognition.RecognizerInfo]$matched
    )
    $grammar = New-Object System.Speech.Recognition.DictationGrammar
    [void]$engine.LoadGrammar($grammar)
    $engine.SetInputToDefaultAudioDevice()
    $timeout = [TimeSpan]::FromSeconds($TimeoutSeconds)
    $result = $engine.Recognize($timeout)

    if ($null -eq $result) {
        $payload.ok = $true
        $payload.text = ""
        $payload.error = "NO_SPEECH"
    }
    else {
        $payload.ok = $true
        $payload.text = $result.Text
        $payload.confidence = [double]$result.Confidence
    }
}
catch {
    $payload.error = $_.Exception.Message
}
finally {
    if ($null -ne $engine) {
        try { $engine.Dispose() } catch { }
    }
    $json = $payload | ConvertTo-Json -Depth 5 -Compress
    $utf8 = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($OutputFile, $json, $utf8)
}

