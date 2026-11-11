---
name: Legacy
os: Windows
difficulty: Easy
retired: true
released: 2017-03-15
updated: 2026-11-11
techniques:
  - enumeration
  - smb
  - patch-level
summary: "A retired Windows XP host with almost no surface. The patch level is the machine."
example: true
---

> **Example methodology note.** A study sketch of a long-retired machine, written for this shelf. It is original, it is not copied from a walkthrough, and it is not a reproduction guide. The class of issue and the impact are named. The bytes that would carry an attack out are not.

## Recon

There is very little to enumerate, and that is the enumeration. The ports that answer are the old Windows file-sharing set: the endpoint mapper, NetBIOS, and SMB. No site, no database, no second product sitting there to be interesting.

The operating system comes back as Windows XP. SMB is the dialect from that era, and message signing is not earning its keep. XP left vendor support in 2014. A reachable, unpatched file-sharing service on an operating system with no vendor is not a subtle situation. Write the operating system down as a finding before you write a CVE down as a plan.

It is still worth noting the host name, and whether any share can be read without credentials. On this box that work does not open a door. It stops the engagement being "one request, and it was over", which is a poor habit even on the day it would have been enough.

## Foothold

The class is [MS08-067](https://nvd.nist.gov/vuln/detail/CVE-2008-4250): a flaw in the Server service's path handling, reachable over SMB before any login. It was serious enough, and common enough, to be wormed in the Conficker era. The impact is code execution inside a service that runs as the operating system's own account.

Two facts about this bug are the lesson.

The service pack and the language matter. The bulletin covers a family of targets, and a wrong guess is how an old host falls over rather than yielding a session. On a retired lab machine that is an inconvenience. Anywhere else it is the reason to confirm the scope before iterating.

There is nothing to authenticate to. The missing patch is the whole precondition. On a supported Windows build with SMB still exposed, the note would be about exposure, signing, and relay. This is XP. The note is about a patch from 2008 that was never applied.

## Privilege escalation

There is no second stage. The vulnerable code already runs as SYSTEM, so execution arrives at the top of the box. A bug in a program a person launched, and a bug in a service the machine launched, are different engagements even when the abstracts look similar. Read the privilege of the component before treating a foothold as understood.

The two flag files live in the ordinary profile directories. Collecting them is housekeeping. It is not a technique, and the paths are not the thing to memorise.

## Lessons

- Patch level can be the entire machine. The report sentence is short on purpose: the host runs an unsupported operating system and exposes an unpatched Server service (MS08-067), which allows unauthenticated code execution as SYSTEM. Blast radius is the rest of the paragraph, not a second exploit.
- End of support, plus SMB on a reachable network, is a business finding even when no payload is sent. A reader who only hears the word SYSTEM has been taught the wrong lesson.
- Do not collect a second issue to feel busy. Three ports, one of them the box: write that down and move on.
- The drill is explaining, without notes, why this one has no privilege-escalation phase. "The exploit is admin" is not the explanation. The explanation is which process the bug runs in.
