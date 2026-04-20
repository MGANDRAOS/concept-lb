(function () {
  'use strict';

  const backdrop = document.getElementById('editModalBackdrop');
  const titleInput = document.getElementById('editSectionTitle');
  const commentInput = document.getElementById('editUserComment');
  const blocksContainer = document.getElementById('editBlocksContainer');
  const errorBox = document.getElementById('editModalError');
  const submitBtn = document.getElementById('editModalSubmit');
  const submitLabel = document.getElementById('editModalSubmitLabel');
  const cancelBtn = document.getElementById('editModalCancel');
  const closeBtn = document.getElementById('editModalClose');
  const queueBtn = document.getElementById('editModalQueue');
  const deleteBtn = document.getElementById('editModalDelete');

  let currentPlanId = null;
  let currentSectionId = null;
  let currentSectionTitle = null;
  let currentBlocks = [];

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
    void toast.offsetWidth;
    toast.classList.add('visible');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => {
      toast.classList.remove('visible');
    }, 4000);
  }

  // ── Block editor renderer ───────────────────────────────────
  function renderBlocksEditor() {
    blocksContainer.innerHTML = '';
    if (!currentBlocks || currentBlocks.length === 0) {
      const notice = document.createElement('div');
      notice.className = 'edit-block-readonly';
      notice.textContent = 'No editable blocks found for this section.';
      blocksContainer.appendChild(notice);
      return;
    }

    currentBlocks.forEach(function (block, blockIdx) {
      const type = block.type || 'other';
      const wrapper = document.createElement('div');
      wrapper.className = 'edit-block';

      const header = document.createElement('div');
      header.className = 'edit-block-header';
      header.textContent = type;
      wrapper.appendChild(header);

      if (type === 'paragraph' || type === 'callout') {
        if (type === 'callout' && block.title !== undefined) {
          // title field
          const titleField = document.createElement('input');
          titleField.type = 'text';
          titleField.value = block.title || '';
          titleField.placeholder = 'Callout title';
          titleField.addEventListener('input', function () {
            currentBlocks[blockIdx].title = this.value;
          });
          wrapper.appendChild(titleField);
        }

        const textArea = document.createElement('textarea');
        textArea.value = (type === 'callout' ? block.text : block.text) || block.content || '';
        textArea.placeholder = type === 'paragraph' ? 'Paragraph text' : 'Callout text';
        textArea.addEventListener('input', function () {
          if (type === 'callout') {
            currentBlocks[blockIdx].text = this.value;
          } else {
            if ('text' in block) {
              currentBlocks[blockIdx].text = this.value;
            } else {
              currentBlocks[blockIdx].content = this.value;
            }
          }
        });
        wrapper.appendChild(textArea);

      } else if (type === 'bullets') {
        const items = Array.isArray(block.items) ? block.items : [];
        // ensure the block has an items array we can mutate
        if (!Array.isArray(currentBlocks[blockIdx].items)) {
          currentBlocks[blockIdx].items = items.slice();
        }

        const listContainer = document.createElement('div');

        function renderBulletRows() {
          listContainer.innerHTML = '';
          currentBlocks[blockIdx].items.forEach(function (item, itemIdx) {
            const row = document.createElement('div');
            row.className = 'edit-bullet-row';

            const ta = document.createElement('textarea');
            ta.value = item || '';
            ta.rows = 1;
            ta.addEventListener('input', function () {
              currentBlocks[blockIdx].items[itemIdx] = this.value;
            });

            const removeBtn = document.createElement('button');
            removeBtn.type = 'button';
            removeBtn.className = 'btn-remove';
            removeBtn.textContent = '−';
            removeBtn.addEventListener('click', function () {
              currentBlocks[blockIdx].items.splice(itemIdx, 1);
              renderBulletRows();
            });

            row.appendChild(ta);
            row.appendChild(removeBtn);
            listContainer.appendChild(row);
          });
        }
        renderBulletRows();

        const addBtn = document.createElement('button');
        addBtn.type = 'button';
        addBtn.className = 'edit-block-add';
        addBtn.textContent = '+ Add bullet';
        addBtn.addEventListener('click', function () {
          currentBlocks[blockIdx].items.push('');
          renderBulletRows();
        });

        wrapper.appendChild(listContainer);
        wrapper.appendChild(addBtn);

      } else if (type === 'menu_items') {
        // Schema: { type: "menu_items", category: "...", items: [{name, description}] }
        if (!Array.isArray(currentBlocks[blockIdx].items)) {
          currentBlocks[blockIdx].items = JSON.parse(
            JSON.stringify(Array.isArray(block.items) ? block.items : [])
          );
        }

        const catNameInput = document.createElement('input');
        catNameInput.type = 'text';
        catNameInput.value = block.category || '';
        catNameInput.placeholder = 'Category name';
        catNameInput.style.marginBottom = '8px';
        catNameInput.addEventListener('input', function () {
          currentBlocks[blockIdx].category = this.value;
        });
        wrapper.appendChild(catNameInput);

        const itemsDiv = document.createElement('div');

        function renderMenuItemRows() {
          itemsDiv.innerHTML = '';
          (currentBlocks[blockIdx].items || []).forEach(function (mi, miIdx) {
            const row = document.createElement('div');
            row.className = 'edit-menu-item-row';

            const nameInput = document.createElement('input');
            nameInput.type = 'text';
            nameInput.value = mi.name || '';
            nameInput.placeholder = 'Item name';
            nameInput.addEventListener('input', function () {
              currentBlocks[blockIdx].items[miIdx].name = this.value;
            });

            const descTa = document.createElement('textarea');
            descTa.value = mi.description || '';
            descTa.placeholder = 'Description';
            descTa.rows = 1;
            descTa.addEventListener('input', function () {
              currentBlocks[blockIdx].items[miIdx].description = this.value;
            });

            const removeBtn = document.createElement('button');
            removeBtn.type = 'button';
            removeBtn.className = 'btn-remove';
            removeBtn.textContent = '−';
            removeBtn.addEventListener('click', function () {
              currentBlocks[blockIdx].items.splice(miIdx, 1);
              renderMenuItemRows();
            });

            row.appendChild(nameInput);
            row.appendChild(descTa);
            row.appendChild(removeBtn);
            itemsDiv.appendChild(row);
          });
        }
        renderMenuItemRows();

        const addItemBtn = document.createElement('button');
        addItemBtn.type = 'button';
        addItemBtn.className = 'edit-block-add';
        addItemBtn.textContent = '+ Add item';
        addItemBtn.addEventListener('click', function () {
          currentBlocks[blockIdx].items.push({ name: '', description: '' });
          renderMenuItemRows();
        });

        wrapper.appendChild(itemsDiv);
        wrapper.appendChild(addItemBtn);

      } else if (type === 'image') {
        const notice = document.createElement('div');
        notice.className = 'edit-block-readonly';
        notice.textContent = 'Image block — not directly editable. Use the guidance field below to request changes.';
        wrapper.appendChild(notice);

      } else if (type === 'table') {
        const notice = document.createElement('div');
        notice.className = 'edit-block-readonly';
        notice.textContent = 'Table block — not directly editable. Use the guidance field below to request changes.';
        wrapper.appendChild(notice);

      } else {
        // Fallback: JSON preview (read-only)
        const pre = document.createElement('div');
        pre.className = 'edit-block-readonly';
        pre.textContent = JSON.stringify(block, null, 2);
        wrapper.appendChild(pre);
      }

      blocksContainer.appendChild(wrapper);
    });
  }

  // ── Open / close modal ──────────────────────────────────────
  function openModal({ planId, sectionId, sectionTitle }) {
    currentPlanId = planId;
    currentSectionId = sectionId;
    currentSectionTitle = sectionTitle;
    titleInput.value = sectionTitle;
    commentInput.value = '';
    errorBox.hidden = true;
    errorBox.textContent = '';
    submitBtn.disabled = false;
    submitLabel.textContent = 'Regenerate now';
    if (queueBtn) queueBtn.disabled = false;
    if (deleteBtn) { deleteBtn.disabled = false; deleteBtn.textContent = '🗑 Delete section'; }

    // Deep-clone blocks from the injected map
    const sectionData = (window.__CURRENT_PLAN_SECTIONS__ || {})[sectionId];
    currentBlocks = sectionData && Array.isArray(sectionData.blocks)
      ? JSON.parse(JSON.stringify(sectionData.blocks))
      : [];

    renderBlocksEditor();
    backdrop.hidden = false;
    setTimeout(() => commentInput.focus(), 10);
  }

  function closeModal() {
    backdrop.hidden = true;
    currentPlanId = null;
    currentSectionId = null;
    currentSectionTitle = null;
    currentBlocks = [];
  }

  function showError(message) {
    errorBox.textContent = message;
    errorBox.hidden = false;
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

  function setPendingVisible(sectionId, visible) {
    const rows = document.querySelectorAll(`.section-row[data-section-id="${sectionId}"]`);
    rows.forEach((row) => {
      const actions = row.querySelector('.section-row-actions');
      if (!actions) return;
      const existing = actions.querySelector('.pending-badge');
      if (visible && !existing) {
        const b = document.createElement('span');
        b.className = 'pending-badge';
        b.title = 'You have queued an edit for this section.';
        b.textContent = 'Pending';
        actions.insertBefore(b, actions.firstChild);
      } else if (!visible && existing) {
        existing.remove();
      }
    });
  }

  function updateRegenPlanButton(pendingIds) {
    const btn = document.getElementById('regenPlanBtn');
    if (!btn) return;
    const count = (pendingIds || []).length;
    const countEl = document.getElementById('regenPlanCount');
    if (countEl) countEl.textContent = count ? ` (${count})` : '';
    if (count > 0) btn.removeAttribute('hidden');
    else btn.setAttribute('hidden', '');
  }

  async function refetchPending(planId) {
    try {
      const resp = await fetch(`/api/plans/${encodeURIComponent(planId)}/pending`);
      const body = await resp.json();
      const ids = Object.keys(body.edits || {});
      document.querySelectorAll('.section-row').forEach(row => {
        setPendingVisible(row.dataset.sectionId, ids.includes(row.dataset.sectionId));
      });
      updateRegenPlanButton(ids);
    } catch (_) {}
  }

  // ── Regenerate now (single section) ────────────────────────
  async function submit() {
    const comment = commentInput.value.trim();
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
            regenerate_image: false,
          }),
        },
      );
      let body;
      try {
        body = await resp.json();
      } catch (_) {
        const raw = await resp.text().catch(() => '');
        const preview = (raw || '').replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim().slice(0, 300);
        showError(`Server error (${resp.status} ${resp.statusText || ''}).${preview ? ' ' + preview : ''}`);
        submitBtn.disabled = false;
        submitLabel.textContent = 'Regenerate now';
        return;
      }
      if (!resp.ok || !body.ok) {
        const label = body.error_type ? `[${body.error_type}] ` : '';
        showError(`${label}${body.error || `Request failed (${resp.status}).`}`);
        submitBtn.disabled = false;
        submitLabel.textContent = 'Regenerate now';
        return;
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

      updateIframeAndScroll(body.plan_html, currentSectionId);
      if (currentSectionId) setRevertVisible(currentSectionId, true);
      const regeneratedTitle = currentSectionTitle || 'Section';
      const pid = currentPlanId;
      closeModal();
      showToast(`Section "${regeneratedTitle}" regenerated successfully`);
      refetchPending(pid);
    } catch (err) {
      showError(`Network error: ${err.message || err}`);
      submitBtn.disabled = false;
      submitLabel.textContent = 'Regenerate now';
    }
  }

  // ── Save to queue ───────────────────────────────────────────
  async function queue() {
    errorBox.hidden = true;
    queueBtn.disabled = true;

    try {
      const resp = await fetch(
        `/api/plans/${encodeURIComponent(currentPlanId)}/sections/${encodeURIComponent(currentSectionId)}/pending`,
        {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            blocks: currentBlocks,
            user_comment: commentInput.value.trim(),
          }),
        },
      );
      let body;
      try { body = await resp.json(); } catch (_) { body = null; }
      if (!resp.ok || !body || !body.ok) {
        const msg = (body && (body.error || body.error_type)) || `Request failed (${resp.status}).`;
        showError(`Queue failed: ${msg}`);
        queueBtn.disabled = false;
        return;
      }
      const sectionTitle = currentSectionTitle || 'Section';
      const pid = currentPlanId;
      const sid = currentSectionId;
      // Remember queued blocks so reopening the section shows the user's edit
      const map = window.__CURRENT_PLAN_SECTIONS__ || {};
      if (sid && map[sid]) {
        map[sid].blocks = JSON.parse(JSON.stringify(currentBlocks || []));
        window.__CURRENT_PLAN_SECTIONS__ = map;
      }
      queueBtn.disabled = false;
      closeModal();
      showToast(`Section "${sectionTitle}" queued`);
      refetchPending(pid);
    } catch (err) {
      showError(`Network error: ${err.message || err}`);
      queueBtn.disabled = false;
    }
  }

  // ── Regenerate full plan ────────────────────────────────────
  // Overlay controller for full-plan regeneration
  let regenElapsedTimer = null;
  function showRegenOverlay(pendingEdits) {
    const overlay = document.getElementById('regenOverlay');
    const elapsedEl = document.getElementById('regenElapsed');
    const list = document.getElementById('regenSectionsList');
    const ul = document.getElementById('regenSectionsUl');
    if (!overlay) return;

    // Populate section titles from sidebar rows so the user sees what's being applied
    if (ul) {
      ul.innerHTML = '';
      const ids = Object.keys(pendingEdits || {});
      ids.forEach(sid => {
        const row = document.querySelector(`.section-row[data-section-id="${sid}"] .section-row-title`);
        const title = row ? row.textContent.trim() : sid;
        const li = document.createElement('li');
        li.textContent = title;
        ul.appendChild(li);
      });
      if (list) list.hidden = ids.length === 0;
    }

    // Start elapsed timer
    const startedAt = Date.now();
    const tick = () => {
      const s = Math.floor((Date.now() - startedAt) / 1000);
      const mm = String(Math.floor(s / 60)).padStart(2, '0');
      const ss = String(s % 60).padStart(2, '0');
      if (elapsedEl) elapsedEl.textContent = `${mm}:${ss}`;
    };
    tick();
    clearInterval(regenElapsedTimer);
    regenElapsedTimer = setInterval(tick, 1000);

    overlay.hidden = false;
  }

  function hideRegenOverlay() {
    const overlay = document.getElementById('regenOverlay');
    if (overlay) overlay.hidden = true;
    clearInterval(regenElapsedTimer);
    regenElapsedTimer = null;
  }

  async function regenerateFullPlan() {
    const btn = document.getElementById('regenPlanBtn');
    if (!btn) return;
    const planId = btn.dataset.planId;
    if (!confirm('Regenerate the full plan using your queued edits? This may take a few minutes and costs an API call.')) return;

    // Fetch current pending edits to show in the overlay (and confirm they exist server-side)
    let pendingEdits = {};
    try {
      const pre = await fetch(`/api/plans/${encodeURIComponent(planId)}/pending`);
      const preBody = await pre.json();
      pendingEdits = (preBody && preBody.edits) || {};
    } catch (_) { /* overlay still shows without the list */ }

    btn.disabled = true;
    const originalHTML = btn.innerHTML;
    btn.textContent = 'Regenerating plan…';
    showRegenOverlay(pendingEdits);

    try {
      const resp = await fetch(`/api/plans/${encodeURIComponent(planId)}/regenerate-plan`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      });
      let body; try { body = await resp.json(); } catch (_) { body = null; }
      if (!resp.ok || !body || !body.ok) {
        const msg = (body && (body.error || body.error_type)) || `Request failed (${resp.status}).`;
        showToast(`Regenerate failed: ${msg}`, 'error');
        return;
      }
      updateIframeAndScroll(body.plan_html, null);
      document.querySelectorAll('.pending-badge').forEach(b => b.remove());
      document.querySelectorAll('.stale-badge').forEach(b => b.remove());
      updateRegenPlanButton([]);
      const n = (body.applied_edit_section_ids || []).length;
      showToast(`Plan regenerated — ${n} edit${n === 1 ? '' : 's'} applied`);
    } catch (err) {
      showToast(`Network error: ${err.message || err}`, 'error');
    } finally {
      hideRegenOverlay();
      btn.disabled = false;
      btn.innerHTML = originalHTML;
    }
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
      refetchPending(planId);
    } catch (err) {
      showToast(`Network error: ${err.message || err}`, 'error');
    }
  }

  // ── Event wiring ────────────────────────────────────────────
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
      return;
    }
    const restoreBtn = event.target.closest('.restore-section-btn');
    if (restoreBtn) {
      restoreDeletedSection({
        planId: restoreBtn.dataset.planId,
        sectionId: restoreBtn.dataset.sectionId,
        sectionTitle: restoreBtn.dataset.sectionTitle,
      });
    }
  });

  async function deleteSection() {
    if (!currentPlanId || !currentSectionId) return;
    const title = currentSectionTitle || 'this section';
    if (!confirm(`Delete "${title}" from the plan? You can Restore it later from the sidebar.`)) return;

    deleteBtn.disabled = true;
    deleteBtn.textContent = 'Deleting…';

    try {
      const resp = await fetch(
        `/api/plans/${encodeURIComponent(currentPlanId)}/sections/${encodeURIComponent(currentSectionId)}`,
        { method: 'DELETE', headers: { 'Content-Type': 'application/json' } },
      );
      let body; try { body = await resp.json(); } catch (_) { body = null; }
      if (!resp.ok || !body || !body.ok) {
        const msg = (body && (body.error || body.error_type)) || `Request failed (${resp.status}).`;
        showError(`Delete failed: ${msg}`);
        deleteBtn.disabled = false;
        deleteBtn.textContent = '🗑 Delete section';
        return;
      }

      // Remove the section's row and any cached block data client-side
      const sid = currentSectionId;
      const sectionTitle = currentSectionTitle;
      const planId = currentPlanId;
      const map = window.__CURRENT_PLAN_SECTIONS__ || {};
      if (sid) delete map[sid];

      // Remove from main list, add to deleted list
      const row = document.querySelector(`.section-row[data-section-id="${sid}"]`);
      if (row) row.remove();
      addToDeletedList(sid, sectionTitle, planId);

      // Update frame
      updateIframeAndScroll(body.plan_html, null);

      // Resync pending state
      refetchPending(planId);

      closeModal();
      showToast(`Section "${sectionTitle}" deleted`);
    } catch (err) {
      showError(`Network error: ${err.message || err}`);
      deleteBtn.disabled = false;
      deleteBtn.textContent = '🗑 Delete section';
    }
  }

  function addToDeletedList(sectionId, sectionTitle, planId) {
    let container = document.querySelector('.section-list-deleted');
    if (!container) {
      const panel = document.querySelector('.section-list-panel');
      if (!panel) return;
      container = document.createElement('div');
      container.className = 'section-list-deleted';
      const h = document.createElement('h3');
      h.textContent = 'Deleted sections';
      container.appendChild(h);
      panel.appendChild(container);
    }
    // Skip if already there
    if (container.querySelector(`.section-row-deleted[data-section-id="${sectionId}"]`)) return;

    const row = document.createElement('div');
    row.className = 'section-row-deleted';
    row.dataset.sectionId = sectionId;

    const titleEl = document.createElement('div');
    titleEl.className = 'section-row-title';
    titleEl.title = sectionTitle;
    titleEl.textContent = sectionTitle;

    const actions = document.createElement('div');
    actions.className = 'section-row-actions';
    const restoreBtn = document.createElement('button');
    restoreBtn.type = 'button';
    restoreBtn.className = 'restore-section-btn';
    restoreBtn.dataset.sectionId = sectionId;
    restoreBtn.dataset.sectionTitle = sectionTitle;
    restoreBtn.dataset.planId = planId;
    restoreBtn.textContent = 'Restore';
    actions.appendChild(restoreBtn);

    row.appendChild(titleEl);
    row.appendChild(actions);
    container.appendChild(row);
  }

  async function restoreDeletedSection({ planId, sectionId, sectionTitle }) {
    if (!confirm(`Restore "${sectionTitle}" to the plan?`)) return;
    try {
      const resp = await fetch(
        `/api/plans/${encodeURIComponent(planId)}/sections/${encodeURIComponent(sectionId)}/restore`,
        { method: 'POST', headers: { 'Content-Type': 'application/json' } },
      );
      let body; try { body = await resp.json(); } catch (_) { body = null; }
      if (!resp.ok || !body || !body.ok) {
        const msg = (body && (body.error || body.error_type)) || `Request failed (${resp.status}).`;
        showToast(`Restore failed: ${msg}`, 'error');
        return;
      }

      // Re-add to the client-side sections map so Edit works again
      const map = window.__CURRENT_PLAN_SECTIONS__ || {};
      map[sectionId] = body.section;
      window.__CURRENT_PLAN_SECTIONS__ = map;

      // Remove from deleted list in sidebar
      const drow = document.querySelector(`.section-row-deleted[data-section-id="${sectionId}"]`);
      if (drow) drow.remove();
      // Remove the "Deleted sections" heading if empty
      const container = document.querySelector('.section-list-deleted');
      if (container && !container.querySelector('.section-row-deleted')) {
        container.remove();
      }

      updateIframeAndScroll(body.plan_html, sectionId);
      showToast(`Section "${sectionTitle}" restored — reload the page to see it in the sidebar`);
    } catch (err) {
      showToast(`Network error: ${err.message || err}`, 'error');
    }
  }

  if (deleteBtn) deleteBtn.addEventListener('click', deleteSection);

  closeBtn.addEventListener('click', closeModal);
  cancelBtn.addEventListener('click', closeModal);
  submitBtn.addEventListener('click', submit);
  queueBtn.addEventListener('click', queue);

  const regenPlanBtn = document.getElementById('regenPlanBtn');
  if (regenPlanBtn) regenPlanBtn.addEventListener('click', regenerateFullPlan);

  backdrop.addEventListener('click', (event) => {
    if (event.target === backdrop) closeModal();
  });

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && !backdrop.hidden) closeModal();
  });
})();
