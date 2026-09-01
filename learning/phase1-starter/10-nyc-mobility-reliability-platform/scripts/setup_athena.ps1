[CmdletBinding()]
param(
    [Parameter()]
    [ValidateNotNullOrEmpty()]
    [string] $StackName = 'nyc-mobility-reliability-dev',

    [Parameter()]
    [ValidateNotNullOrEmpty()]
    [string] $Region = 'us-east-1',

    [Parameter()]
    [ValidateRange(1, 60)]
    [int] $PollSeconds = 2,

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

function Get-StackOutput {
    param([Parameter(Mandatory)][string] $OutputKey)

    $value = (Invoke-AwsCli -Arguments @(
            'cloudformation', 'describe-stacks', '--stack-name', $StackName,
            '--query', "Stacks[0].Outputs[?OutputKey=='$OutputKey'].OutputValue | [0]",
            '--output', 'text'
        )).Trim()
    if (-not $value -or $value -eq 'None') {
        throw "Stack '$StackName' does not expose output '$OutputKey'."
    }
    return $value
}

if (-not (Get-Command 'aws' -ErrorAction SilentlyContinue)) {
    throw "Required command 'aws' was not found on PATH."
}

$projectRoot = Split-Path -Parent $PSScriptRoot
$ddlPath = Join-Path $projectRoot 'sql\ddl\create_external_tables.sql'
if (-not (Test-Path -LiteralPath $ddlPath -PathType Leaf)) {
    throw "Athena DDL was not found: $ddlPath"
}

$databaseName = Get-StackOutput -OutputKey 'GlueDatabaseName'
$dataBucket = Get-StackOutput -OutputKey 'DataBucketName'
$workGroup = Get-StackOutput -OutputKey 'AthenaWorkGroupName'

$quotedDatabaseName = '`' + $databaseName.Replace('`', '``') + '`'
$sql = Get-Content -LiteralPath $ddlPath -Raw
$sql = $sql.Replace('{{DATABASE_NAME}}', $quotedDatabaseName)
$sql = $sql.Replace('{{DATA_BUCKET}}', $dataBucket)
if ($sql -match '\{\{[^}]+\}\}') {
    throw 'The Athena DDL still contains an unreplaced template token.'
}

# Strip full-line SQL comments before splitting this repository's semicolon-delimited DDL.
$sql = [regex]::Replace($sql, '(?m)^\s*--.*(?:\r?\n|$)', '')
$statements = @(
    $sql -split ';' |
        ForEach-Object { $_.Trim() } |
        Where-Object { $_ }
)
if ($statements.Count -eq 0) {
    throw "No SQL statements were found in $ddlPath."
}

for ($index = 0; $index -lt $statements.Count; $index++) {
    $statementNumber = $index + 1
    $statement = $statements[$index]
    Write-Host "[$statementNumber/$($statements.Count)] Starting Athena statement."
    $queryExecutionId = (Invoke-AwsCli -Arguments @(
            'athena', 'start-query-execution',
            '--query-string', $statement,
            '--work-group', $workGroup,
            '--query', 'QueryExecutionId', '--output', 'text'
        )).Trim()
    if (-not $queryExecutionId -or $queryExecutionId -eq 'None') {
        throw "Athena did not return a query execution ID for statement $statementNumber."
    }

    while ($true) {
        $statusJson = Invoke-AwsCli -Arguments @(
            'athena', 'get-query-execution',
            '--query-execution-id', $queryExecutionId,
            '--query', 'QueryExecution.Status', '--output', 'json'
        )
        $status = $statusJson | ConvertFrom-Json
        switch ($status.State) {
            'SUCCEEDED' {
                Write-Host "[$statementNumber/$($statements.Count)] Succeeded ($queryExecutionId)."
                break
            }
            'FAILED' {
                throw "Athena statement $statementNumber failed ($queryExecutionId): $($status.StateChangeReason)"
            }
            'CANCELLED' {
                throw "Athena statement $statementNumber was cancelled ($queryExecutionId): $($status.StateChangeReason)"
            }
            default {
                Start-Sleep -Seconds $PollSeconds
            }
        }
        if ($status.State -eq 'SUCCEEDED') {
            break
        }
    }
}

Write-Host "Athena setup completed in workgroup '$workGroup' using database '$databaseName'."
