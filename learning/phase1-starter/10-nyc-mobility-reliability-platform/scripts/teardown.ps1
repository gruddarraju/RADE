[CmdletBinding()]
param(
    [Parameter()]
    [ValidateNotNullOrEmpty()]
    [string] $StackName = 'nyc-mobility-reliability-dev',

    [Parameter()]
    [ValidateNotNullOrEmpty()]
    [string] $Region = 'us-east-1',

    [Parameter(Mandatory)]
    [switch] $ConfirmDelete,

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

if (-not $ConfirmDelete) {
    throw 'Refusing teardown. Re-run with -ConfirmDelete to delete the CloudFormation stack.'
}
if (-not (Get-Command 'aws' -ErrorAction SilentlyContinue)) {
    throw "Required command 'aws' was not found on PATH."
}

Write-Warning "Deleting CloudFormation stack '$StackName' in '$Region'."
Write-Host 'Only the stack will be deleted. No S3 bucket will be emptied or force-deleted.'
Write-Host 'The stack data bucket is retained by policy, including all object versions.'
Write-Host 'The external artifact bucket created or configured by deploy.ps1 is not a stack resource and also remains.'

$null = Invoke-AwsCli -Arguments @(
    'cloudformation', 'delete-stack', '--stack-name', $StackName
)
Write-Host 'Waiting for stack deletion to finish...'
$null = Invoke-AwsCli -Arguments @(
    'cloudformation', 'wait', 'stack-delete-complete', '--stack-name', $StackName
)

Write-Host "Stack '$StackName' was deleted. Retained data and external artifact buckets were not modified."
