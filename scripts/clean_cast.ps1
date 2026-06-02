$src = 'C:\Users\rnf\Projects\aula-dashboard\frontend\js\cast.js'
$tmp = 'C:\Users\rnf\Projects\aula-dashboard\frontend\js\cast.js.tmp'
$lines = Get-Content $src
$clean = $lines[0..370] + $lines[524..649]
$clean[0] = '// js/cast.js — Google Cast / Nest afspiller widget'
$clean[2] = 'let castState = {};        // device name -> state'
Set-Content $tmp $clean -Encoding UTF8
Remove-Item $src -Force
Rename-Item $tmp $src
Write-Host "Done. Lines: $($clean.Count)"
