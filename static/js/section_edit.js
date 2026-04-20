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
        const categories = Array.isArray(block.categories) ? block.categories : [];
        if (!Array.isArray(currentBlocks[blockIdx].categories)) {
          currentBlocks[blockIdx].categories = JSON.parse(JSON.stringify(categories));
        }

        const catContainer = document.createElement('div');

        function renderCategories() {
          catContainer.innerHTML = '';
          currentBlocks[blockIdx].categories.forEach(function (cat, catIdx) {
            const catHeader = document.createElement('div');
            catHeader.className = 'edit-block-header';
            catHeader.style.marginTop = catIdx > 0 ? '10px' : '0';

            const catNameInput = document.createElement('input');
            catNameInput.type = 'text';
            catNameInput.value = cat.category || '';
            catNameInput.placeholder = 'Category name';
            catNameInput.style.marginBottom = '6px';
            catNameInput.addEventListener('input', function () {
              currentBlocks[blockIdx].categories[catIdx].category = this.value;
            });

            const itemsDiv = document.createElement('div');
            const menuItems = Array.isArray(cat.items) ? cat.items : [];

            function renderMenuItemRows() {
              itemsDiv.innerHTML = '';
              (currentBlocks[blockIdx].categories[catIdx].items || []).forEach(function (mi, miIdx) {
                const row = document.createElement('div');
                row.className = 'edit-menu-item-row';

                const nameInput = document.createElement('input');
                nameInput.type = 'text';
                nameInput.value = mi.name || '';
                nameInput.placeholder = 'Item name';
                nameInput.addEventListener('input', function () {
                  currentBlocks[blockIdx].categories[catIdx].items[miIdx].name = this.value;
                });

                const descTa = document.createElement('textarea');
                descTa.value = mi.description || '';
                descTa.placeholder = 'Description';
                descTa.rows = 1;
                descTa.addEventListener('input', function () {
                  currentBlocks[blockIdx].categories[catIdx].items[miIdx].description = this.value;
                });

                const removeBtn = document.createElement('button');
                removeBtn.type = 'button';
                removeBtn.className = 'btn-remove';
                removeBtn.textContent = '−';
                removeBtn.addEventListener('click', function () {
                  currentBlocks[blockIdx].categories[catIdx].items.splice(miIdx, 1);
                  renderMenuItemRows();
                });

                row.appendChild(nameInput);
                row.appendChild(descTa);
                row.appendChild(removeBtn);
                itemsDiv.appendChild(row);
              });

              const addItemBtn = document.createElement('button');
              addItemBtn.type = 'button';
              addItemBtn.className = 'edit-block-add';
              addItemBtn.textContent = '+ Add item';
              addItemBtn.addEventListener('click', function () {
                if (!Array.isArray(currentBlocks[blockIdx].categories[catIdx].items)) {
                  currentBlocks[blockIdx].categories[catIdx].items = [];
                }
                currentBlocks[blockIdx].categories[catIdx].items.push({ name: '', description: '' });
                renderMenuItemRows();
              });
              itemsDiv.appendChild(addItemBtn);
            }

            if (!Array.isArray(currentBlocks[blockIdx].categories[catIdx].items)) {
              currentBlocks[blockIdx].categories[catIdx].items = JSON.parse(JSON.stringify(menuItems));
            }
            renderMenuItemRows();

            catContainer.appendChild(catNameInput);
            catContainer.appendChild(itemsDiv);
          });
        }
        renderCategories();
        wrapper.appendChild(catContainer);

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
      closeModal();
      showToast(`Section "${sectionTitle}" queued`);
      refetchPending(pid);
    } catch (err) {
      showError(`Network error: ${err.message || err}`);
      queueBtn.disabled = false;
    }
  }

  // ── Regenerate full plan ────────────────────────────────────
  async function regenerateFullPlan() {
    const btn = document.getElementById('regenPlanBtn');
    if (!btn) return;
    const planId = btn.dataset.planId;
    if (!confirm('Regenerate the full plan using your queued edits? This may take a few minutes and costs an API call.')) return;
    btn.disabled = true;
    const originalHTML = btn.innerHTML;
    btn.textContent = 'Regenerating plan…';
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
    }
  });

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
