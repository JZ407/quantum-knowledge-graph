$action = New-ScheduledTaskAction -Execute 'C:\Python314\python.exe' -Argument '-X utf8 D:\Claude_code\knowledge_graph\build_graph.py'
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Hours 6) -RepetitionDuration (New-TimeSpan -Days 365)
Register-ScheduledTask -TaskName 'QuantumKG_AutoBuild' -Action $action -Trigger $trigger -Force
Write-Host "Task 'QuantumKG_AutoBuild' created successfully"
