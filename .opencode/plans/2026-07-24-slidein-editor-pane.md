# Slide-In Editor Pane + Wiring Fixes

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** Move the Pine Script editor (editor + results) to a resizable slide-in pane that opens from the left of the chart area. Verify and fix all data wiring (historical, live, overlays).

**Architecture:** The editor pane currently sits in a fixed 460px right grid column. It becomes an absolutely-positioned overlay inside `.chart-pane`, sliding in/out with CSS `transform: translateX()`. The layout grid loses the editor column — only watchlist + chart remain.

**Tech Stack:** CSS transform/transition, pointer events, localStorage

---

## File Map

| File | Change |
|------|--------|
| `frontend/index.html` | Move editor-pane inside chart-pane; add toggle button to topbar; add backdrop |
| `frontend/style.css` | Remove editor from grid; add slide-in, resize handle, backdrop, toggle button CSS |
| `frontend/src/main.js` | Add editor toggle wiring; verify pipeline |
| `frontend/src/ui/topbar.js` | Add editor-open state to topbar (optional badge) |

---

## Task 1: Restructure HTML — move editor into chart area

**Files:**
- Modify: `frontend/index.html:92-191`

- [ ] **Step 1: Change layout grid to 2 columns (watchlist + chart)**

Remove the editor-pane from the layout grid. Change:
```html
<main class="layout">
    <aside class="sidebar" id="watchlist-sidebar">...</aside>
    <section class="chart-pane">...</section>
    <aside class="editor-pane">...</aside>
</main>
```

To:
```html
<main class="layout">
    <aside class="sidebar" id="watchlist-sidebar">...</aside>
    <section class="chart-pane">
        <div class="chart-pane">
            <!-- existing chart content -->
        </div>
        <aside class="editor-pane" id="editor-slide">
            <div class="editor-resize-handle" id="editor-resize"></div>
            <div class="editor-pane-inner">
                <!-- existing editor content -->
            </div>
        </aside>
        <div id="editor-backdrop" class="editor-backdrop" hidden></div>
    </section>
</main>
```

- [ ] **Step 2: Add editor toggle button to topbar**

Add before the `topbar-spacer`:
```html
<button id="editor-toggle" class="btn btn-ghost" title="Toggle Editor (Ctrl+\)">📝 Editor</button>
```

---

## Task 2: CSS — slide-in pane, resize handle, backdrop

**Files:**
- Modify: `frontend/style.css`

- [ ] **Step 1: Change layout grid**

```css
.layout {
    grid-template-columns: 220px 1fr;
}
.layout.sidebar-collapsed {
    grid-template-columns: 0px 1fr;
}
```

- [ ] **Step 2: Chart pane gets position:relative for editor overlay**

`.chart-pane` already has `position: relative`. Keep it.

- [ ] **Step 3: Editor slide-in pane**

```css
.editor-pane {
    position: absolute;
    left: 0;
    top: 0;
    bottom: 0;
    width: 460px;
    max-width: 80vw;
    min-width: 280px;
    z-index: 20;
    display: flex;
    flex-direction: column;
    background: var(--bg-panel);
    border-right: 1px solid var(--border);
    transform: translateX(-100%);
    transition: transform 0.25s ease;
    box-shadow: 4px 0 20px rgba(0,0,0,0.5);
}
.editor-pane.open {
    transform: translateX(0);
}
```

- [ ] **Step 4: Editor inner content fills the pane**

```css
.editor-pane-inner {
    display: flex;
    flex-direction: column;
    flex: 1 1 auto;
    min-height: 0;
    overflow: hidden;
}
```

- [ ] **Step 5: Resize handle**

```css
.editor-resize-handle {
    position: absolute;
    right: -4px;
    top: 0;
    bottom: 0;
    width: 8px;
    cursor: col-resize;
    z-index: 5;
    background: transparent;
}
.editor-resize-handle:hover,
.editor-resize-handle.is-dragging {
    background: var(--accent);
    opacity: 0.3;
}
```

- [ ] **Step 6: Backdrop**

```css
.editor-backdrop {
    position: absolute;
    inset: 0;
    z-index: 15;
    background: rgba(0,0,0,0.3);
}
.editor-backdrop[hidden] {
    display: none;
}
```

---

## Task 3: JS — toggle, resize, keyboard shortcut

**Files:**
- Modify: `frontend/src/main.js`
- Modify: `frontend/src/ui/topbar.js` (optional)

- [ ] **Step 1: Add editor toggle logic in main.js bootstrap**

```js
// Editor toggle
const editorToggle = document.getElementById('editor-toggle');
const editorSlide = document.getElementById('editor-slide');
const editorBackdrop = document.getElementById('editor-backdrop');
let editorOpen = false;

function toggleEditor(open) {
    editorOpen = open !== undefined ? open : !editorOpen;
    editorSlide.classList.toggle('open', editorOpen);
    editorBackdrop.hidden = !editorOpen;
    // Resize charts after transition
    setTimeout(() => {
        // Trigger fitAll or ResizeObserver
        window.dispatchEvent(new Event('resize'));
    }, 300);
}

editorToggle.addEventListener('click', () => toggleEditor());

editorBackdrop.addEventListener('click', () => toggleEditor(false));

// Keyboard shortcut: Ctrl+\
document.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === '\\') {
        e.preventDefault();
        toggleEditor();
    }
});
```

- [ ] **Step 2: Resize handle logic**

```js
// Resize handle
const resizeHandle = document.getElementById('editor-resize');
let isDragging = false;
let startX = 0;
let startW = 0;

resizeHandle.addEventListener('mousedown', (e) => {
    isDragging = true;
    startX = e.clientX;
    startW = editorSlide.offsetWidth;
    resizeHandle.classList.add('is-dragging');
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
});

document.addEventListener('mousemove', (e) => {
    if (!isDragging) return;
    const newW = Math.max(280, Math.min(startW + (startX - e.clientX), window.innerWidth * 0.8));
    editorSlide.style.width = `${newW}px`;
});

document.addEventListener('mouseup', () => {
    if (isDragging) {
        isDragging = false;
        resizeHandle.classList.remove('is-dragging');
        document.body.style.cursor = '';
        document.body.style.userSelect = '';
    }
});
```

---

## Task 4: Verify wiring — historical, live, overlays

- [ ] **Step 1: Check historical data pipeline**

The flow: `loadHistorical()` → `setOhlcv(bars)` → candles on chart.
Verify by:
1. Load page
2. Click "Load" button
3. Confirm candles appear on chart
4. Run a script → overlays appear

- [ ] **Step 2: Check live streaming**

The flow: `toggleLive()` → `stream.start()` → `onBar` callback → `appendBar()` → chart updates.
1. Load historical data
2. Click "▶ Live"
3. Verify new candles appear (or at least no errors in console)

- [ ] **Step 3: Check overlay (indicator pane)**

For `overlay=false` scripts (like MACD, RSI SubPane):
1. Click a demo with `overlay=false`
2. Verify the indicator pane appears below volume with plots
3. Verify the time scale syncs with main chart

- [ ] **Step 4: Run tests**

```bash
cd /mnt/data/home/jango/Git/pynescript && bun test frontend/tests/
```
Expected: 33 pass, 0 fail

---

## Task 5: Commit

- [ ] **Step 1: Commit all changes**

```bash
git add -A
git commit -m "feat(editor): slide-in pane from left with resize handle

- Move editor from fixed right column to slide-in overlay
- Resize handle on right edge with drag-to-resize
- Backdrop closes editor on click
- Keyboard shortcut Ctrl+\ toggles editor
- Layout grid now 2 columns (watchlist + chart)
"
```
