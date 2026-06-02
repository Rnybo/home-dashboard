$f = 'C:\Users\rnf\Projects\aula-dashboard\frontend\js\globals.js'
$content = Get-Content $f -Raw
$idx = $content.IndexOf("`n// -- Dev mock helpers")
if ($idx -ge 0) { $content = $content.Substring(0, $idx) }
Set-Content $f $content.TrimEnd() -Encoding UTF8 -NoNewline
Write-Host "Done"
