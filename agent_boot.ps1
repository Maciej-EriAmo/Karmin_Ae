# Holon SE boot — zawsze z katalogu repo
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
python "$PSScriptRoot\agent_boot.py" @args
