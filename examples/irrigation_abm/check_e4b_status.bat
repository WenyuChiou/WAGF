@echo off
REM ============================================================
REM   One-shot codex monitor of e4b seed46 recovery
REM   Double-click for instant status, or schedule via Task Scheduler
REM ============================================================
for %%I in ("%~dp0..\..") do SET "REPO=%%~fI"
cd /d "%REPO%"
for /f "tokens=2 delims==" %%I in ('"wmic os get LocalDateTime /value | findstr LocalDateTime"') do set "DT=%%I"
SET "TS=%DT:~0,8%_%DT:~8,6%"
SET "OUT_FILE=.ai/codex_status_e4b_%TS%.md"

REM No -o flag (it would overwrite the structured file with codex's final message).
REM Brief instructs codex to use its Write tool directly.
codex exec --full-auto -C "%REPO%" "Read .ai/codex_e4b_monitor_brief.md and execute its checks. Write the structured status report directly via your Write tool to %OUT_FILE%. Do NOT echo the report in your final message — just confirm 'Wrote %OUT_FILE%' as the last line."

echo.
echo ============================================================
echo Latest status:
echo ============================================================
type "%OUT_FILE%"
echo.
pause
