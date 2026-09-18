// Daily 24h GHL status for Orkay India + International. Node 18+, no deps.
// Usage: node report.mjs [hours=24]   → prints markdown + writes reports/YYYY-MM-DD.md
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const DIR = dirname(fileURLToPath(import.meta.url));
// .env file locally; real environment variables (cloud routine / CI) win
let envFile = '';
try { envFile = readFileSync(join(DIR, '.env'), 'utf8'); } catch {}
const env = { ...Object.fromEntries(envFile.split(/\r?\n/)
  .filter(l => l.includes('=') && !l.startsWith('#')).map(l => [l.slice(0, l.indexOf('=')).trim(), l.slice(l.indexOf('=') + 1).trim()])), ...process.env };
const missing = ['INDIA_TOKEN', 'INDIA_LOCATION_ID', 'INTL_TOKEN', 'INTL_LOCATION_ID'].filter(k => !env[k]);
if (missing.length) { console.error(`Missing env vars: ${missing.join(', ')}`); process.exit(1); }

const ACCOUNTS = [
  { name: 'Orkay India', loc: env.INDIA_LOCATION_ID, token: env.INDIA_TOKEN },
  { name: 'Orkay International', loc: env.INTL_LOCATION_ID, token: env.INTL_TOKEN },
];
const HOURS = Number(process.argv[2] || 24);
const END = new Date();
const START = new Date(END - HOURS * 3600e3);
const API = 'https://services.leadconnectorhq.com';

async function ghl(acc, path, body, version = '2021-07-28') {
  for (let attempt = 0; ; attempt++) {
    const r = await fetch(API + path, {
      method: body ? 'POST' : 'GET',
      headers: { Authorization: `Bearer ${acc.token}`, Version: version, Accept: 'application/json', 'Content-Type': 'application/json' },
      body: body && JSON.stringify(body),
    });
    if (r.status === 429 && attempt < 4) { await new Promise(s => setTimeout(s, 2000 * (attempt + 1))); continue; }
    const j = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(`${r.status} ${[j.message].flat().join('; ')}`.trim());
    return j;
  }
}

const range = { gte: START.toISOString(), lte: END.toISOString() };
const countBy = (arr, fn) => arr.reduce((m, x) => (m[fn(x)] = (m[fn(x)] || 0) + 1, m), {});
const table = (obj, h = ['', 'Count']) => {
  const rows = Object.entries(obj).sort((a, b) => b[1] - a[1]);
  return rows.length ? `| ${h[0]} | ${h[1]} |\n|---|---|\n` + rows.map(([k, v]) => `| ${k} | ${v} |`).join('\n') : '_none_';
};
const inr = n => Math.round(n).toLocaleString('en-IN');

async function allContacts(acc) {
  const out = [];
  for (let page = 1; page <= 20; page++) { // ponytail: caps at 2,000 new contacts/day
    const j = await ghl(acc, '/contacts/search', { locationId: acc.loc, page, pageLimit: 100,
      filters: [{ field: 'dateAdded', operator: 'range', value: range }] });
    out.push(...j.contacts);
    if (out.length >= j.total || !j.contacts.length) break;
  }
  return out;
}

async function allOpps(acc, field) {
  const out = [];
  for (let page = 1; page <= 20; page++) {
    const j = await ghl(acc, '/opportunities/search', { locationId: acc.loc, page, limit: 100,
      filters: [{ field, operator: 'range', value: range }] });
    out.push(...j.opportunities);
    if (out.length >= j.total || !j.opportunities.length) break;
  }
  return out;
}

async function recentConversations(acc) {
  const out = [];
  let startAfterDate;
  for (let i = 0; i < 20; i++) {
    const q = `/conversations/search?locationId=${acc.loc}&limit=100&sort=desc&sortBy=last_message_date` + (startAfterDate ? `&startAfterDate=${startAfterDate}` : '');
    const { conversations: c = [] } = await ghl(acc, q, null, '2021-04-15');
    const inWindow = c.filter(x => x.lastMessageDate >= +START);
    out.push(...inWindow);
    if (inWindow.length < c.length || c.length < 100) break;
    startAfterDate = c.at(-1).lastMessageDate;
  }
  return out;
}

async function section(title, fn) {
  try { return `### ${title}\n${await fn()}\n`; }
  catch (e) { return `### ${title}\n⚠️ Could not fetch: ${e.message}${/scope|40[13]/.test(e.message) ? ' (Private Integration token is missing this scope)' : ''}\n`; }
}

async function accountReport(acc) {
  let stageName = id => id, pipeName = id => id;
  try {
    const { pipelines } = await ghl(acc, `/opportunities/pipelines?locationId=${acc.loc}`);
    const s = {}, p = {};
    for (const pl of pipelines) { p[pl.id] = pl.name; for (const st of pl.stages) s[st.id] = st.name; }
    stageName = id => s[id] || id; pipeName = id => p[id] || id;
  } catch {}

  const parts = [`## ${acc.name}\n`];
  const summary = {};

  parts.push(await section('New leads (contacts created)', async () => {
    const c = await allContacts(acc);
    summary.leads = c.length;
    // search omits attribution; fetch each contact (10 at a time) for its real channel
    for (let i = 0; i < c.length; i += 10) await Promise.all(c.slice(i, i + 10).map(async x => {
      const a = (await ghl(acc, `/contacts/${x.id}`).catch(() => ({}))).contact?.attributionSource;
      if (a && !x.source) x.source = [a.sessionSource, a.medium, a.adName].filter(Boolean).join(' / ');
    }));
    const tags = countBy(c.flatMap(x => x.tags?.length ? x.tags : ['(no tag)']), t => t);
    return `**${c.length} new leads**\n\nBy source:\n${table(countBy(c, x => x.source || 'Unknown'), ['Source', 'Leads'])}\n\nBy tag:\n${table(tags, ['Tag', 'Leads'])}\n\nBy country:\n${table(countBy(c, x => x.country || 'Unknown'), ['Country', 'Leads'])}`;
  }));

  parts.push(await section('Pipeline — new opportunities', async () => {
    const o = await allOpps(acc, 'date_added');
    summary.newOpps = o.length;
    const val = o.reduce((s, x) => s + (x.monetaryValue || 0), 0);
    return `**${o.length} created** (value ₹${inr(val)})\n\n${table(countBy(o, x => `${pipeName(x.pipelineId)} → ${stageName(x.pipelineStageId)}`), ['Pipeline → Stage', 'Opps'])}`;
  }));

  parts.push(await section('Pipeline — stage movements', async () => {
    const o = (await allOpps(acc, 'last_stage_change_date')).filter(x => new Date(x.createdAt) < START);
    summary.moved = o.length;
    return `**${o.length} existing opportunities moved to a new stage**\n\n${table(countBy(o, x => `${pipeName(x.pipelineId)} → ${stageName(x.pipelineStageId)}`), ['Now in stage', 'Opps'])}`;
  }));

  parts.push(await section('Pipeline — won / lost / abandoned', async () => {
    const o = (await allOpps(acc, 'last_status_change_date')).filter(x => x.status !== 'open' && new Date(x.lastStatusChangeAt) >= START);
    const by = s => o.filter(x => x.status === s);
    summary.won = by('won').length; summary.lost = by('lost').length;
    return ['won', 'lost', 'abandoned'].map(s => `- **${s}**: ${by(s).length} (₹${inr(by(s).reduce((a, x) => a + (x.monetaryValue || 0), 0))})`).join('\n');
  }));

  parts.push(await section('Conversations', async () => {
    const c = await recentConversations(acc);
    summary.convs = c.length;
    const inbound = c.filter(x => x.lastMessageDirection === 'inbound');
    const unread = c.filter(x => x.unreadCount > 0);
    return `- Active conversations: **${c.length}**\n- Last message from customer (awaiting reply): **${inbound.length}**\n- Unread: **${unread.length}**\n\nBy channel:\n${table(countBy(c, x => (x.lastMessageType || 'unknown').replace('TYPE_', '')), ['Channel', 'Convs'])}`;
  }));

  parts.push(await section('Appointments', async () => {
    const { calendars = [] } = await ghl(acc, `/calendars/?locationId=${acc.loc}`, null, '2021-04-15');
    const ev = [];
    for (const cal of calendars) {
      const { events = [] } = await ghl(acc, `/calendars/events?locationId=${acc.loc}&calendarId=${cal.id}&startTime=${+START}&endTime=${+END + 7 * 86400e3}`, null, '2021-04-15');
      ev.push(...events.map(e => ({ ...e, cal: cal.name })));
    }
    const booked = ev.filter(e => new Date(e.dateAdded) >= START);
    const held = ev.filter(e => new Date(e.startTime) >= START && new Date(e.startTime) <= END);
    summary.booked = booked.length;
    return `- Booked in last ${HOURS}h: **${booked.length}**\n- Scheduled in last ${HOURS}h: **${held.length}** (${Object.entries(countBy(held, e => e.appointmentStatus || 'unknown')).map(([k, v]) => `${k} ${v}`).join(', ') || 'none'})\n- Upcoming next 7 days: **${ev.filter(e => new Date(e.startTime) > END).length}**`;
  }));

  return { md: parts.join('\n'), summary };
}

const fmt = d => d.toLocaleString('en-IN', { timeZone: 'Asia/Kolkata', dateStyle: 'medium', timeStyle: 'short' });
const results = [];
for (const acc of ACCOUNTS) results.push({ acc, ...(await accountReport(acc)) });

const head = `# Orkay GHL — ${HOURS}h status\n_${fmt(START)} → ${fmt(END)} IST_\n\n| | ${results.map(r => r.acc.name).join(' | ')} |\n|---|${results.map(() => '---').join('|')}|\n` +
  [['New leads', 'leads'], ['New opportunities', 'newOpps'], ['Moved stage', 'moved'], ['Won', 'won'], ['Lost', 'lost'], ['Active conversations', 'convs'], ['Appointments booked', 'booked']]
    .map(([l, k]) => `| ${l} | ${results.map(r => r.summary[k] ?? '⚠️').join(' | ')} |`).join('\n');
const md = head + '\n\n' + results.map(r => r.md).join('\n---\n\n');

mkdirSync(join(DIR, 'reports'), { recursive: true });
const file = join(DIR, 'reports', `${END.toLocaleDateString('en-CA', { timeZone: 'Asia/Kolkata' })}.md`);
writeFileSync(file, md);
console.log(md + `\n\n_Saved: ${file}_`);
