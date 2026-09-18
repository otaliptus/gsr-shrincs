(() => {
  const data = JSON.parse(document.getElementById('opcode-data').textContent);
  const panel = document.getElementById('opcode-panel');
  const triggers = [...document.querySelectorAll('[data-opcodes]')];
  let active = null;
  let pinned = false;
  let timer;

  function close() {
    clearTimeout(timer);
    if (active) active.setAttribute('aria-expanded', 'false');
    active = null;
    pinned = false;
    panel.hidden = true;
  }

  function position() {
    if (!active) return;
    const rect = active.getBoundingClientRect();
    const gap = 10;
    const width = panel.offsetWidth;
    const height = panel.offsetHeight;
    const below = rect.bottom + gap;
    const top = below + height <= innerHeight - gap ? below : Math.max(gap, rect.top - height - gap);
    panel.style.left = `${Math.max(gap, Math.min(rect.left, innerWidth - width - gap))}px`;
    panel.style.top = `${top}px`;
  }

  function add(tag, text, parent = panel) {
    const element = document.createElement(tag);
    element.textContent = text;
    parent.append(element);
    return element;
  }

  function show(trigger) {
    clearTimeout(timer);
    if (active === trigger && !panel.hidden) return;
    if (active) active.setAttribute('aria-expanded', 'false');
    active = trigger;
    const details = data[trigger.dataset.opcodes];
    panel.replaceChildren();
    const dismiss = add('button', '×');
    dismiss.type = 'button';
    dismiss.className = 'opcode-close';
    dismiss.setAttribute('aria-label', 'Close opcode list');
    dismiss.addEventListener('click', () => {
      const previous = active;
      previous.focus();
      close();
    });
    add('strong', details.title);
    add('p', details.note);
    if (details.opcodes.length) {
      add('h3', 'Full opcode list');
      const list = add('div', '');
      list.className = 'opcode-chips';
      for (const name of details.opcodes) add('code', name, list);
    }
    if (details.pushes.length) {
      add('h3', 'Direct data pushes');
      add('p', `${details.pushes.join(', ')} bytes. Each length has its own push byte. Pushed values are data, not instructions.`);
    }
    trigger.setAttribute('aria-expanded', 'true');
    panel.hidden = false;
    panel.scrollTop = 0;
    position();
  }

  function later() {
    clearTimeout(timer);
    if (!pinned && document.activeElement !== active && !panel.contains(document.activeElement)) timer = setTimeout(close, 180);
  }

  for (const trigger of triggers) {
    trigger.addEventListener('pointerenter', event => {
      if (event.pointerType === 'touch' || pinned) return;
      show(trigger);
    });
    trigger.addEventListener('pointerleave', later);
    trigger.addEventListener('focus', () => { pinned = false; show(trigger); });
    trigger.addEventListener('blur', event => {
      if (!panel.contains(event.relatedTarget)) { pinned = false; later(); }
    });
    trigger.addEventListener('click', () => {
      if (active === trigger && pinned) close();
      else { show(trigger); pinned = true; }
    });
    // SVG chart rows have button semantics but need keyboard activation.
    trigger.addEventListener('keydown', event => {
      if (trigger.tagName.toLowerCase() === 'g' && ['Enter', ' '].includes(event.key)) {
        event.preventDefault();
        trigger.dispatchEvent(new MouseEvent('click', { bubbles: true }));
      }
    });
  }
  panel.addEventListener('pointerenter', () => clearTimeout(timer));
  panel.addEventListener('pointerleave', later);
  panel.addEventListener('focusout', event => {
    if (!panel.contains(event.relatedTarget) && event.relatedTarget !== active) close();
  });
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && active) {
      if (panel.contains(document.activeElement)) active.focus();
      close();
    }
  });
  document.addEventListener('pointerdown', event => {
    if (active && !active.contains(event.target) && !panel.contains(event.target)) close();
  });
  window.addEventListener('resize', position);
  document.addEventListener('scroll', event => {
    if (!panel.contains(event.target)) position();
  }, true);
})();
