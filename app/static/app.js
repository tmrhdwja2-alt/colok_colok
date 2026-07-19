const form = document.querySelector('#upload-form');
const input = document.querySelector('#file-input');
const dropzone = document.querySelector('#dropzone');
const fileName = document.querySelector('#file-name');
const button = document.querySelector('#analyze-button');
const loading = document.querySelector('#loading');
const errorBox = document.querySelector('#error-box');
const results = document.querySelector('#results');

input.addEventListener('change', () => {
  fileName.textContent = input.files[0]?.name || '.FA · .FASTA · .FNA';
});
['dragenter', 'dragover'].forEach(name => dropzone.addEventListener(name, event => {
  event.preventDefault(); dropzone.classList.add('drag');
}));
['dragleave', 'drop'].forEach(name => dropzone.addEventListener(name, event => {
  event.preventDefault(); dropzone.classList.remove('drag');
}));
dropzone.addEventListener('drop', event => {
  if (event.dataTransfer.files.length) {
    input.files = event.dataTransfer.files;
    fileName.textContent = input.files[0].name;
  }
});

form.addEventListener('submit', async event => {
  event.preventDefault();
  if (!input.files.length) return;
  resetState();
  button.disabled = true;
  loading.classList.remove('hidden');
  animatePipeline();
  const data = new FormData();
  data.append('file', input.files[0]);
  try {
    const response = await fetch('/api/analyze', { method: 'POST', body: data });
    const responseText = await response.text();
    let payload = null;
    if (responseText) {
      try {
        payload = JSON.parse(responseText);
      } catch {
        throw new Error(`The server returned an invalid response (HTTP ${response.status}).`);
      }
    }
    if (!response.ok) {
      throw new Error(payload?.error || `The analysis service failed (HTTP ${response.status}).`);
    }
    if (!payload) {
      throw new Error('The analysis service returned an empty response. Please try again.');
    }
    renderResults(payload);
  } catch (error) {
    errorBox.textContent = error.message;
    errorBox.classList.remove('hidden');
  } finally {
    loading.classList.add('hidden');
    button.disabled = false;
  }
});

function resetState() {
  errorBox.classList.add('hidden'); results.classList.add('hidden');
  document.querySelectorAll('.pipeline li').forEach(item => item.classList.remove('active'));
}
function animatePipeline() {
  document.querySelectorAll('.pipeline li').forEach((item, index) => {
    setTimeout(() => item.classList.add('active'), index * 450);
  });
}
function renderResults(data) {
  document.querySelectorAll('.pipeline li').forEach(item => item.classList.add('active'));
  document.querySelector('#sample-id').textContent = data.sample_id;
  document.querySelector('#elapsed').textContent = `${data.elapsed_seconds}s`;
  document.querySelector('#disclaimer').textContent = data.disclaimer;
  const q = data.quality;
  document.querySelector('#quality-card').innerHTML = `<span><b>${escapeHtml(q.status)}</b> · ${q.contigs.toLocaleString()} contigs · ${q.total_bases.toLocaleString()} bp</span><span>GC ${q.gc_fraction}% · N ${q.n_fraction}% · ${escapeHtml(data.annotation_engine)}</span>`;
  document.querySelector('#result-grid').innerHTML = data.predictions.map(cardTemplate).join('');
  document.querySelector('#hit-count').textContent = `${data.amr_hits.length} detected`;
  document.querySelector('#hits').innerHTML = data.amr_hits.length ? data.amr_hits.map(hitTemplate).join('') : '<p>No AMR elements were detected.</p>';
  results.classList.remove('hidden');
  results.scrollIntoView({ behavior: 'smooth', block: 'start' });
}
function cardTemplate(item) {
  const color = item.call === 'Likely to Fail' ? '#ff6b5f' : item.call === 'Likely to Work' ? '#20c5b5' : '#ffc857';
  return `<article class="result-card" style="--call:${color}">
    <div class="drug"><div><h3>${escapeHtml(item.antibiotic)}</h3><div class="class">${escapeHtml(item.drug_class)}</div></div><span class="badge">${escapeHtml(item.call)}</span></div>
    <div class="confidence"><span>CALIBRATED CONFIDENCE</span><strong>${item.confidence}%</strong></div><div class="meter"><i style="width:${item.confidence}%"></i></div>
    <div class="evidence"><b>${escapeHtml(item.evidence_type)}</b><p>${escapeHtml(item.evidence)}</p><div class="target">TARGET GATE · ${escapeHtml(item.target_status)}</div></div>
  </article>`;
}
function hitTemplate(hit) {
  return `<div class="hit-row"><b>${escapeHtml(hit.gene_symbol)}</b><span>${escapeHtml(hit.element_name)}</span><span>${escapeHtml(hit.subclass)}</span><span>${hit.identity ?? '—'}% identity</span></div>`;
}
function escapeHtml(value) {
  return String(value).replace(/[&<>'"]/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[char]));
}
