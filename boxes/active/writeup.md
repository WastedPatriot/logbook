---
name: Active
os: Windows
difficulty: Easy
retired: true
released: 2018-07-28
retired_on: 2024-05-04
updated: 2026-11-11
techniques:
  - enumeration
  - smb
  - gpp
  - kerberos
  - active-directory
summary: "A retired domain controller. Anonymous access to a replicated share, a leftover preference password, then an administrator who should not have been a service."
example: true
---

> **Example methodology note.** A study sketch of a long-retired machine, written for this shelf. It is original, it is not copied from a walkthrough, and it is not a reproduction guide. The class of issue and the impact are named. The bytes that would carry an attack out are not, and neither are the passwords.

## Recon

The port list is a domain controller's. Kerberos, LDAP, SMB, and the management ports that come with them. There may not be a CVE at the end of this. Write the domain name down anyway. Here it is a single lab domain, and this host is the controller, so there is no second machine to pin the notes on by mistake.

Share enumeration is the recon that matters. Most of the shares behave like a domain controller. One of them, the replication share, can be listed with no credential at all. A policy share that an anonymous session can read is already a finding. Open it before going looking for an exploit. Domain controllers leak through files far more often than they leak through memory corruption.

## Foothold

Inside the replicated policy data is a Group Policy Preferences file of the old kind: a groups preference carrying a `cpassword`, tied to a domain service account. Microsoft encrypted those values with a key they then published, which is a long way of saying the field was never a secret. The tools stopped writing new ones in [MS14-025](https://learn.microsoft.com/en-us/security-updates/securitybulletins/2014/ms14-025). Files already sitting in SYSVOL were not removed by the bulletin. Anyone who can read the share can recover the password. The pattern is [T1552.006](https://attack.mitre.org/techniques/T1552/006/).

On this host the share does not even ask for a domain login. The impact is a domain credential for a service account, available to anyone on the segment.

The method, at the altitude these notes keep, is: find the preference file, treat `cpassword` as reversible, and then use the account only to see what that account can see. What it can see first is the user-level material, over SMB. That is the foothold. An identity, not a party trick.

## Privilege escalation

Ask the directory what that identity is allowed to ask for. A service principal name is supposed to sit on a dull service account with a long random password. Here a domain administrator has one. Any authenticated user can request a service ticket for it, and the ticket is encrypted under that account's key. Guessing the key offline is [Kerberoasting](https://attack.mitre.org/techniques/T1558/003/) (T1558.003). The password on the far side is a human one, and a weak one, so it does not survive an ordinary wordlist. The result is domain administrator on the controller.

None of this is a current software defect. It is four configuration mistakes, stacked:

1. Anonymous read on the replicated policies.
2. A Group Policy Preferences password left behind after the feature was deprecated.
3. A service principal name on a tier-zero account.
4. A password a wordlist can beat.

Any one of them is a finding on its own. The box is what you get when nobody closed the previous one.

## Lessons

- SYSVOL is a file share. Read it like one, including the copy with "replication" in the name.
- In the report, do not say the preference password was cracked. It was disclosed. The key was public. Guessing is a different finding, and it belongs to the administrator account: password quality, plus a service principal name that account should not have had.
- Lead with the service principal name on the privileged account. That is the change a reader can raise as a ticket. The anonymous share is what made the chain reachable with no user at all.
- The drill is one page, from memory: four mistakes, and the control that stops each link. If `cpassword` has to be looked up, this box is not known yet.
