foreach ($v in 14,15,16) {
    $p = "HKCU:\Software\Adobe\CSXS.$v"
    New-Item -Path $p -Force | Out-Null
    Set-ItemProperty -Path $p -Name 'PlayerDebugMode' -Value '1' -Type String -Force
    Write-Host "CSXS.$v PlayerDebugMode = 1"
}
