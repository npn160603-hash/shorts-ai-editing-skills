param(
  [Parameter(Mandatory=$true)][string]$ProjectPath,
  [string]$DestinationRelative = ".agents\skills\shorts-ai-editing-skills"
)
$ErrorActionPreference = "Stop"
$project = (Resolve-Path -LiteralPath $ProjectPath).Path
$destination = Join-Path $project $DestinationRelative
if (Test-Path -LiteralPath $destination) {
  throw "Đích đã tồn tại: $destination. Không ghi đè. Đổi -DestinationRelative hoặc tự kiểm tra."
}
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $destination) | Out-Null
Copy-Item -LiteralPath $PSScriptRoot -Destination $destination -Recurse -Exclude "_demo_out"
$v11 = Join-Path (Split-Path -Parent $PSScriptRoot) "shorts-motion-designer"
$v11dest = Join-Path (Split-Path -Parent $destination) "shorts-motion-designer"
if ((Test-Path -LiteralPath $v11) -and -not (Test-Path -LiteralPath $v11dest)) {
  Copy-Item -LiteralPath $v11 -Destination $v11dest -Recurse
  Write-Output "Đã chép kèm Shorts Motion Designer V1.1 (để kiểm tương thích schema)."
}
Write-Output "Đã chép gói đến: $destination"
Write-Output "Kiểm tra: python `"$destination\scripts\check_all.py`""
Write-Output "Đây mới là cài tài liệu + runtime tham chiếu, CHƯA tích hợp vào editor. Xem CODEX_START_HERE.md."
