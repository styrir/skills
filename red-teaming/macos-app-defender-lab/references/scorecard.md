# macOS App Defender Lab — Scorecard

```text
App / version / build:
Date:
Binary path:
Tester:

## Signing & platform
[ ] Signing: adhoc / dev / Developer ID / notarized
[ ] Team ID:
[ ] Hardened Runtime: on/off
[ ] Library validation: on/off
[ ] get-task-allow on RELEASE: yes/no (want no)
[ ] spctl assessment:

## Static
[ ] Loud license/trial strings: count ___
[ ] Strings encrypted / not xref-friendly: yes/no
[ ] URLs / activate endpoints found:
[ ] Electron asar business logic: yes/no/n/a
[ ] Extra helpers/XPC/dylibs:

## Dynamic
[ ] Debugger attach on release: yes/no
[ ] Frida attach on release: yes/no
[ ] Single memory/feature bool: yes/no
[ ] Offline full pro after one activation: yes/no
[ ] HTTPS activate spoofable (no pin): yes/no
[ ] Keychain/prefs license blob obvious: yes/no

## Outcome
Time to first unlock: ___ minutes
First unlock method: strings | lldb flip | frida | mitm | asar | patch | other
Notes:

## Fixes
P0 (this week):
P1 (this month):
P2 (backlog):

## Pass bar (shipping paid features)
- [ ] No single client-side bool unlocks crown jewels
- [ ] Server gates valuable capability
- [ ] Release has HR + no get-task-allow
- [ ] Skilled self-test > 4 hours to stable offline unlock OR unlock is useless without server
```
