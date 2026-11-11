'use strict';

const fs = require('fs');
const net = require('net');
const path = require('path');

const manifest = JSON.parse(fs.readFileSync(process.env.MANIFEST, 'utf8'));
const evidence = process.env.EVIDENCE;
const origin = manifest.origin;
const assertions = [];
const failures = [];
const css = [];
const pageErrors = [];

const REQUIRED_CASES = [
  "proxy rejects a foreign origin",
  "proxy rejects connect",
  "desktop anonymous dashboard redirects to login",
  "mobile anonymous dashboard redirects to login",
  "desktop anonymous oura redirects to login",
  "mobile anonymous oura redirects to login",
  "desktop anonymous export redirects to login",
  "mobile anonymous export redirects to login",
  "desktop login without csrf is rejected",
  "mobile login without csrf is rejected",
  "desktop anonymous journal redirects to login",
  "mobile anonymous journal redirects to login",
  "desktop wrong password stays signed out",
  "mobile wrong password stays signed out",
  "desktop other user cannot open the owner dashboard",
  "mobile other user cannot open the owner dashboard",
  "desktop other user cannot open an owner record",
  "mobile other user cannot open an owner record",
  "desktop owner signs in",
  "mobile owner signs in",
  "desktop keyboard focus moves",
  "mobile keyboard focus moves",
  "desktop today has no horizontal overflow",
  "mobile today has no horizontal overflow",
  "desktop shows Today",
  "mobile shows Today",
  "desktop shows Journal",
  "mobile shows Journal",
  "desktop shows Progress",
  "mobile shows Progress",
  "desktop shows Diary",
  "desktop shows Plan",
  "desktop shows More",
  "mobile shows More",
  "desktop diary opens",
  "mobile diary opens",
  "desktop diary has no horizontal overflow",
  "mobile diary has no horizontal overflow",
  "desktop plan opens",
  "mobile plan opens",
  "desktop progress opens",
  "mobile progress opens",
  "desktop content security policy",
  "mobile content security policy",
  "desktop steady score",
  "mobile steady score",
  "desktop steady value",
  "mobile steady value",
  "desktop protein bar class",
  "mobile protein bar class",
  "desktop steps bar class",
  "mobile steps bar class",
  "desktop protein bar width",
  "mobile protein bar width",
  "desktop protein chip names the metric",
  "mobile protein chip names the metric",
  "desktop thin bar height",
  "mobile thin bar height",
  "desktop unknown score has no value",
  "mobile unknown score has no value",
  "desktop unknown score text",
  "mobile unknown score text",
  "desktop known zero steps",
  "mobile known zero steps",
  "desktop known zero calories",
  "mobile known zero calories",
  "desktop null steps are not zero",
  "mobile null steps are not zero",
  "desktop missing meal stays missing",
  "mobile missing meal stays missing",
  "desktop null calories stay calories",
  "mobile null calories stay calories",
  "desktop meal calories win",
  "mobile meal calories win",
  "desktop alternatives has no horizontal overflow",
  "mobile alternatives has no horizontal overflow",
  "desktop shows eight of ten",
  "mobile shows eight of ten",
  "desktop shows eight alternative links",
  "mobile shows eight alternative links",
  "desktop derived steps are not selected",
  "mobile derived steps are not selected",
  "desktop omitted alternative stays off the chip",
  "mobile omitted alternative stays off the chip",
  "desktop history link opens omitted alternative",
  "mobile history link opens omitted alternative",
  "desktop competing sleep is not one duration",
  "mobile competing sleep is not one duration",
  "desktop unique sleep states its duration",
  "mobile unique sleep states its duration",
  "desktop headroom copy wraps",
  "mobile headroom copy wraps",
  "desktop mixed class shows personal and test",
  "mobile mixed class shows personal and test",
  "desktop long alternative wraps",
  "mobile long alternative wraps",
  "prior stylesheet color is the fixture marker",
  "nutrition page one omits the oldest row",
  "nutrition history link opens page two",
  "correction page one links older history",
  "correction older link keeps the first revision",
  "long source and device render",
  "escaped device renders",
  "long device wraps",
  "long device has no horizontal overflow",
  "mobile long device has no horizontal overflow",
  "legacy history stays unresolved",
  "legacy inspect link opens",
  "derived history is not a token",
  "hrv method and unit render",
  "excluded controls stay unselected",
  "excluded statuses stay labeled",
  "personal record stays visible without synthetic",
  "synthetic record stays hidden without synthetic",
  "csv preview writes nothing",
  "desktop oura is fail closed",
  "mobile oura is fail closed",
  "desktop oura page hides tokens",
  "mobile oura page hides tokens",
  "desktop oura start requires confirmation",
  "mobile oura start requires confirmation",
  "desktop confirmed oura start stays local",
  "mobile confirmed oura start stays local",
  "desktop oura callback without state fails",
  "mobile oura callback without state fails",
  "desktop export requires confirmation",
  "mobile export requires confirmation",
  "desktop export download saved",
  "mobile export download saved",
  "stylesheet url comes from the page",
  "old stylesheet revalidates with its validator",
  "desktop json preview writes nothing",
  "mobile json preview writes nothing",
  "desktop proposal preview saves nothing",
  "mobile proposal preview saves nothing",
  "desktop proposal text was not stored",
  "mobile proposal text was not stored",
  "desktop intention preview saves nothing",
  "mobile intention preview saves nothing",
  "desktop explicit false observation is saved",
  "mobile explicit false observation is saved",
  "desktop unknown observation stays unknown",
  "mobile unknown observation stays unknown",
  "desktop journal correction replaces the text",
  "mobile journal correction replaces the text",
  "desktop deleted journal text leaves the list",
  "mobile deleted journal text leaves the list",
  "desktop deleted journal detail is not current",
  "mobile deleted journal detail is not current",
  "desktop sms is not set up",
  "mobile sms is not set up",
  "desktop reach out does not send",
  "mobile reach out does not send",
  "new stylesheet request carries the old validator",
  "new stylesheet etag differs",
  "new stylesheet matches the current color",
  "new stylesheet revalidates with its validator",
  "cold stylesheet is an unvalidated 200",
  "desktop logout returns to login",
  "mobile logout returns to login",
  "no page or console errors"
];

function launchBrowser(slot) {
  const { chromium } = require(process.env.PLAYWRIGHT_MODULE);
  return chromium.launch(launchOptions(slot));
}

function sanitizePhaseError(payload) {
  const phases = new Set(['reads', 'preview', 'write', 'cache', 'runner']);
  const source = payload && typeof payload === 'object' ? payload : {};
  const phase = phases.has(source.phase) ? source.phase : 'runner';
  let text = typeof source.error === 'string' && source.error.trim() ? source.error : 'phase failed';
  text = text.split('\n')[0];
  if (text.includes('<')) text = text.split('<')[0];
  text = text.replace(/[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/g, '[redacted]');
  text = text.replace(/\b(password|cookie|token|authorization|secret|session)\b\s*[:=]?\s*\S+/gi, (_, label) => label.toLowerCase() + '=[redacted]');
  text = text.replace(/\b(?:eyJ[A-Za-z0-9_-]{8,}|[A-Fa-f0-9]{32,}|[A-Za-z0-9+/]{40,}={0,2})\b/g, '[redacted]');
  text = text.replace(/\s+/g, ' ').trim().slice(0, 180);
  if (!text) text = 'phase failed';
  return { phase, error: text };
}

function persistPhaseError(phase, error, directory) {
  const message = error && typeof error === 'object' && error.message ? error.message : error;
  const payload = sanitizePhaseError({ phase, error: String(message || 'phase failed') });
  const root = directory || evidence;
  const target = path.join(root, 'phase-error.json');
  if (!fs.existsSync(target)) {
    const temporary = target + '.tmp';
    fs.writeFileSync(temporary, JSON.stringify(payload) + '\n');
    fs.chmodSync(temporary, 0o600);
    fs.renameSync(temporary, target);
    failures.push(payload.phase + ': ' + payload.error);
  }
  return payload;
}

function check(name, ok, detail) {
  assertions.push({ name, ok: Boolean(ok), detail: detail || '' });
  if (!ok) failures.push(name);
}

const CSV_PREVIEW_MESSAGES = [
  'Nothing is saved until you confirm.',
  'No records have been added yet.',
];

function csvPreviewEvidence(parts) {
  const source = parts && typeof parts === 'object' ? parts : {};
  const page = String(source.page || '');
  const stored = String(source.storedCsv || '');
  const hero = String(source.calorieHero || '');
  const url = String(source.detailUrl || '');
  const csvId = String(source.csvId || '');
  const matched = CSV_PREVIEW_MESSAGES.filter(message => page.includes(message));
  return {
    calorie: source.calorie === '1',
    caloriesUsed: !hero.includes('Not used'),
    detail: Boolean(csvId) && url.includes(csvId),
    source: stored.includes('csv:browser-csv'),
    sourceId: stored.includes('browsercsv1'),
    eligible: stored.includes('CSV-ELIGIBLE'),
    previewCopy: matched.length > 0,
    matched,
  };
}

function csvPreviewOk(parts) {
  const evidence = csvPreviewEvidence(parts);
  return evidence.calorie && evidence.caloriesUsed && evidence.detail && evidence.source
    && evidence.sourceId && evidence.eligible && evidence.previewCopy;
}

function csvPreviewDetail(parts) {
  const evidence = csvPreviewEvidence(parts);
  const failed = ['calorie', 'caloriesUsed', 'detail', 'source', 'sourceId', 'eligible', 'previewCopy']
    .filter(name => !evidence[name]);
  if (failed.length) return failed.join(',');
  return 'preview=' + evidence.matched.join('|');
}

function secret(file) {
  return fs.readFileSync(file, 'utf8').trim();
}

function probe(payload) {
  return new Promise((resolve, reject) => {
    const socket = net.connect(Number(process.env.PROXY_PORT), '127.0.0.1', () => socket.write(payload));
    const chunks = [];
    socket.on('data', chunk => chunks.push(chunk));
    socket.on('error', reject);
    socket.on('end', () => resolve(Buffer.concat(chunks).toString('utf8')));
    socket.setTimeout(5000, () => {
      socket.destroy();
      reject(new Error('proxy probe timed out'));
    });
  });
}

async function waitFor(file) {
  const started = Date.now();
  while (!fs.existsSync(file)) {
    if (Date.now() - started > 90000) throw new Error('timed out waiting for ' + path.basename(file));
    await new Promise(resolve => setTimeout(resolve, 200));
  }
}

function sameTarget(url, part) {
  try {
    const path = new URL(url).pathname;
    return part === '/' ? path === '/' : path === part;
  } catch (error) {
    return false;
  }
}

let operation = null;

function beginOperation(name) {
  operation = { name, expected: [] };
}

function expectStatus(part, status) {
  if (!operation) beginOperation('request');
  operation.expected.push({ part, status, seen: false, console: false });
}

function endOperation() {
  if (!operation) return;
  const missed = operation.expected.filter(item => !item.seen);
  if (missed.length) pageErrors.push('missing expected response ' + operation.name);
  operation = null;
}

function watch(page) {
  page.on('pageerror', error => pageErrors.push(String(error)));
  page.on('response', response => {
    if (!operation) return;
    const match = operation.expected.find(item => !item.seen && sameTarget(response.url(), item.part) && response.status() === item.status);
    if (match) match.seen = true;
  });
  page.on('console', message => {
    if (message.type() !== 'error') return;
    const text = message.text();
    const url = (message.location() && message.location().url) || '';
    const status = Number((text.match(/status of (\d+)/) || [])[1] || 0);
    const match = operation && operation.expected.find(item => !item.console && sameTarget(url, item.part) && item.status === status);
    if (text.startsWith('Failed to load resource') && match) {
      match.console = true;
      return;
    }
    pageErrors.push(text);
  });
  page.on('request', request => {
    const host = new URL(request.url()).hostname;
    if (host !== '127.0.0.1') pageErrors.push('foreign request ' + host);
  });
}

function day(name) {
  return origin + '/?day=' + manifest.dates[name] + '&synthetic=1';
}

async function login(page, username, password) {
  await page.goto(origin + '/login/', { waitUntil: 'domcontentloaded' });
  await page.getByLabel('Username').fill(username);
  await page.getByLabel('Password').fill(password);
  await page.getByRole('button', { name: 'Sign in' }).click();
  await page.waitForLoadState('domcontentloaded');
}

async function postForm(page, url, fields) {
  return page.evaluate(async ({ url, fields }) => {
    const cookie = document.cookie.split('; ').find(item => item.startsWith('csrftoken='));
    const token = cookie ? decodeURIComponent(cookie.slice('csrftoken='.length)) : '';
    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded', 'X-CSRFToken': token },
      body: new URLSearchParams(fields).toString(),
    });
    return { status: response.status, text: await response.text() };
  }, { url, fields });
}

async function postJson(page, url, payload) {
  return page.evaluate(async ({ url, payload }) => {
    const cookie = document.cookie.split('; ').find(item => item.startsWith('csrftoken='));
    const token = cookie ? decodeURIComponent(cookie.slice('csrftoken='.length)) : '';
    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': token },
      body: JSON.stringify(payload),
    });
    return { status: response.status, text: await response.text() };
  }, { url, payload });
}

async function overflow(page, name) {
  const box = await page.evaluate(() => ({
    scroll: document.documentElement.scrollWidth,
    inner: document.documentElement.clientWidth,
  }));
  check(name + ' has no horizontal overflow', box.scroll <= box.inner + 1, String(box.scroll) + '/' + String(box.inner));
}

async function screens(page, label) {
  const nav = label === 'desktop' ? '.desktop-nav' : '.bottom-nav';
  await page.setViewportSize(label === 'desktop' ? { width: 1440, height: 1000 } : { width: 390, height: 844 });
  await page.goto(day('positive'), { waitUntil: 'domcontentloaded' });
  await overflow(page, label + ' today');
  for (const name of label === 'desktop'
    ? ['Today', 'Journal', 'Progress', 'Diary', 'Plan', 'More']
    : ['Today', 'Journal', 'Progress', 'More']) {
    check(label + ' shows ' + name, await page.locator(nav).getByRole('link', { name, exact: true }).count() === 1);
  }
  if (label === 'mobile') {
    await page.locator('.bottom-nav').getByRole('link', { name: 'More', exact: true }).click();
    await page.locator('.more-list').getByRole('link', { name: 'Diary', exact: true }).click();
  } else {
    await page.locator('.desktop-nav').getByRole('link', { name: 'Diary', exact: true }).click();
  }
  check(label + ' diary opens', (await page.locator('h1').innerText()).includes('Diary'));
  await overflow(page, label + ' diary');
  if (label === 'mobile') {
    await page.locator('.bottom-nav').getByRole('link', { name: 'More', exact: true }).click();
    await page.locator('.more-list').getByRole('link', { name: 'Plan', exact: true }).click();
  } else {
    await page.locator('.desktop-nav').getByRole('link', { name: 'Plan', exact: true }).click();
  }
  check(label + ' plan opens', (await page.locator('h1').innerText()).includes('Plan'));
  const progressNav = label === 'mobile' ? '.bottom-nav' : '.desktop-nav';
  await page.locator(progressNav).getByRole('link', { name: 'Progress', exact: true }).click();
  check(label + ' progress opens', (await page.locator('h1').innerText()).includes('Progress'));
  const response = await page.goto(day('positive'), { waitUntil: 'domcontentloaded' });
  const policy = response.headers()['content-security-policy'] || '';
  check(label + ' content security policy', policy.includes("default-src 'self'") && !policy.includes('unsafe-inline'));
  check(label + ' steady score', (await page.locator('.headroom-status').innerText()).trim() === 'Steady');
  const steady = page.getByRole('progressbar', { name: 'Headspace Daily State' });
  check(label + ' steady value', (await steady.getAttribute('aria-valuenow')) === '70');
  const protein = page.locator('.metric-chip', { has: page.locator('.chip-label', { hasText: 'Protein' }) }).locator('.goal-bar > span');
  const steps = page.locator('.metric-chip', { has: page.locator('.chip-label', { hasText: 'Steps' }) }).locator('.goal-bar > span');
  check(label + ' protein bar class', ((await protein.getAttribute('class')) || '').includes('w-50'));
  const stepsBox = await steps.evaluate(element => ({
    bar: element.getBoundingClientRect().width,
    track: element.parentElement.getBoundingClientRect().width,
    label: element.parentElement.getAttribute('aria-label'),
  }));
  check(label + ' steps bar class', ((await steps.getAttribute('class')) || '').includes('w-80') && Math.abs(stepsBox.bar - stepsBox.track * 0.8) <= 2 && stepsBox.label === 'Steps', JSON.stringify(stepsBox));
  const proteinBox = await protein.evaluate(element => ({
    bar: element.getBoundingClientRect().width,
    track: element.parentElement.getBoundingClientRect().width,
  }));
  check(label + ' protein bar width', Math.abs(proteinBox.bar - proteinBox.track * 0.5) <= 2, JSON.stringify(proteinBox));
  check(label + ' protein chip names the metric', (await protein.evaluate(element => element.parentElement.getAttribute('aria-label'))) === 'Protein');
  const height = await protein.evaluate(element => element.getBoundingClientRect().height);
  check(label + ' thin bar height', height >= 3 && height <= 5, String(height));
  await page.goto(day('unknown'), { waitUntil: 'domcontentloaded' });
  const unknown = page.getByRole('progressbar', { name: 'Headspace Daily State' });
  check(label + ' unknown score has no value', (await unknown.getAttribute('aria-valuenow')) === null);
  check(label + ' unknown score text', (await unknown.getAttribute('aria-valuetext')) === 'Not enough to score');
  await page.goto(day('zero'), { waitUntil: 'domcontentloaded' });
  const zero = page.locator('.metric-chip', { has: page.locator('.chip-label', { hasText: 'Steps' }) });
  check(label + ' known zero steps', (await zero.locator('.chip-value').innerText()).trim().startsWith('0'));
  const zeroText = (await page.locator('.calorie-hero .hero-value').innerText()).trim().split(/\s+/)[0];
  check(label + ' known zero calories', zeroText === '0');
  await page.goto(day('null_steps'), { waitUntil: 'domcontentloaded' });
  const missing = page.locator('.metric-chip', { has: page.locator('.chip-label', { hasText: 'Steps' }) });
  check(label + ' null steps are not zero', (await missing.locator('.chip-value').innerText()).trim() !== '0');
  await page.goto(day('no_meal'), { waitUntil: 'domcontentloaded' });
  const mealText = (await page.content()).toLowerCase();
  check(label + ' missing meal stays missing', mealText.includes('no meal is logged') && mealText.includes('running low') && mealText.includes('unresolved oura history is not used') && !mealText.includes('short sleep') && !mealText.includes('under half the goal') && !mealText.includes('off-wrist'));
  await page.goto(day('null_food'), { waitUntil: 'domcontentloaded' });
  const nullFood = (await page.content()).toLowerCase();
  check(label + ' null calories stay calories', nullFood.includes('food calories') && !nullFood.includes('no meal is logged'));
  await page.goto(day('meal'), { waitUntil: 'domcontentloaded' });
  check(label + ' meal calories win', (await page.locator('.calorie-hero .hero-value').innerText()).includes('1800'));
  await page.goto(day('ambiguous'), { waitUntil: 'domcontentloaded' });
  await overflow(page, label + ' alternatives');
  const stepChip = page.locator('.metric-chip', { has: page.locator('.chip-label', { hasText: 'Steps' }) });
  check(label + ' shows eight of ten', (await stepChip.innerText()).includes('Showing 8 of 10'));
  check(label + ' shows eight alternative links', await stepChip.locator('.alternative-list a').count() === 8);
  check(label + ' derived steps are not selected', !(await stepChip.innerText()).includes('99999'));
  const hrefs = await stepChip.locator('.alternative-list a').evaluateAll(nodes => nodes.map(node => node.getAttribute('href') || ''));
  const omitted = manifest.step_ids.find(id => !hrefs.some(href => href.includes(id)));
  const chosen = (await stepChip.locator('.chip-value').innerText()).trim();
  check(label + ' omitted alternative stays off the chip', Boolean(omitted) && chosen === '—' && !(await stepChip.innerText()).includes('77771'));
  await stepChip.getByRole('link', { name: 'Activity history' }).click();
  if (omitted) await page.locator('a[href*="' + omitted + '"]').first().click();
  check(label + ' history link opens omitted alternative', Boolean(omitted) && page.url().includes(String(omitted)));
  await page.goto(day('ambiguous'), { waitUntil: 'domcontentloaded' });
  const longWrap = await page.locator('.alternative-list a').first().evaluate(element => getComputedStyle(element).overflowWrap);
  check(label + ' long alternative wraps', longWrap === 'anywhere', longWrap);
  await page.goto(day('sleep'), { waitUntil: 'domcontentloaded' });
  const bothSleep = (await page.content()).toLowerCase();
  await page.goto(origin + '/?day=' + manifest.dates.sleep, { waitUntil: 'domcontentloaded' });
  const personalSleep = (await page.content()).toLowerCase();
  check(label + ' competing sleep is not one duration', !bothSleep.includes('5 hours') && !bothSleep.includes('8 hours') && personalSleep.includes('short sleep from desk is 5 hours') && !personalSleep.includes('watch'));
  await page.goto(origin + '/summaries/recovery/' + manifest.unique_sleep_id + '/', { waitUntil: 'domcontentloaded' });
  const sleepDetail = await page.locator('body').innerText();
  check(label + ' unique sleep states its duration', sleepDetail.includes('420') && sleepDetail.includes('min') && !sleepDetail.toLowerCase().includes('7 hours'));
  await page.goto(day('short_sleep'), { waitUntil: 'domcontentloaded' });
  const headroom = page.locator('section[aria-label="Headspace"]');
  const disclosure = headroom.locator('details.fold');
  await disclosure.locator('summary', { hasText: 'Details' }).click();
  const open = await disclosure.evaluate(element => element.open === true);
  const copy = disclosure.locator('.headroom-copy').first();
  const copyVisible = await copy.isVisible();
  const headroomText = (await headroom.innerText()).toLowerCase();
  const wrap = await copy.evaluate(element => getComputedStyle(element).overflowWrap);
  const hidden = await headroom.evaluate(element => getComputedStyle(element).overflow);
  check(label + ' headroom copy wraps', open && copyVisible && wrap === 'anywhere' && hidden !== 'hidden' && headroomText.includes(manifest.long_headroom.toLowerCase()), wrap + '/' + hidden + (open ? '/open' : '/closed'));
  await page.goto(day('mixed'), { waitUntil: 'domcontentloaded' });
  const mixed = await page.locator('.metric-chip', { has: page.locator('.chip-label', { hasText: 'Steps' }) }).innerText();
  await page.goto(origin + '/?day=' + manifest.dates.mixed, { waitUntil: 'domcontentloaded' });
  const personalOnly = await page.locator('.metric-chip', { has: page.locator('.chip-label', { hasText: 'Steps' }) }).innerText();
  check(label + ' mixed class shows personal and test', mixed.includes('personal') && mixed.includes('test') && personalOnly.includes('1000') && !personalOnly.includes('2000'));
}

async function access(browser, label) {
  const width = label === 'desktop' ? 1440 : 390;
  const height = label === 'desktop' ? 1000 : 844;
  const owned = await browser.newContext({ serviceWorkers: 'block', viewport: { width, height } });
  const page = await owned.newPage();
  watch(page);
  try {
  await page.goto(origin + '/', { waitUntil: 'domcontentloaded' });
  check(label + ' anonymous dashboard redirects to login', page.url().includes('/login/'));
  await page.goto(origin + '/integrations/oura/', { waitUntil: 'domcontentloaded' });
  check(label + ' anonymous oura redirects to login', page.url().includes('/login/'));
  await page.goto(origin + '/export/', { waitUntil: 'domcontentloaded' });
  check(label + ' anonymous export redirects to login', page.url().includes('/login/'));
  beginOperation(label + ' login csrf');
  expectStatus('/login/', 403);
  const denied = await page.evaluate(async (url) => {
    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: 'username=synthetic-browser-owner&password=not-the-owner-password',
    });
    return { status: response.status, text: await response.text() };
  }, origin + '/login/');
  check(label + ' login without csrf is rejected', denied.status === 403 && !denied.text.includes('proxy rejected'));
  endOperation();
  await page.goto(origin + '/journal/', { waitUntil: 'domcontentloaded' });
  check(label + ' anonymous journal redirects to login', page.url().includes('/login/'));
  await login(page, manifest.owner, 'not-the-owner-password');
  check(label + ' wrong password stays signed out', page.url().includes('/login/') && await page.getByRole('button', { name: 'Sign out' }).count() === 0);
  beginOperation(label + ' other user redirect');
  expectStatus('/', 403);
  await login(page, manifest.other_user, secret(manifest.other_password_file));
  endOperation();
  beginOperation(label + ' other user dashboard');
  expectStatus('/', 403);
  const forbidden = await page.goto(origin + '/', { waitUntil: 'domcontentloaded' });
  const forbiddenText = await page.content();
  check(label + ' other user cannot open the owner dashboard', forbidden.status() === 403 && !forbiddenText.includes(manifest.personal_marker) && !forbiddenText.includes(manifest.token_sentinel));
  endOperation();
  beginOperation(label + ' other user record');
  expectStatus('/summaries/activity/' + manifest.long_id + '/', 403);
  const forbiddenRecord = await page.goto(origin + '/summaries/activity/' + manifest.long_id + '/', { waitUntil: 'domcontentloaded' });
  check(label + ' other user cannot open an owner record', forbiddenRecord.status() === 403 && !(await page.content()).includes(manifest.long_device));
  endOperation();
  await postForm(page, origin + '/logout/', {});
  await login(page, manifest.owner, secret(manifest.owner_password_file));
  check(label + ' owner signs in', await page.getByRole('button', { name: 'Sign out' }).count() === 1);
  await page.keyboard.press('Tab');
  const focused = await page.evaluate(() => document.activeElement ? document.activeElement.tagName : '');
  check(label + ' keyboard focus moves', ['A', 'BUTTON', 'INPUT', 'SELECT', 'TEXTAREA'].includes(focused), focused);
  await integrations(page, label);
  } finally {
    await owned.close();
  }
}

async function integrations(page, label) {
  await page.goto(origin + '/integrations/oura/', { waitUntil: 'domcontentloaded' });
  const oura = await page.content();
  check(label + ' oura is fail closed', oura.includes('Oura is not configured.') && !oura.includes('Connect Oura') && oura.includes('State: disconnected'));
  check(label + ' oura page hides tokens', !oura.includes(manifest.token_sentinel) && !oura.includes(manifest.account_key_sentinel));
  beginOperation(label + ' oura unconfirmed');
  expectStatus('/integrations/oura/start/', 400);
  const unconfirmed = await postForm(page, origin + '/integrations/oura/start/', {});
  check(label + ' oura start requires confirmation', unconfirmed.status === 400 && unconfirmed.text.includes('Confirm Oura access first.'));
  endOperation();
  beginOperation(label + ' oura confirmed');
  expectStatus('/integrations/oura/start/', 409);
  const unavailable = await postForm(page, origin + '/integrations/oura/start/', { confirm_connect: 'yes' });
  check(label + ' confirmed oura start stays local', unavailable.status === 409 && unavailable.text.includes('Oura setup is unavailable:') && !unavailable.text.includes('proxy rejected'));
  endOperation();
  beginOperation(label + ' oura callback');
  expectStatus('/integrations/oura/callback/', 400);
  const callback = await page.goto(origin + '/integrations/oura/callback/', { waitUntil: 'domcontentloaded' });
  check(label + ' oura callback without state fails', callback.status() === 400 && (await page.content()).includes('Oura authorization was not completed'));
  endOperation();
  await page.goto(origin + '/export/', { waitUntil: 'domcontentloaded' });
  beginOperation(label + ' export confirm');
  expectStatus('/export/', 400);
  const quiet = await postForm(page, origin + '/export/', {});
  check(label + ' export requires confirmation', quiet.status === 400 && quiet.text.includes('Confirm the private export first.'));
  endOperation();
  await page.getByRole('checkbox', { name: 'Download my private history to this device' }).check();
  const [download] = await Promise.all([
    page.waitForEvent('download'),
    page.getByRole('button', { name: 'Download private export' }).click(),
  ]);
  const downloadPath = path.join(evidence, 'export-' + label + '.zip');
  await download.saveAs(downloadPath);
  check(label + ' export download saved', fs.existsSync(downloadPath));
  if (label === 'desktop') fs.copyFileSync(downloadPath, path.join(evidence, 'export.zip'));
}

async function readPhase(page, context) {
  const foreign = await probe('GET http://example.invalid/probe HTTP/1.1\r\nHost: example.invalid\r\nConnection: close\r\n\r\n');
  check('proxy rejects a foreign origin', foreign.includes('403'));
  const connect = await probe('CONNECT example.invalid:443 HTTP/1.1\r\nHost: example.invalid:443\r\nConnection: close\r\n\r\n');
  check('proxy rejects connect', connect.includes('403'));
  for (const label of ['desktop', 'mobile']) {
    await access(context.browser(), label);
  }
  await login(page, manifest.owner, secret(manifest.owner_password_file));
  for (const label of ['desktop', 'mobile']) {
    await screens(page, label);
    if (label === 'desktop') {
      await page.goto(day('positive'), { waitUntil: 'domcontentloaded' });
      const priorColor = await page.locator('.headroom-status').evaluate(element => getComputedStyle(element).color);
      check('prior stylesheet color is the fixture marker', priorColor === manifest.prior_style, priorColor);
      const href = await page.locator('link[rel="stylesheet"]').first().getAttribute('href');
      manifest.stylesheet = new URL(href, origin).pathname + new URL(href, origin).search;
      fs.writeFileSync(path.join(evidence, 'stylesheet.json'), JSON.stringify({ path: manifest.stylesheet }));
      check('stylesheet url comes from the page', Boolean(manifest.stylesheet && manifest.stylesheet.includes('/static/') && manifest.stylesheet.includes('app.css')));
    }
  }
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto(origin + '/summaries/nutrition/?synthetic=1', { waitUntil: 'domcontentloaded' });
  const firstPage = await page.content();
  check('nutrition page one omits the oldest row', !firstPage.includes(manifest.page2_label));
  await page.getByRole('link', { name: 'Next' }).click();
  check('nutrition history link opens page two', (await page.content()).includes(manifest.page2_label));
  await page.goto(origin + '/summaries/activity/' + manifest.correction_id + '/', { waitUntil: 'domcontentloaded' });
  check('correction page one links older history', (await page.content()).includes('Older'));
  await page.getByRole('link', { name: 'Older' }).click();
  check('correction older link keeps the first revision', (await page.content()).includes('Revision 1 ·'));
  await page.goto(origin + '/summaries/activity/' + manifest.long_id + '/', { waitUntil: 'domcontentloaded' });
  const detail = await page.content();
  const deviceNode = page.locator('xpath=//dt[normalize-space()="Device"]/following-sibling::dd[1]');
  const deviceText = (await deviceNode.innerText()).trim();
  const deviceHtml = await deviceNode.innerHTML();
  check('long source and device render', detail.includes(manifest.long_source) && deviceText === manifest.long_device);
  check('escaped device renders', deviceText === manifest.long_device && deviceHtml.includes('&amp;') && deviceHtml.includes('&lt;') && !deviceHtml.includes('<'));
  const deviceWrap = await deviceNode.evaluate(element => getComputedStyle(element).overflowWrap);
  check('long device wraps', deviceWrap === 'anywhere', deviceWrap);
  await overflow(page, 'long device');
  await page.setViewportSize({ width: 390, height: 844 });
  await overflow(page, 'mobile long device');
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto(origin + '/summaries/provenance/', { waitUntil: 'domcontentloaded' });
  const history = await page.content();
  check('legacy history stays unresolved', history.includes(manifest.legacy_id) && history.includes('imported'));
  check('derived history is not a token', history.includes('Projection unavailable') && !history.includes(manifest.token_sentinel) && !history.includes(manifest.derived_token_sentinel));
  await page.locator('a[href*="' + manifest.legacy_id + '"]', { hasText: 'Inspect original' }).click();
  check('legacy inspect link opens', (await page.locator('h1').innerText()).includes('Original history'));
  await page.goto(origin + '/summaries/recovery/' + manifest.hrv_id + '/', { waitUntil: 'domcontentloaded' });
  const hrv = await page.content();
  await page.goto(origin + '/summaries/recovery/' + manifest.hrv_alt_id + '/', { waitUntil: 'domcontentloaded' });
  const hrvAlt = await page.content();
  check('hrv method and unit render', hrv.includes('RMSSD') && hrv.includes('ms') && hrv.includes('desk') && hrvAlt.includes('SDNN') && hrvAlt.includes('band') && !hrvAlt.includes('RMSSD'));
  await page.goto(day('controls'), { waitUntil: 'domcontentloaded' });
  const controls = await page.locator('.metric-chip', { has: page.locator('.chip-label', { hasText: 'Steps' }) }).innerText();
  check('excluded controls stay unselected', !controls.includes('77771') && !controls.includes('77772') && !controls.includes('77773'));
  await page.goto(origin + '/summaries/provenance/', { waitUntil: 'domcontentloaded' });
  const statuses = await page.content();
  check('excluded statuses stay labeled', statuses.includes('stale') && statuses.includes('conflict') && statuses.includes('invalid'));
  await page.goto(origin + '/summaries/nutrition/' + manifest.personal_id + '/', { waitUntil: 'domcontentloaded' });
  const personal = await page.content();
  check('personal record stays visible without synthetic', personal.includes(manifest.personal_marker) && personal.includes('Stored synthetic flag: false'));
  await page.goto(origin + '/summaries/nutrition/', { waitUntil: 'domcontentloaded' });
  const hidden = !(await page.content()).includes(manifest.synthetic_hidden_id);
  await page.goto(origin + '/summaries/nutrition/?synthetic=1', { waitUntil: 'domcontentloaded' });
  check('synthetic record stays hidden without synthetic', hidden && (await page.content()).includes(manifest.synthetic_hidden_id));
  await page.goto(day('csv'), { waitUntil: 'domcontentloaded' });
  const calorie = (await page.locator('.calorie-hero .hero-value').innerText()).trim().split(/\s+/)[0];
  const calorieHero = await page.locator('.calorie-hero').innerText();
  await page.goto(origin + '/summaries/nutrition/' + manifest.csv_id + '/?synthetic=1', { waitUntil: 'domcontentloaded' });
  const storedCsv = await page.content();
  const detailUrl = page.url();
  await page.goto(origin + '/summaries/import/', { waitUntil: 'domcontentloaded' });
  const header = await page.locator('.csv-header').innerText();
  const csvPath = path.join(evidence, 'preview.csv');
  fs.writeFileSync(csvPath, header + '\nbrowserpreview1,nutrition,' + manifest.dates.personal + ',America/Chicago,partial,true,"{""calories"": 0}",,preview\n');
  await page.locator('input[name="namespace"]').fill('synthetic-summary');
  await page.locator('input[type="file"]').setInputFiles(csvPath);
  await page.getByRole('button', { name: 'Review summaries' }).click();
  const previewPage = await page.content();
  const previewParts = {
    calorie, calorieHero, detailUrl, storedCsv, csvId: manifest.csv_id, page: previewPage,
  };
  check('csv preview writes nothing', csvPreviewOk(previewParts), csvPreviewDetail(previewParts));
  fs.unlinkSync(csvPath);
  const logged = stylesheetLog(manifest.stylesheet);
  const first = logged.find(row => row.status === 200);
  const revalidated = logged.find(row => row.status === 304 && first && row.reqInm === first.etag);
  check('old stylesheet revalidates with its validator', Boolean(first && revalidated && first.etag), JSON.stringify(logged.slice(0, 4)));
}

const savedEntries = {};
function journalText(label, desktop, mobile) {
  return label === 'mobile' ? mobile : desktop;
}

async function journalPreviews(page, label) {
  await page.setViewportSize(label === 'desktop' ? { width: 1440, height: 1000 } : { width: 390, height: 844 });
  await page.goto(origin + '/journal/?synthetic=1', { waitUntil: 'domcontentloaded' });
  const before = await page.locator('article').count();
  const preview = await postJson(page, origin + '/journal/preview/', { body: 'Browser json preview.', proposals: [] });
  const previewBody = JSON.parse(preview.text);
  check(label + ' json preview writes nothing', preview.status === 200 && previewBody.persisted === false && previewBody.silence_is_unknown === true);
  await page.locator('summary', { hasText: 'Add a fact' }).click();
  await page.locator('input[name="local_date"]').fill(manifest.anchor);
  await page.locator('textarea[name="body"]').fill(journalText(label, 'Browser proposal says no.', 'Mobile proposal says no.'));
  await page.locator('select[name="domain_id"]').selectOption('12');
  await page.locator('select[name="metric_key"]').selectOption('explicit_choice');
  await page.locator('select[name="value_state"]').selectOption('observed');
  await page.locator('select[name="boolean"]').selectOption('false');
  await page.locator('select[name="temporal_scope"]').selectOption('completed');
  await page.locator('input[name="support_span"]').fill('says no');
  await page.getByRole('button', { name: 'Check proposal' }).click();
  await page.waitForLoadState('domcontentloaded');
  const proposal = await page.content();
  const saved = proposal.includes('Nothing was saved.');
  const explicitNo = proposal.includes(', no');
  check(label + ' proposal preview saves nothing', saved && explicitNo,
    'saved=' + saved + ' no=' + explicitNo + ' url=' + page.url());
  await page.goto(origin + '/journal/?synthetic=1', { waitUntil: 'domcontentloaded' });
  const stored = await page.locator('article').filter({ hasText: journalText(label, 'Browser proposal says no.', 'Mobile proposal says no.') }).count();
  const afterPreview = await page.locator('article').count();
  check(label + ' proposal text was not stored', stored === 0 && afterPreview === before,
    'stored=' + stored + ' count=' + afterPreview + '/' + before);
  await page.goto(origin + '/journal/?synthetic=1', { waitUntil: 'domcontentloaded' });
  await page.locator('summary', { hasText: 'Add a fact' }).click();
  await page.locator('input[name="local_date"]').fill(manifest.anchor);
  await page.locator('textarea[name="body"]').fill(journalText(label, 'Browser intention stays unsaved.', 'Mobile intention stays unsaved.'));
  await page.locator('select[name="domain_id"]').selectOption('12');
  await page.locator('select[name="metric_key"]').selectOption('explicit_choice');
  await page.locator('select[name="value_state"]').selectOption('intention');
  await page.locator('input[name="support_span"]').fill('stays unsaved');
  await page.locator('select[name="temporal_scope"]').selectOption('intention');
  await page.getByRole('button', { name: 'Check proposal' }).click();
  await page.waitForLoadState('domcontentloaded');
  const intention = await page.locator('section', { has: page.locator('h2', { hasText: 'Proposal check' }) }).innerText();
  check(label + ' intention preview saves nothing', intention.includes('Nothing was saved.') && intention.includes('Ready to save: domain 12, explicit_choice, intention') && !intention.includes('explicit_choice, observed') && !intention.includes('explicit_choice, unknown') && !intention.includes('exact words'));
}

async function journalWrites(page, label) {
  await page.setViewportSize(label === 'desktop' ? { width: 1440, height: 1000 } : { width: 390, height: 844 });
  await page.goto(origin + '/journal/?synthetic=1', { waitUntil: 'domcontentloaded' });
  await page.locator('form.stack-form').evaluate(form => {
    const input = document.createElement('input');
    input.type = 'hidden';
    input.name = 'synthetic';
    input.value = 'on';
    form.appendChild(input);
  });
  await page.locator('summary', { hasText: 'Add a fact' }).click();
  await page.locator('input[name="local_date"]').fill(manifest.anchor);
  const explicitBody = journalText(label, 'Browser explicit false says no.', 'Mobile explicit false says no.');
  const correctedBody = journalText(label, 'Browser explicit false corrected.', 'Mobile explicit false corrected.');
  const unknownBody = journalText(label, 'Browser unknown stays unknown.', 'Mobile unknown stays unknown.');
  await page.locator('textarea[name="body"]').fill(explicitBody);
  await page.locator('select[name="domain_id"]').selectOption('12');
  await page.locator('select[name="metric_key"]').selectOption('explicit_choice');
  await page.locator('select[name="value_state"]').selectOption('observed');
  await page.locator('select[name="boolean"]').selectOption('false');
  await page.locator('input[name="support_span"]').fill('says no');
  await page.getByRole('button', { name: 'Save journal entry' }).click();
  await page.waitForLoadState('domcontentloaded');
  const explicit = (await page.locator('p', { hasText: 'explicit_choice' }).first().innerText()).trim();
  check(label + ' explicit false observation is saved', explicit.includes('explicit_choice') && explicit.endsWith('no'),
    'synthetic=on is added because the new-entry form has no synthetic checkbox');
  savedEntries[label] = page.url();
}

async function journalFinish(page, label) {
  await page.setViewportSize(label === 'desktop' ? { width: 1440, height: 1000 } : { width: 390, height: 844 });
  const correctedBody = journalText(label, 'Browser explicit false corrected.', 'Mobile explicit false corrected.');
  const unknownBody = journalText(label, 'Browser unknown stays unknown.', 'Mobile unknown stays unknown.');
  await page.goto(savedEntries[label], { waitUntil: 'domcontentloaded' });
  await page.locator('textarea[name="body"]').fill(correctedBody);
  await page.getByRole('button', { name: 'Save correction' }).click();
  await page.waitForLoadState('domcontentloaded');
  check(label + ' journal correction replaces the text', (await page.content()).includes(correctedBody));
  const detailUrl = page.url();
  await page.getByRole('checkbox', { name: 'Remove this text from current storage' }).check();
  await page.getByRole('button', { name: 'Delete entry' }).click();
  await page.waitForLoadState('domcontentloaded');
  await page.goto(origin + '/journal/?synthetic=1', { waitUntil: 'domcontentloaded' });
  check(label + ' deleted journal text leaves the list', !(await page.content()).includes(correctedBody));
  beginOperation(label + ' deleted detail');
  expectStatus(new URL(detailUrl).pathname, 404);
  await page.goto(detailUrl, { waitUntil: 'domcontentloaded' });
  check(label + ' deleted journal detail is not current', !(await page.content()).includes(correctedBody));
  endOperation();
  await page.goto(origin + '/journal/?synthetic=1', { waitUntil: 'domcontentloaded' });
  await page.locator('form.stack-form').evaluate(form => {
    const input = document.createElement('input');
    input.type = 'hidden';
    input.name = 'synthetic';
    input.value = 'on';
    form.appendChild(input);
  });
  await page.locator('summary', { hasText: 'Add a fact' }).click();
  await page.locator('input[name="local_date"]').fill(manifest.anchor);
  await page.locator('textarea[name="body"]').fill(unknownBody);
  await page.locator('select[name="domain_id"]').selectOption('12');
  await page.locator('select[name="metric_key"]').selectOption('explicit_choice');
  await page.locator('select[name="value_state"]').selectOption('unknown');
  await page.getByRole('button', { name: 'Save journal entry' }).click();
  await page.waitForLoadState('domcontentloaded');
  const unknownFact = await page.content();
  check(label + ' unknown observation stays unknown', unknownFact.includes(unknownBody) && unknownFact.includes('unknown') && !unknownFact.includes('70.00'));

  await page.goto(origin + '/holding/', { waitUntil: 'domcontentloaded' });
  check(label + ' sms is not set up', (await page.content()).includes('The app number is not set up yet.'));
  await page.getByRole('checkbox', { name: 'Select' }).check();
  await page.getByRole('button', { name: 'Reach Out' }).click();
  await page.waitForLoadState('domcontentloaded');
  check(label + ' reach out does not send', (await page.content()).includes('Not sent'));
}

async function cachePhase(page) {
  fs.writeFileSync(path.join(evidence, 'cache-ready.json'), JSON.stringify({ phase: 'revalidated' }));
  await waitFor(path.join(evidence, 'cache-swapped.json'));
  const stylesheet = manifest.stylesheet;
  const proxyLog = path.join(evidence, 'proxy.log');
  const old = stylesheetLog(stylesheet).filter(row => row.status === 200).pop();
  const freshCursor = logCursor(proxyLog);
  await page.goto(day('positive'), { waitUntil: 'domcontentloaded' });
  const color = await page.locator('.headroom-status').evaluate(element => getComputedStyle(element).color);
  const transition = await waitForAppendedStylesheet(proxyLog, stylesheet, freshCursor, row => (
    row.status === 200 && old && row.reqInm === old.etag && row.etag && row.etag !== old.etag
  ), 5000);
  const fresh = transition.found || transition.rows.find(row => row.status === 200);
  check('new stylesheet request carries the old validator', Boolean(old && fresh && fresh.reqInm === old.etag), JSON.stringify(fresh || {}));
  check('new stylesheet etag differs', Boolean(old && fresh && fresh.etag && fresh.etag !== old.etag), JSON.stringify({ old: old && old.etag, fresh: fresh && fresh.etag }));
  check('new stylesheet matches the current color', color === manifest.expected_style, color);
  const followCursor = logCursor(proxyLog);
  await page.goto(day('unknown'), { waitUntil: 'domcontentloaded' });
  const followWait = await waitForAppendedStylesheet(proxyLog, stylesheet, followCursor, row => (
    Boolean(fresh) && row.status === 304 && row.reqInm === fresh.etag && row.etag === fresh.etag
  ), 5000);
  const follow = followWait.rows;
  check('new stylesheet revalidates with its validator', Boolean(fresh) && follow.some(row => row.status === 304 && row.reqInm === fresh.etag && row.etag === fresh.etag), JSON.stringify(follow));
  const warmCount = stylesheetLog(stylesheet).filter(row => row.status === 200 && row.etag === fresh.etag).length;
  const coldBrowser = await launchBrowser('cold');
  try {
    const coldContext = await coldBrowser.newContext({ serviceWorkers: 'block', viewport: { width: 1440, height: 1000 } });
    const coldPage = await coldContext.newPage();
    watch(coldPage);
    const coldCursor = logCursor(proxyLog);
    await coldPage.goto(origin + '/login/', { waitUntil: 'domcontentloaded' });
    await waitForAppendedStylesheet(proxyLog, stylesheet, coldCursor, row => (
      Boolean(fresh) && row.status === 200 && row.etag === fresh.etag && !row.reqInm
    ), 5000);
    const cold = stylesheetLog(stylesheet).filter(row => row.status === 200 && row.etag === fresh.etag && !row.reqInm);
    check('cold stylesheet is an unvalidated 200', cold.length >= 1 && stylesheetLog(stylesheet).filter(row => row.status === 200 && row.etag === fresh.etag).length === warmCount + 1);
  } finally {
    await coldBrowser.close();
  }
}

function parseStylesheetLine(line) {
  const parts = line.split(' ');
  const status = Number(parts[3]);
  const field = name => decodeURIComponent(((line.match(new RegExp(name + '=([^ ]*)')) || ['', ''])[1] || ''));
  return { path: parts[2] || '', status, etag: field('etag'), reqInm: field('req_inm'), reqIms: field('req_ims') };
}

function stylesheetRows(text, stylesheet) {
  return text.split('\n').filter(line => line.startsWith('FORWARD')).map(parseStylesheetLine)
    .filter(row => row.path === stylesheet && (row.status === 200 || row.status === 304));
}

function stylesheetLog(stylesheet) {
  return stylesheetRows(fs.readFileSync(path.join(evidence, 'proxy.log'), 'utf8'), stylesheet);
}

function logCursor(file) {
  try {
    const size = fs.statSync(file).size;
    if (!size) return 0;
    const fd = fs.openSync(file, 'r');
    try {
      const last = Buffer.alloc(1);
      fs.readSync(fd, last, 0, 1, size - 1);
      if (last.toString('utf8') === '\n') return size;
      const window = Math.min(size, 8192);
      const offset = size - window;
      const buf = Buffer.alloc(window);
      fs.readSync(fd, buf, 0, window, offset);
      const text = buf.toString('utf8');
      const cut = text.lastIndexOf('\n');
      return cut === -1 ? 0 : offset + Buffer.byteLength(text.slice(0, cut + 1));
    } finally {
      fs.closeSync(fd);
    }
  } catch (error) {
    return 0;
  }
}

function textAfter(file, cursor) {
  let size = 0;
  try {
    size = fs.statSync(file).size;
  } catch (error) {
    return '';
  }
  if (size <= cursor) return '';
  const fd = fs.openSync(file, 'r');
  try {
    const buffer = Buffer.alloc(size - cursor);
    const read = fs.readSync(fd, buffer, 0, buffer.length, cursor);
    let text = buffer.subarray(0, read).toString('utf8');
    if (!text.endsWith('\n')) {
      const cut = text.lastIndexOf('\n');
      text = cut === -1 ? '' : text.slice(0, cut + 1);
    }
    return text;
  } finally {
    fs.closeSync(fd);
  }
}

async function waitForAppendedStylesheet(file, stylesheet, cursor, predicate, timeoutMs) {
  const limit = Number(timeoutMs) > 0 ? Number(timeoutMs) : 5000;
  const started = Date.now();
  let rows = [];
  while (true) {
    rows = stylesheetRows(textAfter(file, cursor), stylesheet);
    const found = rows.find(row => {
      try {
        return Boolean(predicate(row));
      } catch (error) {
        return false;
      }
    }) || null;
    if (found || Date.now() - started >= limit) return { found, rows };
    await new Promise(resolve => setTimeout(resolve, 40));
  }
}

function launchOptions(slot) {
  const launchFile = path.join(evidence, 'launch-' + slot + '.json');
  return {
    executablePath: process.env.CX83_BROWSER_LAUNCHER,
    env: Object.assign({}, process.env, { CX83_LAUNCH_FILE: launchFile }),
    headless: true,
    chromiumSandbox: true,
    args: [
      '--disable-background-networking',
      '--disable-component-update',
      '--disable-domain-reliability',
      '--disable-sync',
      '--no-first-run',
      '--proxy-bypass-list=<-loopback>',
    ],
    proxy: { server: process.env.PROXY_SERVER },
  };
}

async function main() {
  const browser = await launchBrowser('warm');
  const context = await browser.newContext({
    viewport: { width: 1440, height: 1000 },
    serviceWorkers: 'block',
  });
  context.on('response', response => {
    if (response.url().includes('/static/tracking/app.css')) {
      css.push({ url: response.url(), status: response.status(), etag: response.headers().etag || '' });
    }
  });
  const page = await context.newPage();
  watch(page);
  try {
    try {
      await readPhase(page, context);
      fs.writeFileSync(path.join(evidence, 'reads-done.json'), JSON.stringify({ phase: 'reads-done' }));
    } catch (error) {
      persistPhaseError('reads', error);
      throw error;
    }
    await waitFor(path.join(evidence, 'continue.json'));
    try {
      for (const label of ['desktop', 'mobile']) await journalPreviews(page, label);
      fs.writeFileSync(path.join(evidence, 'preview-done.json'), JSON.stringify({ phase: 'preview-done' }));
      await waitFor(path.join(evidence, 'writes-continue.json'));
      for (const label of ['desktop', 'mobile']) await journalWrites(page, label);
      fs.writeFileSync(path.join(evidence, 'false-saved.json'), JSON.stringify({ phase: 'false-saved' }));
      await waitFor(path.join(evidence, 'false-continue.json'));
      for (const label of ['desktop', 'mobile']) await journalFinish(page, label);
    } catch (error) {
      persistPhaseError(fs.existsSync(path.join(evidence, 'preview-done.json')) ? 'write' : 'preview', error);
      throw error;
    }
    try {
      await cachePhase(page);
    } catch (error) {
      persistPhaseError('cache', error);
      throw error;
    }
    for (const label of ['desktop', 'mobile']) {
      await page.setViewportSize(label === 'desktop' ? { width: 1440, height: 1000 } : { width: 390, height: 844 });
      if (label === 'mobile') await login(page, manifest.owner, secret(manifest.owner_password_file));
      await page.goto(origin + '/', { waitUntil: 'domcontentloaded' });
      if (await page.getByRole('button', { name: 'Sign out' }).count()) {
        await page.getByRole('button', { name: 'Sign out' }).click();
        await page.waitForLoadState('domcontentloaded');
      }
      await page.goto(origin + '/journal/', { waitUntil: 'domcontentloaded' });
      check(label + ' logout returns to login', page.url().includes('/login/'));
    }
    const unexpected = pageErrors.filter(Boolean);
    check('no page or console errors', unexpected.length === 0, unexpected.slice(0, 5).join(' | '));
  } finally {
    await browser.close();
  }
  if (process.env.BROWSER_INJECT_FAILURE === 'assertion') {
    check('injected-assertion', false, 'deliberate assertion failure');
  }
  const names = assertions.map(item => item.name);
  const missing = REQUIRED_CASES.filter(name => !names.includes(name));
  const unknown = names.filter(name => name !== 'injected-assertion' && !REQUIRED_CASES.includes(name));
  const duplicate = names.filter((name, index) => names.indexOf(name) !== index);
  if (missing.length || unknown.length || duplicate.length) failures.push('case-inventory');
  const ok = missing.length === 0 && unknown.length === 0 && duplicate.length === 0 && assertions.every(item => item.ok);
  fs.writeFileSync(path.join(evidence, 'results.json'), JSON.stringify({
    ok, assertions, failures,
  }, null, 2));
  if (!ok) process.exitCode = 1;
}

if (require.main === module) {
  main().catch(error => {
    persistPhaseError('runner', error);
    check('runner', false, 'phase failed');
    fs.writeFileSync(path.join(evidence, 'results.json'), JSON.stringify({
      ok: false, assertions, failures,
    }, null, 2));
    process.exitCode = 1;
  });
}

module.exports = {
  sanitizePhaseError, persistPhaseError, logCursor, waitForAppendedStylesheet, csvPreviewOk, csvPreviewDetail,
};
