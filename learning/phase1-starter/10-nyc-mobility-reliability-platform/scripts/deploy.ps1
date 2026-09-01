[CmdletBinding()]
param(
    [Parameter()]
    [ValidatePattern('^[a-z][a-z0-9-]{2,29}$')]
    [string] $ProjectName = 'nyc-mobility-reliability',

    [Parameter()]
    [ValidatePattern('^[a-z][a-z0-9-]{1,7}$')]
    [string] $Environment = 'dev',

    [Parameter()]
    [ValidateNotNullOrEmpty()]
    [string] $Region = 'us-east-1',

    [Parameter()]
    [ValidateNotNullOrEmpty()]
    [string] $StackName = 'nyc-mobility-reliability-dev',

    [Parameter()]
    [string] $ArtifactBucketName = '',

    [Parameter()]
    [ValidateNotNullOrEmpty()]
    [string] $ArtifactPrefix = 'nyc-mobility-reliability',

    [Parameter()]
    [string] $NotificationEmail = '',

    [Parameter()]
    [bool] $ScheduleEnabled = $false,

    [Parameter()]
    [ValidateRange(0.0, 1.0)]
    [double] $RejectRateThreshold = 0.05,

    [Parameter()]
    [ValidateRange(1, 36500)]
    [int] $RawRetentionDays = 365,

    [Parameter()]
    [ValidateRange(1, 36500)]
    [int] $QuarantineRetentionDays = 90,

    [Parameter()]
    [ValidateSet(1, 3, 5, 7, 14, 30, 60, 90, 120, 150, 180, 365, 400, 545, 731, 1096, 1827, 2192, 2557, 2922, 3288, 3653)]
    [int] $LogRetentionDays = 14,

    [Parameter()]
    [string] $Profile = ''
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Assert-Command {
    param([Parameter(Mandatory)][string] $Name)

    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Required command '$Name' was not found on PATH."
    }
}

function Invoke-NativeCommand {
    param(
        [Parameter(Mandatory)][string] $Command,
        [Parameter(Mandatory)][string[]] $Arguments
    )

    Write-Verbose ("Running: {0} {1}" -f $Command, ($Arguments -join ' '))
    $output = & $Command @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code ${LASTEXITCODE}: $Command $($Arguments -join ' ')"
    }
    return ($output -join [Environment]::NewLine)
}

function Invoke-AwsCli {
    param([Parameter(Mandatory)][string[]] $Arguments)

    $allArguments = @($Arguments) + @('--region', $Region)
    if ($Profile) {
        $allArguments += @('--profile', $Profile)
    }
    return Invoke-NativeCommand -Command 'aws' -Arguments $allArguments
}

Assert-Command -Name 'aws'
Assert-Command -Name 'sam'

$projectRoot = Split-Path -Parent $PSScriptRoot
$templatePath = Join-Path $projectRoot 'infra\template.yaml'
$packagedTemplatePath = Join-Path $projectRoot 'infra\packaged-template.yaml'
$buildDirectory = Join-Path $projectRoot '.aws-sam\build'
$jobDirectory = Join-Path $projectRoot 'src\jobs'

$accountId = (Invoke-AwsCli -Arguments @(
        'sts', 'get-caller-identity', '--query', 'Account', '--output', 'text'
    )).Trim()
if ($accountId -notmatch '^\d{12}$') {
    throw "STS returned an unexpected AWS account ID: '$accountId'."
}
Write-Host "Deploying to AWS account $accountId in $Region."

if (-not $ArtifactBucketName) {
    $baseBucketName = "$ProjectName-$Environment-artifacts-$accountId-$Region".ToLowerInvariant()
    $ArtifactBucketName = ($baseBucketName -replace '[^a-z0-9.-]', '-')
}
if ($ArtifactBucketName.Length -lt 3 -or $ArtifactBucketName.Length -gt 63 -or
    $ArtifactBucketName -notmatch '^[a-z0-9][a-z0-9.-]*[a-z0-9]$') {
    throw "ArtifactBucketName '$ArtifactBucketName' is not a valid S3 bucket name."
}

$headArguments = @('s3api', 'head-bucket', '--bucket', $ArtifactBucketName, '--region', $Region)
if ($Profile) {
    $headArguments += @('--profile', $Profile)
}
$null = & aws @headArguments 2>$null
$bucketExists = $LASTEXITCODE -eq 0

if (-not $bucketExists) {
    Write-Host "Creating external artifact bucket s3://$ArtifactBucketName."
    $createArguments = @('s3api', 'create-bucket', '--bucket', $ArtifactBucketName)
    if ($Region -ne 'us-east-1') {
        $createArguments += @(
            '--create-bucket-configuration',
            "LocationConstraint=$Region"
        )
    }
    $null = Invoke-AwsCli -Arguments $createArguments
}
else {
    Write-Host "Using existing artifact bucket s3://$ArtifactBucketName."
}

$encryptionConfiguration = 'Rules=[{ApplyServerSideEncryptionByDefault={SSEAlgorithm=AES256},BucketKeyEnabled=false}]'
$publicAccessConfiguration = 'BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true'
$ownershipConfiguration = 'Rules=[{ObjectOwnership=BucketOwnerEnforced}]'

$null = Invoke-AwsCli -Arguments @(
    's3api', 'put-bucket-versioning', '--bucket', $ArtifactBucketName,
    '--versioning-configuration', 'Status=Enabled'
)
$null = Invoke-AwsCli -Arguments @(
    's3api', 'put-bucket-encryption', '--bucket', $ArtifactBucketName,
    '--server-side-encryption-configuration', $encryptionConfiguration
)
$null = Invoke-AwsCli -Arguments @(
    's3api', 'put-public-access-block', '--bucket', $ArtifactBucketName,
    '--public-access-block-configuration', $publicAccessConfiguration
)
$null = Invoke-AwsCli -Arguments @(
    's3api', 'put-bucket-ownership-controls', '--bucket', $ArtifactBucketName,
    '--ownership-controls', $ownershipConfiguration
)

$ArtifactPrefix = $ArtifactPrefix.Trim('/')
if (-not $ArtifactPrefix) {
    throw 'ArtifactPrefix must contain at least one non-slash character.'
}
$jobFiles = @('ingest_tlc.py', 'raw_to_curated.py', 'curated_to_aggregate.py')
$jobHashes = foreach ($jobFile in $jobFiles) {
    $sourcePath = Join-Path $jobDirectory $jobFile
    if (-not (Test-Path -LiteralPath $sourcePath -PathType Leaf)) {
        throw "Glue job script was not found: $sourcePath"
    }
    (Get-FileHash -LiteralPath $sourcePath -Algorithm SHA256).Hash.ToLowerInvariant()
}
$hashAlgorithm = [Security.Cryptography.SHA256]::Create()
try {
    $releaseBytes = [Text.Encoding]::UTF8.GetBytes(($jobHashes -join ''))
    $releaseHash = $hashAlgorithm.ComputeHash($releaseBytes)
}
finally {
    $hashAlgorithm.Dispose()
}
$releaseId = ([BitConverter]::ToString($releaseHash) -replace '-', '').ToLowerInvariant().Substring(0, 16)
$deploymentArtifactPrefix = "$ArtifactPrefix/releases/$releaseId"
Write-Host "Using immutable Glue release prefix $deploymentArtifactPrefix."

foreach ($jobFile in $jobFiles) {
    $sourcePath = Join-Path $jobDirectory $jobFile
    $destination = "s3://$ArtifactBucketName/$deploymentArtifactPrefix/jobs/$jobFile"
    Write-Host "Uploading $jobFile to $destination"
    $null = Invoke-AwsCli -Arguments @(
        's3', 'cp', $sourcePath, $destination,
        '--only-show-errors', '--sse', 'AES256'
    )
}

$samCommonArguments = @('--region', $Region)
if ($Profile) {
    $samCommonArguments += @('--profile', $Profile)
}

Write-Host 'Building the SAM application.'
$null = Invoke-NativeCommand -Command 'sam' -Arguments (@(
        'build', '--template-file', $templatePath,
        '--build-dir', $buildDirectory,
        '--cached', '--parallel'
    ) + $samCommonArguments)

$builtTemplatePath = Join-Path $buildDirectory 'template.yaml'
Write-Host 'Packaging Lambda and Step Functions artifacts.'
$null = Invoke-NativeCommand -Command 'sam' -Arguments (@(
        'package', '--template-file', $builtTemplatePath,
        '--s3-bucket', $ArtifactBucketName,
        '--s3-prefix', "$deploymentArtifactPrefix/sam",
        '--output-template-file', $packagedTemplatePath
    ) + $samCommonArguments)

$parameterOverrides = @(
    "ProjectName=$ProjectName",
    "Environment=$Environment",
    "ArtifactBucketName=$ArtifactBucketName",
    "ArtifactPrefix=$deploymentArtifactPrefix",
    "ScheduleEnabled=$($ScheduleEnabled.ToString().ToLowerInvariant())",
    "RejectRateThreshold=$($RejectRateThreshold.ToString([Globalization.CultureInfo]::InvariantCulture))",
    "RawRetentionDays=$RawRetentionDays",
    "QuarantineRetentionDays=$QuarantineRetentionDays",
    "LogRetentionDays=$LogRetentionDays"
)
if ($NotificationEmail) {
    $parameterOverrides += "NotificationEmail=$NotificationEmail"
}

Write-Host "Deploying CloudFormation stack $StackName non-interactively."
$null = Invoke-NativeCommand -Command 'sam' -Arguments (@(
        'deploy', '--template-file', $packagedTemplatePath,
        '--stack-name', $StackName,
        '--capabilities', 'CAPABILITY_IAM',
        '--no-confirm-changeset', '--no-fail-on-empty-changeset',
        '--parameter-overrides'
    ) + $parameterOverrides + $samCommonArguments)

Write-Host "`nStack outputs:"
$outputs = Invoke-AwsCli -Arguments @(
    'cloudformation', 'describe-stacks', '--stack-name', $StackName,
    '--query', 'Stacks[0].Outputs[].{OutputKey:OutputKey,OutputValue:OutputValue}',
    '--output', 'table'
)
Write-Host $outputs
Write-Host "`nArtifact bucket: s3://$ArtifactBucketName/$deploymentArtifactPrefix (external to the stack and not deleted by teardown)."
