// Enumerate ObjC classes/methods that look license/subscription related.
// Usage: frida -n <process> -l frida-objc-enum.js
//    or: frida -f /path/to/binary -l frida-objc-enum.js --no-pause

'use strict';

const PAT = /license|licence|trial|serial|activat|subscri|premium|purchase|receipt|entitlement|billing|paywall|isPro|isPaid|unlock/i;

function safeStr(s) {
  try { return String(s); } catch (_) { return ''; }
}

if (!ObjC.available) {
  console.log('[!] ObjC runtime not available (pure Swift UI-only or non-Apple binary). Try Swift hooking or lldb.');
} else {
  console.log('[*] ObjC available — scanning classes…');
  let hits = 0;
  for (const name of Object.keys(ObjC.classes)) {
    if (!PAT.test(name)) continue;
    const cls = ObjC.classes[name];
    console.log('\n[class] ' + name);
    try {
      const methods = cls.$ownMethods;
      for (let i = 0; i < methods.length; i++) {
        const m = methods[i];
        if (PAT.test(m) || true) {
          // print all methods on name-matched classes
          console.log('  ' + m);
          hits++;
        }
      }
    } catch (e) {
      console.log('  (method enum error: ' + e + ')');
    }
  }

  console.log('\n[*] Method-name scan across all classes (slower)…');
  for (const name of Object.keys(ObjC.classes)) {
    try {
      const methods = ObjC.classes[name].$ownMethods;
      for (let i = 0; i < methods.length; i++) {
        const m = methods[i];
        if (PAT.test(m)) {
          console.log('[method] ' + name + ' ' + m);
          hits++;
        }
      }
    } catch (_) {}
  }
  console.log('[*] done, rough hits logged: ' + hits);
}

// Also print exports that look interesting
try {
  const mods = Process.enumerateModules();
  console.log('\n[*] Main module: ' + mods[0].name + ' base=' + mods[0].base);
} catch (_) {}
