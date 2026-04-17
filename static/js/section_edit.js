(function () {
  'use strict';

  const backdrop = document.getElementById('editModalBackdrop');
  const titleInput = document.getElementById('editSectionTitle');
  const commentInput = document.getElementById('editUserComment');
  const imageCheckbox = document.getElementById('editRegenerateImage');
  const errorBox = document.getElementById('editModalError');
  const submitBtn = document.getElementById('editModalSubmit');
  const submitLabel = document.getElementById('editModalSubmitLabel');
  const cancelBtn = document.getElementById('editModalCancel');
  const closeBtn = document.getElementById('editModalClose');

  let currentPlanId = null;
  let currentSectionId = null;
  let currentSectionTitle = null;

  // ── Toast notification ──────────────────────────────────────
  let toastTimer = null;
  function showToast(message, variant = 'success') {
    let toast = document.getElementById('sectionEditToast');
    if (!toast) {
      toast = document.createElement('div');
      toast.id = 'sectionEditToast';
      toast.className = 'section-edit-toast';
      document.body.appendChild(toast);
    }
    toast.className = `section-edit-toast ${variant}`;
    toast.textContent = message;
    // Force reflow so re-triggered animation plays
    void toast.offsetWidth;
    toast.classList.add('visible');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => {
      toast.classList.remove('visible');
    }, 4000);
  }

  function openModal({ planId, sectionId, sectionTitle }) {
    currentPlanId = planId;
    currentSectionId = sectionId;
    currentSectionTitle = sectionTitle;
    titleInput.value = sectionTitle;
    commentInput.value = '';
    imageCheckbox.checked = false;
    errorBox.hidden = true;
    errorBox.textContent = '';
    submitBtn.disabled = false;
    submitLabel.textContent = 'Regenerate';
    backdrop.hidden = false;
    setTimeout(() => commentInput.focus(), 10);
  }

  function closeModal() {
    backdrop.hidden = true;
    currentPlanId = null;
    currentSectionId = null;
    currentSectionTitle = null;
  }

  function showError(message) {
    errorBox.textContent = message;
    errorBox.hidden = false;
  }

  async function submit() {
    const comment = commentInput.value.trim();
    if (!comment) {
      showError('Please describe what you want to change.');
      return;
    }
    submitBtn.disabled = true;
    submitLabel.textContent = 'Regenerating…';
    errorBox.hidden = true;

    try {
      const resp = await fetch(
        `/api/plans/${encodeURIComponent(currentPlanId)}/sections/${encodeURIComponent(currentSectionId)}/regenerate`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            user_comment: comment,
            regenerate_image: imageCheckbox.checked,
          }),
        },
      );
      let body;
      try {
        body = await resp.json();
      } catch (_) {
        // Server returned non-JSON (e.g., a crash page). Show the status text.
        const raw = await resp.text().catch(() => '');
        const preview = (raw || '').replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim().slice(0, 300);
        showError(`Server error (${resp.status} ${resp.statusText || ''}).${preview ? ' ' + preview : ''}`);
        submitBtn.disabled = false;
        submitLabel.textContent = 'Regenerate';
        return;
      }
      if (!resp.ok || !body.ok) {
        const label = body.error_type ? `[${body.error_type}] ` : '';
        showError(`${label}${body.error || `Request failed (${resp.status}).`}`);
        submitBtn.disabled = false;
        submitLabel.textContent = 'Regenerate';
        return;
      }

      // Update the iframe preview in place
      const frame = document.getElementById('previewFrame');
      if (frame) {
        frame.srcdoc = body.plan_html;
      }

      // Update stale badges in the sidebar
      const staleSet = new Set(body.stale_section_ids || []);
      document.querySelectorAll('.section-row').forEach((row) => {
        const sid = row.dataset.sectionId;
        const actions = row.querySelector('.section-row-actions');
        const existingBadge = actions.querySelector('.stale-badge');
        const shouldHaveBadge = staleSet.has(sid);
        if (shouldHaveBadge && !existingBadge) {
          const badge = document.createElement('span');
          badge.className = 'stale-badge';
          badge.title = 'This section may be out of date. Review or regenerate.';
          badge.textContent = 'Stale';
          actions.insertBefore(badge, actions.firstChild);
        } else if (!shouldHaveBadge && existingBadge) {
          existingBadge.remove();
        }
      });

      const regeneratedTitle = currentSectionTitle || 'Section';
      closeModal();
      showToast(`Section "${regeneratedTitle}" regenerated successfully`);
    } catch (err) {
      showError(`Network error: ${err.message || err}`);
      submitBtn.disabled = false;
      submitLabel.textContent = 'Regenerate';
    }
  }

  document.addEventListener('click', (event) => {
    const btn = event.target.closest('.edit-section-btn');
    if (btn) {
      openModal({
        planId: btn.dataset.planId,
        sectionId: btn.dataset.sectionId,
        sectionTitle: btn.dataset.sectionTitle,
      });
    }
  });

  closeBtn.addEventListener('click', closeModal);
  cancelBtn.addEventListener('click', closeModal);
  submitBtn.addEventListener('click', submit);

  backdrop.addEventListener('click', (event) => {
    if (event.target === backdrop) closeModal();
  });

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && !backdrop.hidden) closeModal();
  });
})();
