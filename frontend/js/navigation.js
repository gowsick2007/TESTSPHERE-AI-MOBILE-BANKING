/**
 * TestSphere AI — Shared layout navigation injector
 */

document.addEventListener('DOMContentLoaded', async () => {
  // 1. Initial Session Sync
  try {
    await window.API.checkSession();
  } catch (e) {}

  // Redirect to login if not authenticated and not on login page
  const isLoginPage = window.location.pathname.endsWith('index.html') || window.location.pathname === '/';
  if (!window.API.state.authenticated && !isLoginPage) {
    window.location.href = '/';
    return;
  }

  renderLayout();
  updateStrategyBadge();
});


function renderLayout() {
  const sidebarEl = document.getElementById('shared-sidebar');
  const headerEl = document.getElementById('shared-header');

  const curPath = window.location.pathname;

  // Render Sidebar
  if (sidebarEl) {
    sidebarEl.className = 'sidebar';
    sidebarEl.innerHTML = `
      <div class="brand">
        <h1>TestSphere<span>.AI</span></h1>
        <div class="brand-subtitle">Change Impact Selector</div>
      </div>
      
      <ul class="nav-links">
        <li class="${curPath.endsWith('dashboard.html') ? 'active' : ''}">
          <a href="/frontend/pages/dashboard.html"><i class="fas fa-chart-line"></i> Dashboard</a>
        </li>
        <li class="${curPath.endsWith('data-management.html') ? 'active' : ''}">
          <a href="/frontend/pages/data-management.html"><i class="fas fa-database"></i> Data Center</a>
        </li>
        <li class="${curPath.endsWith('change-analysis.html') ? 'active' : ''}">
          <a href="/frontend/pages/change-analysis.html"><i class="fas fa-code-branch"></i> Change Analysis</a>
        </li>
        <li class="${curPath.endsWith('test-selector.html') ? 'active' : ''}">
          <a href="/frontend/pages/test-selector.html"><i class="fas fa-tasks"></i> Test Selector</a>
        </li>
        <li class="${curPath.endsWith('dependency-graph.html') ? 'active' : ''}">
          <a href="/frontend/pages/dependency-graph.html"><i class="fas fa-project-diagram"></i> Dependency Graph</a>
        </li>
        <li class="${curPath.endsWith('coverage.html') ? 'active' : ''}">
          <a href="/frontend/pages/coverage.html"><i class="fas fa-shield-alt"></i> Coverage Analyzer</a>
        </li>
        <li class="${curPath.endsWith('failure-intelligence.html') ? 'active' : ''}">
          <a href="/frontend/pages/failure-intelligence.html"><i class="fas fa-bug"></i> Failure Intelligence</a>
        </li>
        <li class="${curPath.endsWith('experiment-lab.html') ? 'active' : ''}">
          <a href="/frontend/pages/experiment-lab.html"><i class="fas fa-flask"></i> Experiment Lab</a>
        </li>
        <li class="${curPath.endsWith('rollback.html') ? 'active' : ''}">
          <a href="/frontend/pages/rollback.html"><i class="fas fa-history"></i> Rollback Strategy</a>
        </li>
        <li class="${curPath.endsWith('audit-security.html') ? 'active' : ''}">
          <a href="/frontend/pages/audit-security.html"><i class="fas fa-user-shield"></i> Compliance Audit</a>
        </li>
        <li class="${curPath.endsWith('documentation.html') ? 'active' : ''}">
          <a href="/frontend/pages/documentation.html"><i class="fas fa-book"></i> Documentation</a>
        </li>
      </ul>

      <div class="sidebar-footer">
        <div class="status-indicator">
          <div class="status-dot"></div>
          <span>SYSTEM ONLINE</span>
        </div>
        <div id="shared-strategy-badge" class="strategy-badge">
          STRATEGY: SMART_SELECTOR
        </div>
      </div>
    `;
  }

  // Render Header
  if (headerEl) {
    headerEl.className = 'top-header';
    
    // Breadcrumb parsing
    let pageNameStr = 'Dashboard';
    if (curPath.endsWith('data-management.html')) pageNameStr = 'Data Center';
    if (curPath.endsWith('change-analysis.html')) pageNameStr = 'Change Analysis';
    if (curPath.endsWith('test-selector.html')) pageNameStr = 'Test Selector';
    if (curPath.endsWith('dependency-graph.html')) pageNameStr = 'Dependency Graph';
    if (curPath.endsWith('coverage.html')) pageNameStr = 'Coverage Analyzer';
    if (curPath.endsWith('failure-intelligence.html')) pageNameStr = 'Failure Intelligence';
    if (curPath.endsWith('experiment-lab.html')) pageNameStr = 'Experiment Lab';
    if (curPath.endsWith('rollback.html')) pageNameStr = 'Rollback Strategy';
    if (curPath.endsWith('audit-security.html')) pageNameStr = 'Compliance Audit';
    if (curPath.endsWith('documentation.html')) pageNameStr = 'Documentation';

    const state = window.API.state;
    const initialLetter = state.username ? state.username.charAt(0).toUpperCase() : 'G';

    headerEl.innerHTML = `
      <div class="page-title">
        <h2>${pageNameStr}</h2>
        <div class="breadcrumbs">TestSphere AI / Pages / ${pageNameStr}</div>
      </div>

      <div class="header-right">
        <div class="user-area">
          <div class="user-avatar">${initialLetter}</div>
          <div class="user-info">
            <span class="user-name">${state.username}</span>
            <span class="user-role">${state.role}</span>
          </div>
          <button class="logout-btn" onclick="window.API.logout()" title="Logout">
            <i class="fas fa-sign-out-alt"></i>
          </button>
        </div>
      </div>
    `;
  }
}

async function updateStrategyBadge() {
  const badge = document.getElementById('shared-strategy-badge');
  if (!badge) return;

  try {
    const res = await window.API.fetchStrategy();
    const strategy = res.current_strategy;
    badge.innerText = `STRATEGY: ${strategy}`;
    if (strategy === 'LEGACY_FULL_SUITE') {
      badge.style.background = 'rgba(239, 68, 68, 0.15)';
      badge.style.color = 'var(--color-danger)';
      badge.style.borderColor = 'rgba(239, 68, 68, 0.3)';
    } else {
      badge.style.background = 'rgba(255, 122, 0, 0.15)';
      badge.style.color = 'var(--accent-primary)';
      badge.style.borderColor = 'rgba(255, 122, 0, 0.3)';
    }
  } catch (e) {
    badge.innerText = 'STRATEGY: SMART_SELECTOR';
  }
}
