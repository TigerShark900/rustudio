// Small CDP driver for the capture rig's Chromium (inside the capture netns).
//
//   node cdp.mjs PORT setcookie        < cookie   (value on stdin, never printed)
//   node cdp.mjs PORT tabs
//   node cdp.mjs PORT js    URLPART JS            (Runtime.evaluate in the first tab whose url contains URLPART)
//   node cdp.mjs PORT shot  URLPART OUT.png
//   node cdp.mjs PORT open  URL
//
// Output never includes cookie values: `js` results are cut to 600 chars and
// any .ROBLOSECURITY-looking text is replaced.
const [port, cmd, ...args] = process.argv.slice(2);
const base = `http://127.0.0.1:${port}`;
const redact = s => String(s).replace(/_\|WARNING:-DO-NOT-SHARE-THIS[^"'\s;]*/g, '<redacted>');

function session(url) {
  const ws = new WebSocket(url);
  let id = 0;
  const send = (method, params = {}) => new Promise((res, rej) => {
    const my = ++id;
    const on = ev => {
      const m = JSON.parse(ev.data);
      if (m.id === my) { ws.removeEventListener('message', on); m.error ? rej(new Error(m.error.message)) : res(m.result); }
    };
    ws.addEventListener('message', on);
    ws.send(JSON.stringify({ id: my, method, params }));
  });
  return { ws, send, open: new Promise(r => ws.addEventListener('open', r)) };
}
async function tab(part) {
  const list = await (await fetch(`${base}/json/list`)).json();
  const t = list.find(t => t.type === 'page' && (!part || t.url.includes(part)));
  if (!t) throw new Error(`no tab matching ${part}`);
  const s = session(t.webSocketDebuggerUrl);
  await s.open;
  return s;
}

if (cmd === 'setcookie') {
  let raw = '';
  for await (const c of process.stdin) raw += c;
  const value = raw.trim();
  raw = '';
  const s = await tab('');
  const r = await s.send('Network.setCookie', {
    name: '.ROBLOSECURITY', value, domain: '.roblox.com', path: '/', secure: true, httpOnly: true,
    sameSite: 'Lax', expires: Math.floor(Date.now() / 1000) + 30 * 24 * 3600,
  });
  console.log('cookie set:', r.success);
  await s.send('Page.navigate', { url: 'https://www.roblox.com/home' });
  await new Promise(r => setTimeout(r, 5000));
  const who = await s.send('Runtime.evaluate', {
    expression: "fetch('https://users.roblox.com/v1/users/authenticated',{credentials:'include'}).then(r=>r.json()).then(j=>j.name||JSON.stringify(j))",
    awaitPromise: true,
  });
  console.log('signed in as:', who.result.value);
  s.ws.close();
} else if (cmd === 'cookieonly') {
  // set the session cookie in the tab matching args[0] without navigating (value on stdin, never printed)
  let raw = '';
  for await (const c of process.stdin) raw += c;
  const value = raw.trim();
  raw = '';
  const s = await tab(args[0]);
  const r = await s.send('Network.setCookie', {
    name: '.ROBLOSECURITY', value, domain: '.roblox.com', path: '/', secure: true, httpOnly: true,
    sameSite: 'Lax', expires: Math.floor(Date.now() / 1000) + 30 * 24 * 3600,
  });
  console.log('cookie set:', r.success);
  s.ws.close();
} else if (cmd === 'follow') {
  // navigate the tab matching args[0] to its own ?returnUrl= (no page JS; the URL is never printed)
  const list = await (await fetch(`${base}/json/list`)).json();
  const t = list.find(t => t.type === 'page' && t.url.includes(args[0]));
  const u = new URL(t.url);
  const ret = u.searchParams.get('returnUrl') || u.searchParams.get('ReturnUrl');
  const s = session(t.webSocketDebuggerUrl);
  await s.open;
  const r = await s.send('Page.navigate', { url: ret });
  console.log('navigated to', new URL(ret).host + new URL(ret).pathname, r.errorText || 'ok');
  s.ws.close();
} else if (cmd === 'authorize') {
  // Studio's browser login in the tab matching args[0]: click through the consent buttons, catch the
  // roblox-studio-auth: redirect (headless Chromium can't hand custom schemes to the system) and give it to
  // the rig's xdg-open. The redirect carries a one-time code: it is never printed.
  const s = await tab(args[0]);
  await s.send('Page.enable');
  await s.send('Network.enable');
  let got = null;
  s.ws.addEventListener('message', ev => {
    const m = JSON.parse(ev.data);
    const u = m.params?.url || m.params?.request?.url || m.params?.frame?.url || '';
    if (!got && u.startsWith('roblox-studio-auth:')) got = u;
  });
  // Never 'Agree': accepting terms is the account holder's own click. Waits args[1] seconds (default 30).
  const steps = Math.ceil((Number(args[1]) || 30) / 2.5);
  const clickJs = `(() => { const want = ['Continue', 'Authorize', 'Confirm', 'Allow', 'Log In'];
    for (const b of document.querySelectorAll('button, a[role=button], input[type=submit]')) {
      const t = (b.innerText || b.value || '').trim();
      if (want.some(w => t === w || t.startsWith(w)) && !b.disabled) { b.click(); return 'clicked ' + t; } }
    return 'no button'; })()`;
  let last = '';
  for (let i = 0; i < steps && !got; i++) {
    const r = await s.send('Runtime.evaluate', { expression: clickJs, returnByValue: true }).catch(e => ({ result: { value: String(e) } }));
    const v = String(r.result?.value);
    if (v !== last) console.log(new Date().toISOString().slice(11, 19), 'step', i, v);
    last = v;
    await new Promise(r => setTimeout(r, 2500));
  }
  if (!got) { console.log('no roblox-studio-auth redirect seen'); process.exit(1); }
  console.log('caught roblox-studio-auth redirect; handing to xdg-open');
  const { spawn } = await import('node:child_process');
  spawn('xdg-open', [got], { stdio: 'ignore', detached: true }).unref();
  got = null;
  s.ws.close();
} else if (cmd === 'handoff') {
  // find a roblox-studio-auth: URL in the tab matching args[0] (links, meta refresh, scripts, page HTML) and
  // hand it to the rig's xdg-open. Never printed.
  const s = await tab(args[0]);
  const r = await s.send('Runtime.evaluate', { returnByValue: true, expression: `(() => {
    const re = /roblox-studio-auth:[^"'<>\\s]+/;
    for (const a of document.querySelectorAll('a[href]')) if (a.href.startsWith('roblox-studio-auth:')) return a.href;
    const m = document.documentElement.outerHTML.match(re);
    return m ? m[0].replace(/&amp;/g, '&') : '';
  })()` });
  let u = r.result?.value || '';
  if (!u) { console.log('no roblox-studio-auth URL in the page'); process.exit(1); }
  console.log('found roblox-studio-auth URL (' + u.length + ' chars); handing to xdg-open');
  const { spawn } = await import('node:child_process');
  spawn('xdg-open', [u], { stdio: 'ignore', detached: true }).unref();
  u = '';
  s.ws.close();
} else if (cmd === 'catchauth') {
  // browser-wide: intercept roblox.com responses, find a roblox-studio-auth: location (JSON body or Location
  // header), hand it to the rig's xdg-open, then exit. Runs args[0] seconds (default 600). Never printed.
  const ver = await (await fetch(`${base}/json/version`)).json();
  const b = session(ver.webSocketDebuggerUrl);
  await b.open;
  const { spawn } = await import('node:child_process');
  let done = false;
  const re = /roblox-studio-auth:[^"'<>\s\\]+/;
  b.ws.addEventListener('message', async ev => {
    const m = JSON.parse(ev.data);
    if (m.method !== 'Fetch.requestPaused') return;
    const p = m.params;
    let found = '';
    try {
      for (const h of p.responseHeaders || []) if (/^location$/i.test(h.name) && h.value.startsWith('roblox-studio-auth:')) found = h.value;
      if (!found && p.responseStatusCode) {
        const body = await b.send('Fetch.getResponseBody', { requestId: p.requestId });
        const text = body.base64Encoded ? Buffer.from(body.body, 'base64').toString() : body.body;
        const mm = text.match(re);
        if (mm) found = mm[0].replace(/\\u0026/g, '&');
      }
    } catch (e) { /* bodies of some responses are unavailable */ }
    await b.send('Fetch.continueRequest', { requestId: p.requestId }).catch(() => {});
    if (found && !done) {
      done = true;
      console.log(new Date().toISOString().slice(11, 19), 'caught roblox-studio-auth location from', new URL(p.request.url).host + new URL(p.request.url).pathname, '-> xdg-open');
      spawn('xdg-open', [found], { stdio: 'ignore', detached: true }).unref();
      found = '';
      setTimeout(() => process.exit(0), 1000);
    }
  });
  await b.send('Fetch.enable', { patterns: [{ urlPattern: '*roblox.com*', requestStage: 'Response' }] });
  console.log('watching for the roblox-studio-auth redirect');
  await new Promise(r => setTimeout(r, (Number(args[0]) || 600) * 1000));
  console.log('timed out');
  process.exit(1);
} else if (cmd === 'tabs') {
  const list = await (await fetch(`${base}/json/list`)).json();
  for (const t of list) console.log(t.type, redact(t.url).slice(0, 200), '|', t.title.slice(0, 80));
} else if (cmd === 'js') {
  const s = await tab(args[0]);
  const r = await s.send('Runtime.evaluate', { expression: args[1], awaitPromise: true, returnByValue: true });
  console.log(redact(JSON.stringify(r.result.value ?? r.result.description ?? r)).slice(0, 600));
  s.ws.close();
} else if (cmd === 'shot') {
  const s = await tab(args[0]);
  const r = await s.send('Page.captureScreenshot', { format: 'png' });
  (await import('node:fs')).writeFileSync(args[1], Buffer.from(r.data, 'base64'));
  console.log('saved', args[1]);
  s.ws.close();
} else if (cmd === 'open') {
  // Target.createTarget keeps the whole URL (/json/new?URL cuts it at the first '&')
  const ver = await (await fetch(`${base}/json/version`)).json();
  const b = session(ver.webSocketDebuggerUrl);
  await b.open;
  const r = await b.send('Target.createTarget', { url: args[0] });
  console.log('opened tab', r.targetId ? 'ok' : 'failed');
  b.ws.close();
} else {
  console.error('usage: see header');
  process.exit(2);
}
process.exit(0);
