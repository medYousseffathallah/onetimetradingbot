/* BVMT Trading Intelligence V2 — Interactive Prototype Helper */
(function () {
  const menuBtn = document.querySelector('[data-toggle-nav]');
  const backdrop = document.querySelector('[data-close-nav]');
  if (menuBtn) {
    menuBtn.addEventListener('click', () => {
      document.body.classList.toggle('nav-open');
    });
  }
  if (backdrop) {
    backdrop.addEventListener('click', () => {
      document.body.classList.remove('nav-open');
    });
  }

  // Global mode switcher (REAL_COMPETITION vs SYNTHETIC_DEMO)
  const modeSelect = document.querySelector('[data-mode-select]');
  if (modeSelect) {
    modeSelect.addEventListener('change', (e) => {
      if (e.target.value === 'SYNTHETIC_DEMO') {
        document.body.classList.add('mode-synthetic');
      } else {
        document.body.classList.remove('mode-synthetic');
      }
    });
  }

  // Generic segmented control / tab switcher
  document.querySelectorAll('[data-tab-group]').forEach((group) => {
    const groupName = group.getAttribute('data-tab-group');
    group.querySelectorAll('[data-tab-target]').forEach((btn) => {
      btn.addEventListener('click', () => {
        const target = btn.getAttribute('data-tab-target');
        group.querySelectorAll('[data-tab-target]').forEach((b) => b.classList.remove('active'));
        btn.classList.add('active');
        document.querySelectorAll(`[data-tab-panel="${groupName}"]`).forEach((panel) => {
          panel.style.display = panel.getAttribute('data-panel-id') === target ? '' : 'none';
        });
      });
    });
  });
})();
