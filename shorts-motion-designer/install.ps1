param(
  [Parameter(Mandatory=$true)][string]$ProjectPath,
  [string]$DestinationRelative = ".agents\skills\shorts-motion-designer"
)
$ErrorActionPreference = "Stop"
$project = (Resolve-Path -LiteralPath $ProjectPath).Path
if (-not (Test-Path -LiteralPath (Join-Path $project 'package.json')) -and -not (Test-Path -LiteralPath (Join-Path $project 'pyproject.toml'))) {
  Write-Warning "Không thấy package.json hoặc pyproject.toml ở root. Hãy đảm bảo ProjectPath trỏ đúng project cần tích hợp."
}
$destination = Join-Path $project $DestinationRelative
if (Test-Path -LiteralPath $destination) {
  throw "Skill đích đã tồn tại: $destination. Không overwrite. Hãy kiểm tra hoặc đổi DestinationRelative."
}
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $destination) | Out-Null
Copy-Item -LiteralPath $PSScriptRoot -Destination $destination -Recurse
Write-Output "Đã sao chép Skill đến: $destination"
Write-Output "Mở Codex tại project và yêu cầu đọc: $destination\SKILL.md"
Write-Output "Đây mới là cài tài liệu Skill, chưa tích hợp renderer/editor."
