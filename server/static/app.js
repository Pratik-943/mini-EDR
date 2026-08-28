const byId = (id) => document.getElementById(id);

function safe(value) { return String(value ?? ""); }

async function refresh() {
  try {
    const [health, agents, alerts] = await Promise.all([
      fetch('/api/health').then(r => r.json()),
      fetch('/api/v1/agents').then(r => r.json()),
      fetch('/api/v1/alerts').then(r => r.json())
    ]);
    byId('health').textContent = `ONLINE // ${health.rule_count} RULES`;
    byId('agents').replaceChildren(...agents.map(agent => {
      const node = document.createElement('div'); node.className = 'agent';
      node.textContent = `${agent.hostname} // ${agent.platform} // last seen ${agent.last_seen_at}`;
      return node;
    }));
    if (!agents.length) byId('agents').textContent = 'No enrolled endpoints.';
    const template = byId('alert-template');
    byId('alerts').replaceChildren(...alerts.map(alert => {
      const node = template.content.cloneNode(true);
      node.querySelector('.alert').classList.add(safe(alert.severity));
      node.querySelector('.title').textContent = `[${safe(alert.severity).toUpperCase()}] ${safe(alert.title)}`;
      node.querySelector('.meta').textContent = `${safe(alert.hostname)} // ${safe(alert.rule_id)} // ${safe(alert.mitre || 'NO-MITRE')} // ${safe(alert.created_at)}`;
      node.querySelector('.description').textContent = safe(alert.description);
      node.querySelector('.evidence').textContent = JSON.stringify(alert.evidence, null, 2);
      return node;
    }));
    if (!alerts.length) byId('alerts').textContent = 'No alerts. Monitoring is active.';
  } catch (_) { byId('health').textContent = 'OFFLINE // SERVER UNREACHABLE'; }
}
refresh(); setInterval(refresh, 5000);

