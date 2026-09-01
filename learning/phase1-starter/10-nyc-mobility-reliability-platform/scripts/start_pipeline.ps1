[CmdletBinding()]
param(
    [Parameter()]
    [ValidateNotNullOrEmpty()]
    [string] $StackName = 'nyc-mobility-reliability-dev',

    [Parameter()]
    [ValidateNotNullOrEmpty()]
    [string] $Region = 'us-east-1',

    [Parameter()]
    [ValidateSet('monthly', 'backfill', 'reprocess')]
    [string] $Mode = 'monthly',

    [Parameter()]
    [ValidateRange(2019, 9999)]
    [Nullable[int]] $Year,

    [Parameter()]
    [ValidateRange(1, 12)]
    [Nullable[int]] $Month,

    [Parameter()]
    [string] $RunId = '',

    [Parameter()]
    [string] $Profile = ''
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Invoke-AwsCli {
    param([Parameter(Mandatory)][string[]] $Arguments)

    $allArguments = @($Arguments) + @('--region', $Region)
    if ($Profile) {
        $allArguments += @('--profile', $Profile)
    }
    $output = & aws @allArguments
    if ($LASTEXITCODE -ne 0) {
        throw "AWS CLI failed with exit code ${LASTEXITCODE}: aws $($allArguments -join ' ')"
    }
    return ($output -join [Environment]::NewLine)
}

if (-not (Get-Command 'aws' -ErrorAction SilentlyContinue)) {
    throw "Required command 'aws' was not found on PATH."
}
$hasYear = $PSBoundParameters.ContainsKey('Year')
$hasMonth = $PSBoundParameters.ContainsKey('Month')
if ($hasYear -xor $hasMonth) {
    throw 'Year and Month must be supplied together.'
}

$functionName = (Invoke-AwsCli -Arguments @(
        'cloudformation', 'describe-stacks', '--stack-name', $StackName,
        '--query', "Stacks[0].Outputs[?OutputKey=='LauncherFunctionName'].OutputValue | [0]",
        '--output', 'text'
    )).Trim()
if (-not $functionName -or $functionName -eq 'None') {
    throw "Stack '$StackName' does not expose LauncherFunctionName."
}

$payloadObject = [ordered]@{ mode = $Mode }
if ($hasYear) {
    $payloadObject.year = [int] $Year
    $payloadObject.month = [int] $Month
}
if ($RunId) {
    $payloadObject.run_id = $RunId
}
$payload = $payloadObject | ConvertTo-Json -Compress
$responseFile = [IO.Path]::GetTempFileName()

try {
    Write-Host "Invoking $functionName with payload $payload"
    $metadataJson = Invoke-AwsCli -Arguments @(
        'lambda', 'invoke', '--function-name', $functionName,
        '--cli-binary-format', 'raw-in-base64-out',
        '--payload', $payload, $responseFile
    )
    $metadata = $metadataJson | ConvertFrom-Json
    $responseBody = Get-Content -LiteralPath $responseFile -Raw

    if ($metadata.PSObject.Properties['FunctionError'] -and $metadata.FunctionError) {
        throw "Launcher Lambda returned $($metadata.FunctionError): $responseBody"
    }
    Write-Output $responseBody
}
finally {
    Remove-Item -LiteralPath $responseFile -Force -ErrorAction SilentlyContinue
}
