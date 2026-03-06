# Try HKLM (requires admin)
foreach ($v in 9,10,11,12,13,14,15,16) {
    $p = "HKLM:\Software\Adobe\CSXS.$v"
    try {
        New-Item -Path $p -Force -ErrorAction Stop | Out-Null
        Set-ItemProperty -Path $p -Name 'PlayerDebugMode' -Value '1' -Type String -Force
        Write-Host "HKLM CSXS.$v = 1"
    } catch {
        Write-Host "HKLM CSXS.$v FAILED (need admin?): $_"
    }
}

# Also try LogLevel to get more info
foreach ($v in 12,13) {
    $p = "HKCU:\Software\Adobe\CSXS.$v"
    Set-ItemProperty -Path $p -Name 'LogLevel' -Value '6' -Type String -Force
    Write-Host "HKCU CSXS.$v LogLevel = 6"
}
