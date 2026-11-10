param([Parameter(Mandatory=$true)][string]$Workspace)
# Cài gói vào workspace OpenCode (không ghi đè). Gọi bản Python cho đồng nhất trên mọi hệ điều hành.
python "$PSScriptRoot\scripts\install_opencode.py" "$Workspace"
