// app.js: User interface: draws results, questions, decisions, and the agent trace
'use strict';

const $ = id => document.getElementById(id);
const esc = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
let overrides = { labs: {}, concepts: {}, crits: {}, age: null };
const decisions = {};
let current = 'ex1';

function labelFor(row) {
  if (row.res === 'skip') return ['skip', 'Skipped'];
  if (row.res === 'unsure') return ['warn', 'Unsure'];
  if (row.ex) return row.res === 'yes' ? ['bad', 'Applies'] : ['ok', 'Does not apply'];
  return row.res === 'yes' ? ['ok', 'Met'] : ['bad', 'Not met'];
}
const STATUS = { ok: ['ok', 'Likely eligible'], warn: ['warn', 'Needs review'], bad: ['bad', 'Not eligible'] };

function render(out) {
  const c = out.cost;
  $('stats').innerHTML = [
    [`${out.funnel[0]} → ${out.ranked.length}`, 'trials screened → checked'],
    [`${c.t1} + ${c.t2}`, 'low-cost + escalated calls'],
    [`$${c.spent.toFixed(4)}`, `est. cost vs $${c.fixed.toFixed(3)} fixed pipeline`],
    [`${Math.round(out.save * 100)}%`, 'estimated cost saved', 'save'],
  ].map(([b, s, cls]) => `<div class="stat ${cls || ''}"><b>${b}</b><span>${s}</span></div>`).join('');
  $('funnel').textContent = `Filter: ${out.funnel[0]} trials → ${out.funnel[1]} recruiting → ${out.funnel[2]} fit age and sex → ${out.funnel[3]} nearby → top ${out.ranked.length} checked · ${c.rule} rule checks (free) · ${c.skipped} checks skipped by early stopping`;

  const qs = out.qs;
  $('questions').innerHTML = qs.length ? `<div class="questions"><h3>Questions for the clinician (${qs.length})</h3>
    <p class="hint">The agent stops and asks instead of guessing. Answer and re-run to update the matches.</p>
    ${qs.map((q, i) => `<div class="q"><label for="q${i}">${esc(q.q)} <span class="meta">${esc((q.trials || []).join(', '))}</span></label>${q.kind === 'lab' || q.kind === 'age'
      ? `<input type="number" step="0.1" id="q${i}" data-i="${i}" placeholder="value">`
      : `<select id="q${i}" data-i="${i}"><option value="">Unknown</option><option value="yes">Yes</option><option value="no">No</option></select>`}</div>`).join('')}
    <button class="small" id="answer">Apply answers and re-run</button></div>` : '';
  if (qs.length) $('answer').onclick = () => {
    qs.forEach((q, i) => { const v = $('q' + i).value; if (v === '') return;
      if (q.kind === 'lab') overrides.labs[q.lab] = q.lab === 'nyha' ? (ROMAN[v.toLowerCase()] || +v) : +v;
      else if (q.kind === 'age') overrides.age = +v;
      else if (q.kind === 'concept') overrides.concepts[q.concept] = v === 'yes';
      else if (q.kind === 'crit') overrides.crits[q.crit] = v === 'yes'; });
    run();
  };

  $('trials').innerHTML = out.ranked.length ? out.ranked.map((r, i) => {
    const t = r.t, [cls, txt] = STATUS[r.status], d = decisions[t.id];
    return `<details class="trial" ${i < 2 ? 'open' : ''}><summary><span class="rank">#${i + 1}</span>
      <span class="ttl">${esc(t.title)}<div class="meta">${esc(t.id)} · ${esc(t.locations.map(l => l.join(', ')).slice(0, 2).join(' · '))} · match ${r.fused.toFixed(2)} (BM25 ${r.bm.toFixed(2)}, vector ${r.cs.toFixed(2)})</div></span>
      <span class="pill ${cls}">${txt}</span></summary>
      <div class="body"><div class="tablewrap"><table><thead><tr><th>Type</th><th>Criterion</th><th>Result</th><th>Evidence</th><th>Checked by</th></tr></thead><tbody>
      ${r.rows.map(row => { const [lc, lt] = labelFor(row); return `<tr><td>${row.ex ? 'Exclusion' : 'Inclusion'}</td><td>${esc(row.c)}</td><td><span class="lab ${lc}">${lt}</span></td><td class="ev">${esc(row.ev)}</td><td class="tier">${esc(row.tier)}</td></tr>`; }).join('')}
      </tbody></table></div>
      <div class="decide"><button class="small" data-acc="${esc(t.id)}">Accept for referral</button><button class="small" data-rej="${esc(t.id)}">Reject</button>
      <span class="decision" style="color:var(${d === 'Accepted' ? '--ok' : '--bad'})">${d ? 'Clinician decision: ' + d : ''}</span></div></div></details>`;
  }).join('') : '<p class="empty">No recruiting trials matched the filters. Try another patient or location.</p>';
  document.querySelectorAll('[data-acc]').forEach(b => b.onclick = () => { decisions[b.dataset.acc] = 'Accepted'; render(out); });
  document.querySelectorAll('[data-rej]').forEach(b => b.onclick = () => { decisions[b.dataset.rej] = 'Rejected'; render(out); });

  $('trace').innerHTML = out.trace.map((s, i) => `<div class="step"><div><b>Step ${i + 1} · Thought:</b> ${esc(s.thought)}</div><div><b>Action:</b> ${esc(s.action)}</div><div><b>Observation:</b> ${esc(s.obs)}</div></div>`).join('');
}

async function run() {
  const opts = { topk: Math.max(1, +$('topk').value || 8), alpha: Math.min(1, Math.max(0, +$('alpha').value)), budget: +$('budget').value, p1: +$('p1').value, p2: +$('p2').value };
  let trials = TRIALS; const note = $('sourceNote'); note.hidden = true;
  if ($('source').value === 'live') {
    try { trials = await fetchLive(extractFacts($('summary').value, overrides)); if (!trials.length) throw new Error('no studies returned'); note.textContent = `Loaded ${trials.length} recruiting studies from ClinicalTrials.gov.`; note.hidden = false; }
    catch (e) { trials = TRIALS; note.textContent = 'Live search is not available here (' + e.message + '). Showing the offline sample trials instead.'; note.hidden = false; }
  }
  render(runAgent($('summary').value, trials, opts, overrides));
}
function pick(id) {
  current = id; overrides = { labs: {}, concepts: {}, crits: {}, age: null };
  ['ex1', 'ex2', 'ex3'].forEach(k => $(k).setAttribute('aria-pressed', String(k === id)));
  $('summary').value = EXAMPLES[id]; run();
}
['ex1', 'ex2', 'ex3'].forEach(k => $(k).onclick = () => pick(k));
$('run').onclick = () => { overrides = { labs: {}, concepts: {}, crits: {}, age: null }; run(); };
pick('ex1');