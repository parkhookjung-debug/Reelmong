# 작업 스케줄러에 "ReelmongCrol" 태스크 등록 (로그온 시 1회 실행)
# 실행: powershell -ExecutionPolicy Bypass -File register_task.ps1

# 콘솔 한글 출력 인코딩
chcp 65001 > $null
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$TaskName = "ReelmongCrol"
$Here     = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python   = "C:\Python314\python.exe"
$Script   = Join-Path $Here "collect_once.py"

if (-not (Test-Path $Python)) {
    Write-Host "ERROR: Python을 찾을 수 없음: $Python" -ForegroundColor Red
    exit 1
}
if (-not (Test-Path $Script)) {
    Write-Host "ERROR: 스크립트를 찾을 수 없음: $Script" -ForegroundColor Red
    exit 1
}

# 기존 태스크 있으면 제거
if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Write-Host "기존 태스크 제거 중..."
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false | Out-Null
}

# Action: 콘솔 창 잠깐 떴다 사라짐 (pythonw 쓰면 완전 백그라운드)
$Action = New-ScheduledTaskAction `
    -Execute $Python `
    -Argument "`"$Script`"" `
    -WorkingDirectory $Here

# Trigger: 현재 사용자 로그온 시 (CIM 방식으로 만들어야 Delay 지원됨)
$class   = Get-CimClass -ClassName MSFT_TaskLogonTrigger `
                        -Namespace Root\Microsoft\Windows\TaskScheduler
$Trigger = $class | New-CimInstance -ClientOnly
$Trigger.Enabled = $true
$Trigger.UserId  = "$env:USERDOMAIN\$env:USERNAME"
$Trigger.Delay   = "PT1M"   # 로그온 1분 뒤 (PATH/네트워크 안정화 대기)

# 조건: 네트워크 있을 때만, AC/배터리 무관
$Settings = New-ScheduledTaskSettingsSet `
    -RunOnlyIfNetworkAvailable `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 30) `
    -MultipleInstances IgnoreNew

# 현재 사용자 컨텍스트로 등록 (관리자 권한 불필요)
$Principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive

$Task = New-ScheduledTask -Action $Action -Trigger $Trigger -Settings $Settings -Principal $Principal `
    -Description "릴몽 유튜브 트렌드 자동 수집 (로그온 1분 후 1회)"

Register-ScheduledTask -TaskName $TaskName -InputObject $Task | Out-Null

Write-Host ""
Write-Host "[OK] 태스크 등록 완료: $TaskName" -ForegroundColor Green
Write-Host "    - 트리거 : 로그온 1분 후"
Write-Host "    - 실행   : $Python `"$Script`""
Write-Host "    - 작업폴더: $Here"
Write-Host "    - 조건   : 네트워크 있을 때만, 30분 타임아웃"
Write-Host ""
Write-Host "확인: Get-ScheduledTask -TaskName $TaskName"
Write-Host "수동 실행: Start-ScheduledTask -TaskName $TaskName"
Write-Host "로그: $Here\logs\collect_<날짜>.log"
Write-Host "제거: Unregister-ScheduledTask -TaskName $TaskName -Confirm:`$false"
