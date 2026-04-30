rule Suspicious_Extension
{
    meta:
        description = "Detects creation of a .ps1 or .bat file which might be suspicious in certain contexts"
        author = "Mini-EDR"
        severity = "Low"
    strings:
        $ps1 = ".ps1" nocase
        $bat = ".bat" nocase
        $exe = ".exe" nocase
    condition:
        $ps1 or $bat or $exe
}

rule Suspicious_String_Mimikatz
{
    meta:
        description = "Detects Mimikatz keywords"
        severity = "High"
    strings:
        $m1 = "mimikatz" nocase ascii wide
        $m2 = "sekurlsa::logonpasswords" nocase ascii wide
    condition:
        any of them
}
