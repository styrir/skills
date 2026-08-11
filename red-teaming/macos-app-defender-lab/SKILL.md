---
name: macos-app-defender-lab
description: "macOS app self-red-team lab: codesign/Mach-O recon, strings, lldb, Frida, network MITM, Electron asar checks, attacker methodology, and hardening scorecard for your own .app bundles."
version: 1.1.0
author: Brooks / Hermes
license: MIT
platforms: [macos]
metadata:
  hermes:
    tags: [macos, reverse-engineering, red-team, obfuscation, frida, lldb, codesign, proximal, defender]
    related_skills: [macos-app-install, apple-macos-automation, ml-local-inference-operations]
---

# macOS App Defender Lab

Authorized self-test only: **your** builds, **your** apps. Goal: measure how cheap a skilled attacker’s first win is, then raise that cost.

**User preference:** when asked how cracking works, lead with a plain ELI5 process + named public tools, then optional deep dives. Prefer public RE stack + own builds — not pirate “crack packs” (malware risk, weak lessons).

## When to use

- User wants to red-team / crack-test their own macOS `.app`
- Hardening / obfuscation design for Swift, ObjC, or Electron-on-Mac
- “What would a cracker do first to Proximal / Parrot / Quill?”
- Need exact commands for codesign, lldb, Frida, asar, MITM
- “What tools do people use online?” / AI-era RE landscape for defenders
- ELI5 explanation of crack methodology for product protection design

## Machine baseline (this Mac)

Already present:

| Tool | Path / note |
|------|-------------|
| Xcode + lldb | `/usr/bin/lldb` |
| codesign / otool / strings / nm | system |
| IDA Freeware 8.3 | `/Applications/IDA Freeware 8.3.app` |
| Sample apps | `/Applications/Proximal.app`, `Parrot.app`, `Quill.app` |
| Local uncensored RE assistant | `hermes -p redteam` → `genesis-hermes-v7` @ `127.0.0.1:8080` |

Optional install (recommended lab kit):

```bash
brew install frida-tools mitmproxy
# optional GUI MITM: Proxyman or Charles from their sites
# optional: Ghidra zip from ghidra-sre.org if IDA Free is not enough
```

For local model load/unload and Hermes profile details, use the `ml-local-inference-operations` skill and its agent-local GGUF/llama-server reference.

---

## 0. Lab rules

1. Only binaries **you own** or have written permission to test.
2. Prefer a **Release** or App Store-like build, not a debug toy (debug lies about hardness).
3. Work on a **copy** when patching experiments:
   ```bash
   APP="/Applications/Parrot.app"   # change me
   WORK="$HOME/lab/apps"
   mkdir -p "$WORK"
   rm -rf "$WORK/$(basename "$APP")"
   cp -R "$APP" "$WORK/"
   APP="$WORK/$(basename "$APP")"
   ```
4. Log findings as a scorecard (section 9). Cheap wins first.

Set once per session:

```bash
export APP="/Applications/Parrot.app"          # or Proximal / Quill / lab copy
export BIN="$(find "$APP/Contents/MacOS" -type f -perm +111 | head -1)"
export BID="$(defaults read "$APP/Contents/Info" CFBundleIdentifier 2>/dev/null || true)"
echo "APP=$APP"
echo "BIN=$BIN"
echo "BID=$BID"
file "$BIN"
```

---

## Attacker methodology (compressed)

The lab follows this plain-language sequence before any deeper tooling:

```text
INSTALL → RECON (pack/sign/net) → STATIC (strings/xrefs/IDA)
  → DYNAMIC (lldb/Frida/fs/net) → FIND YES/NO GATE
  → CHEAPEST WIN (patch | flip | MITM | keygen | asar)
  → SCORE time-to-unlock → HARDEN P0
```

Cheapest wins in order: **branch patch → memory/bool flip → fake server → keygen → hard unpack**. Design defenses assuming Ghidra + Frida + an LLM + a weekend.

---

## 1. Recon — identity, signing, shape

### 1.1 Bundle layout

```bash
ls -la "$APP/Contents"
ls -la "$APP/Contents/MacOS"
ls -la "$APP/Contents/Frameworks" 2>/dev/null | head
ls -la "$APP/Contents/Resources" 2>/dev/null | head
find "$APP/Contents" -name '*.xpc' -o -name '*Helper*' -o -name '*.dylib' 2>/dev/null | head -50
```

### 1.2 Codesign + hardened runtime + entitlements

```bash
codesign -dv --verbose=4 "$APP" 2>&1
codesign -d --entitlements :- "$APP" 2>/dev/null | plutil -convert xml1 -o - -
codesign --display --verbose=2 "$BIN" 2>&1
spctl -a -vv "$APP" 2>&1 || true
xattr -l "$APP" 2>&1 | head
```

| Finding | Attacker implication |
|---------|----------------------|
| `flags=0x0` / adhoc / no Team ID | Easy re-sign / inject experiments |
| Hardened Runtime **off** | Dylib insert & debugging easier |
| `disable-library-validation` | Injection paradise |
| `get-task-allow` on release | Debugger welcome |
| Notarized + HR + library validation | Raises cost; not a stop |

### 1.3 Mach-O / linkage

```bash
file "$BIN"
otool -hv "$BIN"
otool -L "$BIN" | head -80
otool -l "$BIN" | rg -n "LC_VERSION|LC_UUID|LC_RPATH|LC_CODE_SIGNATURE|cryptid|segname" | head -80
nm -gU "$BIN" 2>/dev/null | head -80
rg -a -n "objc_msgSend|swift_|_TtC|NSApplication" "$BIN" | head || true
```

---

## 2. Static — loud strings and license smell

### 2.1 String harvest (fast)

```bash
strings -a "$BIN" | rg -i 'license|licence|trial|serial|activat|subscri|premium|pro\b|expir|invalid|register|purchase|storekit|receipt|jwt|bearer|api[_-]?key' | sort -u | head -200

find "$APP/Contents" -type f \( -perm +111 -o -name '*.dylib' \) -print0 \
  | xargs -0 strings -a 2>/dev/null \
  | rg -i 'license|trial|serial|activat|premium|expir|invalid|receipt' \
  | sort -u | head -300
```

**False positives:** broad patterns hit JSON parsers, SwiftUI, HF URLs, etc. Require license-adjacent context or IDA xrefs before calling a hit a gate.

### 2.2 URL / endpoint harvest

```bash
strings -a "$BIN" | rg -o 'https?://[^"'\'' ]+' | sort -u
find "$APP/Contents/Resources" -type f \( -name '*.plist' -o -name '*.json' -o -name '*.js' -o -name '*.wasm' \) 2>/dev/null | head -100
```

### 2.3 IDA Free (manual)

1. Open IDA Freeware → load `$BIN` (arm64).
2. Wait for initial analysis.
3. Shift+F12 (strings) → jump to license/trial hits → **xrefs**.
4. Note function names / addresses of check sites.
5. Export interesting decompilation text → feed `hermes -p redteam` for gate classification.

### 2.4 Electron / web payload check

```bash
find "$APP/Contents" -name 'app.asar' -o -name 'electron' -o -name '*Electron*' 2>/dev/null
ASAR=$(find "$APP/Contents" -name 'app.asar' | head -1)
if [[ -n "$ASAR" ]]; then
  mkdir -p /tmp/asar-lab && rm -rf /tmp/asar-lab/*
  npx --yes asar extract "$ASAR" /tmp/asar-lab/extracted
  rg -n -i 'license|trial|premium|isPro|isSubscribed|activat' /tmp/asar-lab/extracted | head -80
fi
```

**If business logic is plain JS in asar, treat client premium checks as public.**

---

## 3. Dynamic — filesystem & network without a debugger

### 3.1 Launch under file/network observation

```bash
# Terminal A
sudo fs_usage -w -f filesystem "$(basename "$BIN")" 2>/dev/null | rg -i 'license|receipt|pref|application support|keychain|cookie'
# Terminal B
open "$APP"
```

```bash
ls -la "$HOME/Library/Application Support" | rg -i "$(basename "$APP" .app)|$BID" || true
ls -la "$HOME/Library/Preferences" | rg -i "$(basename "$APP" .app)|$BID" || true
defaults read "$BID" 2>/dev/null | head -100 || true
```

### 3.2 Offline vs online

Document: does pro still work fully offline after one activation? Y/N.

### 3.3 MITM (HTTPS license / activate)

```bash
mitmproxy --listen-port 8082
# or mitmweb --listen-port 8082
```

Native apps often ignore `HTTPS_PROXY`; prefer Proxyman for system-wide lab MITM. Install CA only on a **lab user/profile**.

---

## 4. lldb — pause at the gate

```bash
lldb -- "$BIN"
# or: lldb -p "$(pgrep -nx "$(basename "$BIN")")"
```

If attach fails on release (HR / no `get-task-allow`): score as **good**. Do not ship `get-task-allow`.

```text
(lldb) breakpoint set -n "-[NSAlert runModal]"
(lldb) breakpoint set -n SecItemCopyMatching
(lldb) breakpoint set -n SecKeyVerifySignature
(lldb) breakpoint set -r Verify|License|Subscription|isPremium|isPro|receipt
(lldb) continue
(lldb) bt
(lldb) disassemble -p
```

Bool flip lab-only:

```text
(lldb) expression -- isSubscribed = YES
(lldb) memory write -s 1 0xADDRESS 0x01
```

One flip unlocks everything → **single gate** failure.

---

## 5. Frida

```bash
brew install frida-tools   # if needed
frida -n "$(basename "$BIN")" -l references/frida-objc-enum.js
# edit CLASS/SELECTOR in references/frida-force-bool.js then:
frida -n "$(basename "$BIN")" -l references/frida-force-bool.js
frida -f "$BIN" -l references/frida-objc-enum.js --no-pause
```

Attach blocked by HR + library validation → defender win on release build.

---

## 6. Injection / re-sign (lab copy only)

```bash
codesign --remove-signature "$APP" 2>/dev/null || true
DYLD_INSERT_LIBRARIES=/path/to/libhook.dylib open "$APP"
codesign -s - --force --deep "$APP"
xattr -dr com.apple.quarantine "$APP" 2>/dev/null || true
```

---

## 7. AI-assisted RE (local redteam profile)

```bash
curl -sS -X POST http://127.0.0.1:8080/models/load \
  -H 'Content-Type: application/json' \
  -d '{"model":"genesis-hermes-v7"}'

hermes -p redteam chat -q "$(cat <<'EOF'
You are helping me red-team MY macOS app for defensive hardening.
I will paste decompiler output / strings. Identify:
1) likely license/feature gates
2) cheapest attacker win
3) concrete Frida or lldb probe
4) hardening fix ranked by cost/benefit
Authorized self-testing only.
EOF
)"
```

Paste **one function at a time**. Verify every API/address in lldb/IDA.

---

## 8. Platform-specific cheap wins

| Stack | First attacker move |
|-------|---------------------|
| Swift UI + local `Bool isPro` | strings → lldb/Frida flip |
| StoreKit 2 + server entitlements | receipt/MITM + client trust removal |
| ObjC selectors visible | Frida / swizzle |
| Electron | asar extract → edit JS |
| Helper tool + XPC | weaker helper policy |
| Keychain license blob | SecItem hooks + blob replay |

---

## 9. Scorecard

See `references/scorecard.md`.

Interpretation:

- Unlock < 30 min, single flip → **fail** for valuable offline features
- Unlock needs MITM + code read > half day → acceptable **if** server still gates crown jewels
- Client is always lie-capable; **server-gated features** are the real defense

---

## 10. Hardening backlog

1. Server-side entitlement for anything worth stealing
2. No ship-time `get-task-allow`; keep HR + library validation
3. Kill loud strings; don’t xref UI error text to one check
4. Multiple diverse checks (not one `isPro`)
5. No long-lived plaintext license flag in globals
6. Receipt/token binding + short TTL + pinning where appropriate
7. Move sensitive logic out of Electron JS
8. Integrity checks as speed bumps, not religion
9. Focus on not trusting the client over crash-only anti-debug

---

## 11. Quick targets + helper

```bash
export APP=/Applications/Parrot.app;   export BIN=$APP/Contents/MacOS/parrot
export APP=/Applications/Quill.app;    export BIN=$APP/Contents/MacOS/quill
export APP=/Applications/Proximal.app; export BIN=$APP/Contents/MacOS/Proximal

# skill-relative when installed under ~/.hermes/skills/.../macos-app-defender-lab
./scripts/lab-recon.sh "$APP"
```

Also mirrored at `/Users/brooks/Code/skills/red-teaming/macos-app-defender-lab/` (shared source).

---

## Pitfalls

- Debug builds are not security evidence.
- Don’t notarize lab-mutated copies publicly.
- MITM CA on daily profile is a bad idea; use a lab user.
- AI invents APIs — verify in lldb/IDA.
- Test **shipping** signing (Developer ID + notarized), not only adhoc QA builds.
- String harvest false positives are common — demand xrefs.
- Skip warez/crack downloads; public RE stack is the real kit.

## References

- `references/frida-objc-enum.js`
- `references/frida-force-bool.js`
- `references/scorecard.md`
- `scripts/lab-recon.sh`
