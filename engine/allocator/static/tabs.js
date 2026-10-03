
// -- tabs ---------------------------------------------------------------
const tabs = Array.from(document.querySelectorAll('.tab'));
const panels = {};
document.querySelectorAll('.panel').forEach(p => { panels[p.id.slice('panel-'.length)] = p; });

function activateTab(name) {
  tabs.forEach(t => t.classList.toggle('active', t.dataset.tab === name));
  Object.entries(panels).forEach(([key, el]) => el.classList.toggle('active', key === name));
  const frame = panels[name] && panels[name].querySelector('iframe[data-src]');
  if (frame) { frame.src = frame.dataset.src; frame.removeAttribute('data-src'); }
}
tabs.forEach(t => t.onclick = () => activateTab(t.dataset.tab));
