$env:RADAR_CHANNEL="discord"
Get-Content .env.local | ForEach-Object {
  if ($_ -match '^([^#=]+)=(.*)$') { [Environment]::SetEnvironmentVariable($matches[1], $matches[2], "Process") }
}
python radar.py *>> radar-log.txt
