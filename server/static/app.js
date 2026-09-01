const byId = (id) => document.getElementById(id);
const safe = (value) => String(value ?? "");
let adminToken = sessionStorage.getItem('mini-edr-admin-token') || '';

async function adminFetch(path, options = {}) {
  const headers = new Headers(options.headers || {});
  headers.set('X-Admin-Token', adminToken);
  const response = await fetch(path, {...options, headers});
  if (!response.ok) throw new Error((await response.json().catch(() => ({}))).detail || 'Request failed');
  return response.json();
}

function renderAgents(agents) {
  const target = byId('agents');
  target.replaceChildren(...agents.map(agent => {
    const node = document.createElement('div'); node.className = 'agent';
    node.textContent = `${agent.agent_name} // ${agent.hostname} // ${agent.platform} // last seen ${agent.last_seen_at}`;
    return node;
  }));
  if (!agents.length) target.textContent = 'No enrolled endpoints.';
}

function renderAlerts(alerts) {
  const target = byId('alerts'); const template = byId('alert-template');
  target.replaceChildren(...alerts.map(alert => {
    const node = template.content.cloneNode(true);
    node.querySelector('.alert').classList.add(safe(alert.severity));
    node.querySelector('.title').textContent = `[${safe(alert.severity).toUpperCase()}] ${safe(alert.title)}`;
    node.querySelector('.meta').textContent = `${safe(alert.hostname)} // ${safe(alert.rule_id)} // ${safe(alert.mitre || 'NO-MITRE')} // ${safe(alert.created_at)}`;
    node.querySelector('.description').textContent = safe(alert.description);
    node.querySelector('.evidence').textContent = JSON.stringify(alert.evidence, null, 2);
    return node;
  }));
  if (!alerts.length) target.textContent = 'No alerts. Monitoring is active.';
}

function renderDeployments(deployments) {
  const target = byId('deployments');
  target.replaceChildren(...deployments.map(deployment => {
    const node = document.createElement('div'); node.className = 'agent';
    const details = document.createElement('span');
    details.textContent = `${deployment.agent_name} // ${deployment.platform} // ${deployment.status.toUpperCase()} // expires ${deployment.expires_at}`;
    node.append(details);
    if (deployment.status === 'pending') {
      const revoke = document.createElement('button'); revoke.className = 'small-button'; revoke.textContent = 'Revoke';
      revoke.onclick = async () => { await adminFetch(`/api/v1/deployments/${deployment.id}/revoke`, {method: 'POST'}); refresh(); };
      node.append(revoke);
    }
    return node;
  }));
  if (!deployments.length) target.textContent = 'No deployment records.';
}

async function refresh() {
  try {
    const [health, agents, alerts, deployments] = await Promise.all([
      fetch('/api/health').then(r => r.json()), adminFetch('/api/v1/agents'), adminFetch('/api/v1/alerts'), adminFetch('/api/v1/deployments')
    ]);
    byId('health').textContent = `ONLINE // ${health.rule_count} RULES`;
    renderAgents(agents); renderAlerts(alerts); renderDeployments(deployments);
  } catch (error) {
    byId('health').textContent = 'ADMIN SESSION EXPIRED';
    byId('login-error').textContent = error.message;
    byId('login').hidden = false; byId('dashboard').hidden = true;
    sessionStorage.removeItem('mini-edr-admin-token'); adminToken = '';
  }
}

byId('login-button').onclick = async () => {
  adminToken = byId('admin-token').value;
  try {
    await adminFetch('/api/v1/deployments');
    sessionStorage.setItem('mini-edr-admin-token', adminToken);
    byId('login').hidden = true; byId('dashboard').hidden = false; byId('login-error').textContent = '';
    refresh();
  } catch (error) { byId('login-error').textContent = error.message; }
};

byId('create-deployment').onclick = async () => {
  const agentName = byId('agent-name').value.trim();
  if (!agentName) { byId('package-status').textContent = 'Enter a unique agent name.'; byId('deployment-result').hidden = false; return; }
  try {
    const created = await adminFetch('/api/v1/deployments', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({
      agent_name: agentName, platform: byId('deployment-platform').value, expires_in_minutes: Number(byId('deployment-expiry').value)
    })});
    byId('install-command').textContent = created.install_command;
    byId('package-status').textContent = created.package_ready ? 'Package is published and ready to download.' : 'Package has not been published yet. Build and publish the signed agent package before using this command.';
    byId('deployment-result').hidden = false; byId('agent-name').value = ''; refresh();
  } catch (error) { byId('package-status').textContent = error.message; byId('deployment-result').hidden = false; }
};

if (adminToken) { byId('login').hidden = true; byId('dashboard').hidden = false; refresh(); }

