// Force a named ObjC method to return YES/true.
// Edit CLASS and SELECTOR before running.
// Usage: frida -n <process> -l frida-force-bool.js
//
// Lab / authorized self-test only.

'use strict';

// === EDIT THESE ===
const CLASS = 'LicenseManager';          // e.g. from frida-objc-enum.js
const SELECTOR = '- isSubscribed';       // must include - or + prefix
const RETURN_YES = true;
// ==================

if (!ObjC.available) {
  console.log('[!] ObjC not available');
} else if (!ObjC.classes[CLASS]) {
  console.log('[!] class not found: ' + CLASS);
  console.log('[*] tip: run frida-objc-enum.js first');
} else {
  const impl = ObjC.classes[CLASS][SELECTOR];
  if (!impl) {
    console.log('[!] selector not found: ' + CLASS + ' ' + SELECTOR);
    console.log('[*] own methods:');
    console.log(ObjC.classes[CLASS].$ownMethods.join('\n'));
  } else {
    Interceptor.attach(impl.implementation, {
      onEnter(args) {
        console.log('[gate] ' + CLASS + ' ' + SELECTOR + ' called');
      },
      onLeave(retval) {
        if (RETURN_YES) {
          retval.replace(new NativePointer(0x1));
          console.log('[gate] forced YES/true');
        }
      }
    });
    console.log('[*] hooked ' + CLASS + ' ' + SELECTOR);
  }
}
