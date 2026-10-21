param(
    [ValidateRange(1,100)][int]$Bet = 1,
    [ValidateScript({ $_ -gt 0 -and -not [double]::IsInfinity($_) -and -not [double]::IsNaN($_) })][double]$Minutes = 15
)
$pythonPath = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw 'Python environment missing. Follow README.txt to install dependencies.'
}
& $pythonPath (Join-Path $PSScriptRoot 'blackjack_bot.py') --run --focus --bet $Bet --minutes $Minutes
exit $LASTEXITCODE
