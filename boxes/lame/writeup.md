---
name: Lame
os: Linux
difficulty: Easy
retired: true
released: 2017-03-14
retired_on: 2017-05-26
updated: 2026-11-11
techniques:
  - enumeration
  - service-version
  - smb
  - ftp
summary: "The first machine on the platform, long retired. Several old services answer at once. The work is telling a real door from a banner."
example: true
---

> **Example methodology note.** A study sketch of a long-retired machine, written for this shelf. It is original, it is not copied from a walkthrough, and it is not a reproduction guide. The class of issue and the impact are named. The bytes that would carry an attack out are not.

## Recon

Treat a host this old as a pile of hypotheses, not as a shopping list of modules. A version scan has to include the high ports: one of the services worth a line is not sitting in the first thousand.

| Service | Why it earns a line | Working theory |
| --- | --- | --- |
| FTP | Banner matches a build with a [public backdoor](https://nvd.nist.gov/vuln/detail/CVE-2011-2523) | The version may be a costume. The behaviour has to actually be there |
| SSH | OpenSSH from an Ubuntu of that era | A version anchor. Not, by itself, a way in |
| SMB | Samba 3.0.20, inside [CVE-2007-2447](https://nvd.nist.gov/vuln/detail/CVE-2007-2447) | Username-map handling can become command execution, if that feature is on. Impact is the privilege of the daemon |
| distcc | Compiler daemon on a high port, [CVE-2004-2687](https://nvd.nist.gov/vuln/detail/CVE-2004-2687) | Command execution as whichever account the daemon uses. A different question from the Samba one |

Write the hostname and the workgroup down. They confirm the notes belong to this box, and they stop the next machine inheriting them.

## Foothold

The FTP theory dies, and that is the useful part. The version matches a backdoor known in the wild. On this retired image the behaviour is not there. A matching banner is a lead. It becomes a finding only when the behaviour is confirmed.

The Samba theory holds. [CVE-2007-2447](https://nvd.nist.gov/vuln/detail/CVE-2007-2447) is command execution through the username map script, on builds where that feature is switched on. The daemon here is privileged, so the impact is code execution as root, with no local account in between. The decision worth keeping is the pairing: version, feature, privilege of the process. The advisory carries the detail.

The compiler service stays on the list as a second door of the same age. One confirmed path is enough to finish the box. The other remains a labelled hypothesis, so the next odd high port is not a surprise. Even if that advisory applies, the account the daemon runs as is its own fact. It is not automatically the Samba result.

## Privilege escalation

Look at the identity before going hunting for a kernel. The SMB daemon is running with enough privilege that the foothold and the top of the box are the same event. That is a finding about the service account. It is not a phase that was skipped.

Had the identity been an ordinary user, this section would be sudo rules, SUID binaries, scheduled tasks, credentials left on disk. The absence of that list is a result. It belongs in the note in one line, so the gap does not look like a forgotten section.

## Lessons

- Banners propose. They do not convict. The FTP version is the example to keep, because it looks worse than the issue that held.
- When several services are old, pick the one you can explain. Leave the others labelled as hypotheses.
- The first question after code execution is which user you landed as. Privilege is a property of the process, and you observe it.
- Report sentence: an outdated Samba service exposed a known command-injection flaw in username handling and was running with administrative privilege, so the single issue was full compromise. Then exposure. Then the fix, which is to patch, not to run that map script, and not to run the daemon as root.

The drill is the hypothesis table, written before a search box is opened. Version, feature, privilege of the process, and what would disprove it.
