$p = Get-Process -Name 'Illustrator' -ErrorAction SilentlyContinue
if ($p) { Write-Host 'WARNING: Illustrator STILL RUNNING' } else { Write-Host 'OK: Illustrator is closed' }

Remove-Item 'C:\Users\stock\AppData\Local\Temp\cep_cache' -Recurse -Force -ErrorAction SilentlyContinue
Write-Host 'CEP cache cleared'

Remove-Item 'C:\Users\stock\AppData\Local\Temp\CEP12-ILST*' -Force -ErrorAction SilentlyContinue
Remove-Item 'C:\Users\stock\AppData\Local\Temp\CEPHtmlEngine12-ILST*' -Force -ErrorAction SilentlyContinue
Write-Host 'Old logs cleared'
