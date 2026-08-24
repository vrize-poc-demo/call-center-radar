param([string]$OutDir)

Add-Type -AssemblyName System.Speech
$ErrorActionPreference = 'Stop'
$ffmpeg = 'C:\Hack-Projects\ffmpeg-9.0.1-essentials_build\bin\ffmpeg.exe'
$ffprobe = 'C:\Hack-Projects\ffmpeg-9.0.1-essentials_build\bin\ffprobe.exe'
$audioDir = Join-Path $OutDir 'audio'
$metaDir = Join-Path $OutDir 'metadata'
New-Item -ItemType Directory -Force -Path $audioDir, $metaDir | Out-Null

$cases = @(
  @{ Slug='01-analyzed-resolved'; Agent='Maya Agent'; Customer='Resolved Customer'; Expected='Analyzed calls / resolved'; Turns=@(
      @{ Speaker='agent'; Text='Thank you for calling Call Center Radar support. How can I help today?' },
      @{ Speaker='customer'; Text='I need help checking my card delivery status.' },
      @{ Speaker='agent'; Text='I can help with that. I see the card was delivered this morning and the account is active.' },
      @{ Speaker='customer'; Text='Great, that answers my question. Thank you, this is resolved.' }
    )},
  @{ Slug='02-needs-attention'; Agent='Noah Agent'; Customer='Needs Attention Customer'; Expected='Needs attention'; Turns=@(
      @{ Speaker='agent'; Text='Thank you for calling. What problem can I help with?' },
      @{ Speaker='customer'; Text='My payment problem is still not resolved and I cannot access my account.' },
      @{ Speaker='agent'; Text='I am sorry this is still happening. I will document it and escalate the case.' },
      @{ Speaker='customer'; Text='Please do, because I need a follow up today.' }
    )},
  @{ Slug='03-high-risk'; Agent='Isha Agent'; Customer='High Risk Customer'; Expected='High risk'; Turns=@(
      @{ Speaker='agent'; Text='Hello, I can review your account issue now.' },
      @{ Speaker='customer'; Text='This billing problem is not resolved. I still cannot access my account, and I will cancel if no one fixes it today.' },
      @{ Speaker='agent'; Text='I understand. I am escalating this immediately and will request urgent support.' },
      @{ Speaker='customer'; Text='Good, but I need a clear answer before the end of the day.' }
    )},
  @{ Slug='04-unresolved'; Agent='Liam Agent'; Customer='Unresolved Customer'; Expected='Unresolved'; Turns=@(
      @{ Speaker='agent'; Text='Thanks for calling. Are you still having trouble with the refund?' },
      @{ Speaker='customer'; Text='Yes, it is not resolved. I still do not see the refund and I need someone to check it.' },
      @{ Speaker='agent'; Text='I will open a follow up case and send the details to the billing team.' },
      @{ Speaker='customer'; Text='Okay, please follow up because the outcome is still unresolved.' }
    )},
  @{ Slug='05-resolved-customer'; Agent='Ava Agent'; Customer='Happy Resolved Customer'; Expected='Resolved customer'; Turns=@(
      @{ Speaker='agent'; Text='I found the order and updated the delivery address.' },
      @{ Speaker='customer'; Text='Perfect, that fixed the problem.' },
      @{ Speaker='agent'; Text='Great. Your delivery is now scheduled for tomorrow.' },
      @{ Speaker='customer'; Text='Thank you. Everything is resolved now.' }
    )},
  @{ Slug='06-contradiction-customer'; Agent='Ethan Agent'; Customer='Contradiction Customer'; Expected='Contradiction customer'; Turns=@(
      @{ Speaker='agent'; Text='I refreshed your profile. The login issue is resolved and the account is working now.' },
      @{ Speaker='customer'; Text='No, it is still not working. I still cannot access the account.' },
      @{ Speaker='agent'; Text='Thank you for checking. I will reopen the case and escalate it.' },
      @{ Speaker='customer'; Text='Please do, because it did not work.' }
    )},
  @{ Slug='07-follow-up-customer'; Agent='Sophia Agent'; Customer='Followup Customer'; Expected='Follow-up customer'; Turns=@(
      @{ Speaker='agent'; Text='I reviewed the claim and we need one more verification step.' },
      @{ Speaker='customer'; Text='The problem is still open and I need follow up from a supervisor.' },
      @{ Speaker='agent'; Text='I will schedule a callback and add notes for the supervisor.' },
      @{ Speaker='customer'; Text='Thanks. Please call me back today because this is not resolved.' }
    )},
  @{ Slug='08-high-risk-customer'; Agent='Mason Agent'; Customer='Escalation Customer'; Expected='High-risk customer'; Turns=@(
      @{ Speaker='agent'; Text='I am sorry for the repeated issue. Tell me what happened today.' },
      @{ Speaker='customer'; Text='This is the third time I called. The service problem is still not working, and I am filing a complaint if it is not fixed.' },
      @{ Speaker='agent'; Text='I understand the urgency. I will escalate this as high priority now.' },
      @{ Speaker='customer'; Text='I need confirmation today. Otherwise I will cancel the service.' }
    )}
)

function Save-Speech([string]$Text, [string]$Path, [string]$Speaker) {
  $voice = New-Object -ComObject SAPI.SpVoice
  foreach ($candidate in @($voice.GetVoices())) {
    $description = $candidate.GetDescription()
    if ($Speaker -eq 'agent' -and $description -like '*David*') { $voice.Voice = $candidate; break }
    if ($Speaker -eq 'customer' -and $description -like '*Zira*') { $voice.Voice = $candidate; break }
  }
  $stream = New-Object -ComObject SAPI.SpFileStream
  $stream.Format.Type = 22
  $stream.Open($Path, 3, $false)
  $voice.AudioOutputStream = $stream
  [void]$voice.Speak($Text)
  $stream.Close()
}

$manifest = @()
foreach ($case in $cases) {
  $tmp = Join-Path $OutDir ('.tmp-' + $case.Slug)
  if (Test-Path $tmp) { Remove-Item -LiteralPath $tmp -Recurse -Force }
  New-Item -ItemType Directory -Force -Path $tmp | Out-Null
  $clipPaths = @()
  $i = 0
  foreach ($turn in $case.Turns) {
    $mono = Join-Path $tmp ('mono-{0:D2}.wav' -f $i)
    $clip = Join-Path $tmp ('clip-{0:D2}.wav' -f $i)
    $labelText = if ($turn.Speaker -eq 'agent') { 'Agent says. ' + $turn.Text } else { 'Customer says. ' + $turn.Text }
    Save-Speech $labelText $mono $turn.Speaker
    if ($turn.Speaker -eq 'agent') {
      & $ffmpeg -y -v error -i $mono -af 'pan=stereo|c0=c0|c1=0*c0,apad=pad_dur=0.35' -ar 16000 $clip
    } else {
      & $ffmpeg -y -v error -i $mono -af 'pan=stereo|c0=0*c0|c1=c0,apad=pad_dur=0.35' -ar 16000 $clip
    }
    if ($LASTEXITCODE -ne 0) { throw "ffmpeg failed for $($case.Slug) turn $i" }
    $clipPaths += $clip
    $i++
  }
  $listPath = Join-Path $tmp 'concat.txt'
  [System.IO.File]::WriteAllLines($listPath, ($clipPaths | ForEach-Object { "file '$($_.Replace("'", "''"))'" }))
  $outWav = Join-Path $audioDir ($case.Slug + '.wav')
  & $ffmpeg -y -v error -f concat -safe 0 -i $listPath -c copy $outWav
  if ($LASTEXITCODE -ne 0) { throw "ffmpeg concat failed for $($case.Slug)" }
  $meta = [ordered]@{
    agent = [ordered]@{ speaker_id = 1; metadata = [ordered]@{ agent_name = $case.Agent } }
    caller = [ordered]@{ speaker_id = 2; metadata = [ordered]@{ 'first and last name' = $case.Customer } }
    demo = [ordered]@{ expected_category = $case.Expected; audio_file = ($case.Slug + '.wav') }
  }
  $metaPath = Join-Path $metaDir ($case.Slug + '.json')
  [System.IO.File]::WriteAllText($metaPath, ($meta | ConvertTo-Json -Depth 8), [System.Text.Encoding]::UTF8)
  $probe = & $ffprobe -v error -select_streams a:0 -show_entries stream=channels,duration -of csv=p=0 $outWav
  $manifest += [ordered]@{ category=$case.Expected; audio=$outWav; metadata=$metaPath; ffprobe=$probe }
  Remove-Item -LiteralPath $tmp -Recurse -Force
}
[System.IO.File]::WriteAllText((Join-Path $OutDir 'manifest.json'), ($manifest | ConvertTo-Json -Depth 6), [System.Text.Encoding]::UTF8)
$manifest | ConvertTo-Json -Depth 6