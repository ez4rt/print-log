$computerName = "comp1", "comp2"
$output = @()

foreach ($computer in $computerName) {
    $scriptBlock = {
        $all2dayprint = Get-WinEvent -FilterHashTable @{LogName="Microsoft-Windows-PrintService/Operational"; ID=307; StartTime=(Get-Date).AddDays(-60)} | 
            Select-object -Property TimeCreated, 
                             @{label='UserName';expression={$_.properties[2].value}}, 
                             @{label='Document';expression={$_.properties[1].value}}, 
                             @{label='PrinterName';expression={$_.properties[4].value}}, 
                             @{label='PrintSizeKb';expression={$_.properties[6].value/1024}}, 
                             @{label='Pages';expression={$_.properties[7].value}}, 
                             @{label='Port';expression={$_.properties[5].value}}
        $all2dayprint
    }
    $newData = Invoke-Command -ComputerName $computer -ScriptBlock $scriptBlock
    $output += $newData | Where-Object {$_.TimeCreated -notin $output.TimeCreated -and $_.UserName -notin $output.UserName}
}

$jsonFilePath = "path\to\data.json"
if (Test-Path -Path $jsonFilePath) {
    $existingData = Get-Content -Path $jsonFilePath -Encoding utf8 | ConvertFrom-Json
    $output = $output | Group-Object -Property TimeCreated, UserName | Select-Object -ExpandProperty Group
}

$output | ConvertTo-Json -Depth 100 | Out-File -FilePath $jsonFilePath -Encoding utf8