# Repair the pinned generator's overlapping-function emission for this XEX.
# Both entry points share one translated body. No guest instruction is skipped.
$ErrorActionPreference='Stop'
$generated=Join-Path $PSScriptRoot '../generated/default'
$files=Get-ChildItem -LiteralPath $generated -Filter 'psu_recomp.*.cpp'
# ReXGlue returns valid handles with the high bit set. Only INVALID_SOCKET is an error.
$socketBranches=@(
    @('825B1F38','!ctx.cr0.lt','REX_LOAD_U32(ctx.r31.u32 + 4) != UINT32_MAX'),
    @('825B1DBC','!ctx.cr0.lt','REX_LOAD_U32(ctx.r31.u32 + 4) != UINT32_MAX'),
    @('825B1DE0','!ctx.cr6.lt','ctx.r11.u32 != UINT32_MAX'),
    @('825B14F8','!ctx.cr6.lt','ctx.r30.u32 != UINT32_MAX'),
    @('825B1420','!ctx.cr6.lt','ctx.r30.u32 != UINT32_MAX'),
    @('825B1748','ctx.cr6.lt','ctx.r11.u32 == UINT32_MAX'),
    @('825B1770','ctx.cr6.lt','ctx.r11.u32 == UINT32_MAX'),
    @('825B1950','!ctx.cr0.lt','ctx.r3.u32 != UINT32_MAX'),
    @('825B169C','ctx.cr0.lt','ctx.r3.u32 == UINT32_MAX'),
    @('825B1838','ctx.cr6.lt','ctx.r11.u32 == UINT32_MAX')
)
foreach ($branch in $socketBranches) {
    $label,$oldCondition,$newCondition=$branch
    $socket=@($files | Select-String -SimpleMatch "loc_${label}:" | Select-Object -ExpandProperty Path -Unique)
    if ($socket.Count -ne 1) { throw "Expected one translated TCP branch target $label." }
    $socketText=[IO.File]::ReadAllText($socket[0])
    $socketBranch="if ($oldCondition) goto loc_$label;"
    $socketFix="if ($newCondition) goto loc_$label;"
    if (!$socketText.Contains($socketFix)) {
        if ([regex]::Matches($socketText,[regex]::Escape($socketBranch)).Count -ne 1) {
            throw "Unexpected TCP socket result branch to $label."
        }
        [IO.File]::WriteAllText($socket[0],$socketText.Replace($socketBranch,$socketFix))
    }
}
$parent=@($files | Where-Object { [IO.File]::ReadAllText($_.FullName).Contains('DEFINE_REX_FUNC(sub_826380E8)') })
$child=@($files | Where-Object { [IO.File]::ReadAllText($_.FullName).Contains('DEFINE_REX_FUNC(sub_82638260)') })
if ($parent.Count -ne 1 -or $child.Count -ne 1) { throw 'Expected unique loop entry points.' }
$parentText=[IO.File]::ReadAllText($parent[0].FullName)
$childText=[IO.File]::ReadAllText($child[0].FullName)
if ($parentText.Contains('void PsuSharedLoop(') -and $childText.Contains('PsuSharedLoop(ctx, base, true)')) { return }
$pattern='(?s)DEFINE_REX_FUNC\(sub_826380E8\) \{(.*?)\n\}'
$match=[regex]::Match($parentText,$pattern)
if (-not $match.Success) { throw 'Loop body not found.' }
$body=$match.Groups[1].Value
$instructionLines=@($body.Split("`n") | Where-Object { $_ -match '^\s*// ' -and $_ -notmatch 'ERROR:' })
if ($instructionLines.Count -ne 198 -or $instructionLines[94].Trim() -ne '// fmsubs f0,f13,f6,f0') { throw 'Unexpected translated instruction layout.' }
$targets=@('82638184','8263816C','82638150','8263811C')
foreach($target in $targets) {
    if (-not $body.Contains("loc_${target}:")) { throw "Missing original loop label $target" }
    $fatal='REX_FATAL\("Unresolved branch from 0x[0-9A-F]+ to 0x'+$target+'"\)'
    if ([regex]::Matches($body,$fatal).Count -ne 1) { throw "Unexpected branch count for $target" }
    $body=[regex]::Replace($body,$fatal,"goto loc_$target")
}
$body=[regex]::Replace($body,'(?m)^\s*// ERROR: conditional branch to unknown address 0x[0-9A-F]+\r?\n','')
$lines=$body.Split("`n")
$instruction=0
for($i=0;$i -lt $lines.Length;$i++) {
    if ($lines[$i] -match '^\s*// ') {
        if ($instruction -eq 94) { $lines[$i]="loc_82638260:`n"+$lines[$i] }
        $instruction++
    }
}
$body=$lines -join "`n"
$body=$body.Replace('PPCRegister temp{};','PPCRegister temp{};'+"`n`tif (resume) goto loc_82638260;")
$replacement="void PsuSharedLoop(PPCContext& ctx, uint8_t* base, bool resume) {$body`n}`n`nDEFINE_REX_FUNC(sub_826380E8) { PsuSharedLoop(ctx, base, false); }"
$parentText=$parentText.Remove($match.Index,$match.Length).Insert($match.Index,$replacement)
$childMatch=[regex]::Match($childText,'(?s)DEFINE_REX_FUNC\(sub_82638260\) \{.*?\n\}')
if (-not $childMatch.Success) { throw 'Secondary loop entry not found.' }
$wrapper="void PsuSharedLoop(PPCContext&, uint8_t*, bool);`nDEFINE_REX_FUNC(sub_82638260) { PsuSharedLoop(ctx, base, true); }"
$childText=$childText.Remove($childMatch.Index,$childMatch.Length).Insert($childMatch.Index,$wrapper)
[IO.File]::WriteAllText($parent[0].FullName,$parentText)
[IO.File]::WriteAllText($child[0].FullName,$childText)
Write-Output 'Repaired shared loop entry points and four backward branches.'
