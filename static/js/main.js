/**
 * EMS — Employee Management System
 * Main JavaScript
 */

// ── Dark Mode ────────────────────────────────────────────
(function initTheme() {
  const saved = localStorage.getItem('ems-theme') || 'light';
  applyTheme(saved);
})();

function applyTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);
  const icon = document.getElementById('themeIcon');
  if (icon) {
    icon.className = theme === 'dark' ? 'bi bi-sun-fill' : 'bi bi-moon-fill';
  }
}

document.addEventListener('DOMContentLoaded', function () {

  // ── Theme Toggle ──────────────────────────────────────
  document.querySelectorAll('#themeToggle').forEach(btn => {
    btn.addEventListener('click', function () {
      const current = document.documentElement.getAttribute('data-theme');
      const next = current === 'dark' ? 'light' : 'dark';
      applyTheme(next);
      localStorage.setItem('ems-theme', next);
    });
  });

  // ── Sidebar Toggle (mobile) ───────────────────────────
  const sidebarToggle = document.getElementById('sidebarToggle');
  const sidebar       = document.getElementById('sidebar');

  if (sidebarToggle && sidebar) {
    sidebarToggle.addEventListener('click', function () {
      sidebar.classList.toggle('open');
    });

    // Close sidebar when clicking outside
    document.addEventListener('click', function (e) {
      if (!sidebar.contains(e.target) && !sidebarToggle.contains(e.target)) {
        sidebar.classList.remove('open');
      }
    });
  }

  // ── Loading Spinner on form submit / navigation ───────
  const spinner = document.getElementById('spinnerOverlay');

  // Show spinner on anchor clicks that navigate pages
  document.querySelectorAll('a[href]').forEach(link => {
    const href = link.getAttribute('href');
    // Only for real page navigations, skip modals and # links
    if (href && !href.startsWith('#') && !href.startsWith('javascript') && href !== '') {
      link.addEventListener('click', function () {
        // Only show for same-origin links
        if (!link.target || link.target === '_self') {
          showSpinner();
        }
      });
    }
  });

  // Show spinner on form submits
  document.querySelectorAll('form').forEach(form => {
    form.addEventListener('submit', function () {
      showSpinner();
    });
  });

  // Hide spinner once page loads
  window.addEventListener('load', hideSpinner);

  // ── Auto-hide alerts ──────────────────────────────────
  document.querySelectorAll('.alert-custom').forEach(el => {
    setTimeout(() => {
      el.style.transition = 'opacity 0.5s';
      el.style.opacity = '0';
      setTimeout(() => el.remove(), 500);
    }, 4000);
  });

  // ── Animate stat cards on load ────────────────────────
  document.querySelectorAll('.stat-card').forEach((card, i) => {
    card.style.opacity = '0';
    card.style.transform = 'translateY(16px)';
    setTimeout(() => {
      card.style.transition = 'opacity 0.4s ease, transform 0.4s ease';
      card.style.opacity = '1';
      card.style.transform = 'translateY(0)';
    }, 80 * i);
  });

  // ── Animate table rows ────────────────────────────────
  document.querySelectorAll('.table-custom tbody tr').forEach((row, i) => {
    row.style.opacity = '0';
    setTimeout(() => {
      row.style.transition = 'opacity 0.3s ease';
      row.style.opacity = '1';
    }, 40 * i);
  });

});

function showSpinner() {
  const s = document.getElementById('spinnerOverlay');
  if (s) s.classList.add('active');
}

function hideSpinner() {
  const s = document.getElementById('spinnerOverlay');
  if (s) s.classList.remove('active');
}
