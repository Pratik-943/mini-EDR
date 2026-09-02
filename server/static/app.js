const byId = (id) => document.getElementById(id);
const safe = (value) => String(value ?? "");
let adminToken = sessionStorage.getItem('mini-edr-admin-token') || '';
let deploymentOptions = {packages: {windows: false, linux: false}};
let selectedPlatform = '';

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
    node.textContent = `${agent.agent_name} // ${agent.hostname} // ${agent.platform.toUpperCase()} // last seen ${agent.last_seen_at}`;
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
    const node = document.createElement('div'); node.className = 'agent deployment-row';
    const details = document.createElement('span');
    details.textContent = `${deployment.agent_name} // ${deployment.platform.toUpperCase()} // ${deployment.status.toUpperCase()} // expires ${new Date(deployment.expires_at).toLocaleString()}`;
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

function updateStatusCards(agents, deployments, options) {
  byId('active-count').textContent = agents.length;
  byId('pending-count').textContent = deployments.filter(item => item.status === 'pending').length;
  byId('expired-count').textContent = deployments.filter(item => item.status === 'expired').length;
  byId('package-count').textContent = `${Number(options.packages.windows) + Number(options.packages.linux)} / 2`;
}

function updatePackageCards() {
  document.querySelectorAll('.package-card').forEach(card => {
    const platform = card.dataset.platform;
    const ready = deploymentOptions.packages[platform];
    card.disabled = !ready;
    card.classList.toggle('selected', selectedPlatform === platform);
    card.querySelector('em').textContent = ready ? 'Package ready' : 'Package unavailable';
  });
  const ready = Boolean(selectedPlatform && deploymentOptions.packages[selectedPlatform]);
  byId('generate-command').disabled = !ready;
  if (!ready) byId('command-empty').textContent = 'Select an available package. Unpublished packages cannot generate installation commands.';
}

function resetWizard() {
  selectedPlatform = '';
  byId('agent-name').value = '';
  byId('deployment-message').textContent = '';
  byId('command-result').hidden = true;
  byId('command-empty').hidden = false;
  byId('copy-status').textContent = '';
  updatePackageCards();
}

async function refresh() {
  try {
    const [health, agents, alerts, deployments, options] = await Promise.all([
      fetch('/api/health').then(r => r.json()), adminFetch('/api/v1/agents'), adminFetch('/api/v1/alerts'), adminFetch('/api/v1/deployments'), adminFetch('/api/v1/deployment-options')
    ]);
    deploymentOptions = options;
    byId('health').textContent = `ONLINE // ${health.rule_count} RULES`;
    renderAgents(agents); renderAlerts(alerts); renderDeployments(deployments); updateStatusCards(agents, deployments, options); updatePackageCards();
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
    await adminFetch('/api/v1/deployment-options');
    sessionStorage.setItem('mini-edr-admin-token', adminToken);
    byId('login').hidden = true; byId('dashboard').hidden = false; byId('login-error').textContent = '';
    refresh();
  } catch (error) { byId('login-error').textContent = error.message; }
};

byId('open-deployment').onclick = () => { resetWizard(); byId('server-url').value = deploymentOptions.server_url || ''; byId('deployment-dialog').showModal(); };
byId('close-deployment').onclick = () => byId('deployment-dialog').close();
document.querySelectorAll('.package-card').forEach(card => card.onclick = () => { selectedPlatform = card.dataset.platform; byId('deployment-message').textContent = ''; updatePackageCards(); });

byId('generate-command').onclick = async () => {
  const agentName = byId('agent-name').value.trim();
  if (!selectedPlatform || !deploymentOptions.packages[selectedPlatform]) return;
  if (!agentName) { byId('deployment-message').textContent = 'Enter a unique agent name.'; return; }
  try {
    const created = await adminFetch('/api/v1/deployments', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({
      agent_name: agentName, platform: selectedPlatform, expires_in_minutes: Number(byId('deployment-expiry').value)
    })});
    byId('install-command').value = created.install_command;
    byId('command-empty').hidden = true; byId('command-result').hidden = false;
    byId('deployment-message').textContent = 'Copy this one-time command now. It will not be shown again.';
    byId('deployment-message').className = 'success';
    refresh();
  } catch (error) { byId('deployment-message').textContent = error.message; byId('deployment-message').className = 'error'; }
};

byId('copy-command').onclick = async () => {
  const command = byId('install-command');
  try {
    await navigator.clipboard.writeText(command.value);
    byId('copy-status').textContent = 'Copied to clipboard.';
  } catch (_) {
    command.focus(); command.select();
    byId('copy-status').textContent = 'Select the command and press Ctrl + C.';
  }
};

if (adminToken) { byId('login').hidden = true; byId('dashboard').hidden = false; refresh(); }

