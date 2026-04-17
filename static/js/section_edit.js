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

      // Update the iframe preview in place, then scroll to the edited section
      const frame = document.getElementById('previewFrame');
      const scrollTargetId = currentSectionId;
      if (frame) {
        const onLoad = () => {
          frame.removeEventListener('load', onLoad);
          try {
            const doc = frame.contentDocument;
            if (!doc || !scrollTargetId) return;
            const el = doc.getElementById(scrollTargetId);
            if (el) {
              el.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }
          } catch (_) { /* cross-origin or not-yet-ready — ignore */ }
        };
        frame.addEventListener('load', onLoad);
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

      // Regenerate always leaves ≥ 2 revisions (snapshot + new), so Revert is available.
      if (currentSectionId) setRevertVisible(currentSectionId, true);
      const regeneratedTitle = currentSectionTitle || 'Section';
      closeModal();
      showToast(`Section "${regeneratedTitle}" regenerated successfully`);
    } catch (err) {
      showError(`Network error: ${err.message || err}`);
      submitBtn.disabled = false;
      submitLabel.textContent = 'Regenerate';
    }
  }

  // ── Helpers that mutate sidebar state ───────────────────────
  function setRevertVisible(sectionId, visible) {
    const rows = document.querySelectorAll(`.section-row[data-section-id="${sectionId}"]`);
    rows.forEach((row) => {
      const btn = row.querySelector('.revert-section-btn');
      if (!btn) return;
      if (visible) btn.removeAttribute('hidden');
      else btn.setAttribute('hidden', '');
    });
  }

  function updateIframeAndScroll(planHtml, sectionId) {
    const frame = document.getElementById('previewFrame');
    if (!frame) return;
    const onLoad = () => {
      frame.removeEventListener('load', onLoad);
      try {
        const doc = frame.contentDocument;
        if (!doc || !sectionId) return;
        const el = doc.getElementById(sectionId);
        if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
      } catch (_) { /* ignore */ }
    };
    frame.addEventListener('load', onLoad);
    frame.srcdoc = planHtml;
  }

  // ── Revert ──────────────────────────────────────────────────
  async function revertSection({ planId, sectionId, sectionTitle }) {
    try {
      const resp = await fetch(
        `/api/plans/${encodeURIComponent(planId)}/sections/${encodeURIComponent(sectionId)}/revert`,
        { method: 'POST', headers: { 'Content-Type': 'application/json' } },
      );
      let body;
      try { body = await resp.json(); } catch (_) { body = null; }
      if (!resp.ok || !body || !body.ok) {
        const msg = (body && (body.error || body.error_type)) || `Request failed (${resp.status}).`;
        showToast(`Revert failed: ${msg}`, 'error');
        return;
      }
      updateIframeAndScroll(body.plan_html, sectionId);
      setRevertVisible(sectionId, !!body.can_revert);
      showToast(`Section "${sectionTitle}" reverted to the previous version`);
    } catch (err) {
      showToast(`Network error: ${err.message || err}`, 'error');
    }
  }

  document.addEventListener('click', (event) => {
    const editBtn = event.target.closest('.edit-section-btn');
    if (editBtn) {
      openModal({
        planId: editBtn.dataset.planId,
        sectionId: editBtn.dataset.sectionId,
        sectionTitle: editBtn.dataset.sectionTitle,
      });
      return;
    }
    const revertBtn = event.target.closest('.revert-section-btn');
    if (revertBtn) {
      if (!confirm(`Revert "${revertBtn.dataset.sectionTitle}" to the previous version?`)) return;
      revertSection({
        planId: revertBtn.dataset.planId,
        sectionId: revertBtn.dataset.sectionId,
        sectionTitle: revertBtn.dataset.sectionTitle,
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
