# Fix Chart & Volume Pane Layout

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the chart and volume pane sizing, placement, and formatting so they correctly fill their container and display properly.

**Architecture:** The chart area uses a nested flex layout: `.layout` (grid) → `.chart-pane` (flex column) → `.chart-panes-host` (flex column) → `.chart-pane-block` (flex children) → `.chart-host` / `.volume-host` (actual chart containers). The root cause is that `.chart-pane-block` is NOT a flex container, so its children can't fill it via flex properties. Additionally `.volume-host` has conflicting flex values that don't fill its parent.

**Tech Stack:** CSS flexbox, lightweight-charts (JS charting library)

---

## Root Cause Analysis

The CSS layout chain has 3 bugs:

```
.chart-panes-host          (flex column) ✓
  └── .chart-pane-block     (NOT a flex container) ← BUG 1
        ├── .chart-host     (flex: 1 1 auto; min-height: 200px) ← BUG 2 (min-height)
        └── .volume-host    (flex: 0 0 100px) ← BUG 3 (doesn't fill parent)
```

**Bug 1:** `.chart-pane-block` has no `display: flex`. Its children use flex properties (`flex: 1 1 auto`, `flex: 0 0 100px`) but these only work if the parent is a flex container. Without it, children are plain block elements.

**Bug 2:** `.chart-host` has `min-height: 200px` — too large, prevents the main chart from shrinking below 200px even when the volume pane needs space.

**Bug 3:** `.volume-host` has `flex: 0 0 100px` but its parent `.chart-pane-block.is-subpane` is `flex: 0 0 180px`. The volume chart only renders at 100px, leaving 80px dead space.

---

## Task 1: Fix `.chart-pane-block` to be a flex container

**Files:**
- Modify: `frontend/style.css:866-871`

- [ ] **Step 1: Add display:flex to .chart-pane-block**

```css
.chart-pane-block {
    display: flex;
    flex-direction: column;
    flex: 1 1 auto;
    min-height: 0;
    position: relative;
    border-bottom: 1px solid var(--border-soft);
    overflow: hidden;
}
```

Key changes from current:
- Added `display: flex; flex-direction: column;` — makes children fill via flex
- Added `min-height: 0;` — allows the block to shrink below its content size
- Added `overflow: hidden;` — clips children that overflow

- [ ] **Step 2: Commit**

```bash
git add frontend/style.css
git commit -m "fix(chart): make .chart-pane-block a flex container so children fill properly"
```

---

## Task 2: Fix `.chart-host` min-height

**Files:**
- Modify: `frontend/style.css:376-380`

- [ ] **Step 1: Reduce min-height on .chart-host**

```css
.chart-host {
    flex: 1 1 auto;
    min-height: 0;
    position: relative;
}
```

Key change: `min-height: 200px` → `min-height: 0` — allows the main chart to shrink when the window is small or when sub-panes need space. Lightweight-charts handles its own minimum rendering size.

- [ ] **Step 2: Commit**

```bash
git add frontend/style.css
git commit -m "fix(chart): remove forced min-height:200px on .chart-host"
```

---

## Task 3: Fix `.volume-host` to fill its parent

**Files:**
- Modify: `frontend/style.css:907-912`

- [ ] **Step 1: Make .volume-host fill its parent block**

```css
.volume-host {
    flex: 1 1 auto;
    min-height: 0;
    position: relative;
}
```

Key change: `flex: 0 0 100px; min-height: 60px;` → `flex: 1 1 auto; min-height: 0;` — the volume chart now fills its parent `.chart-pane-block.is-subpane` (which is `flex: 0 0 180px`). Remove the `border-top` since the parent already has `border-bottom`.

- [ ] **Step 2: Commit**

```bash
git add frontend/style.css
git commit -m "fix(chart): .volume-host fills parent .chart-pane-block"
```

---

## Task 4: Reduce sub-pane height and polish

**Files:**
- Modify: `frontend/style.css:877-879`

- [ ] **Step 1: Reduce sub-pane fixed height**

```css
.chart-pane-block.is-subpane {
    flex: 0 0 120px;
}
```

Key change: `180px` → `120px` — the volume pane doesn't need to be that tall. 120px is enough to show volume bars clearly while giving more space to the main price chart.

- [ ] **Step 2: Verify time-presets bar positioning**

The `.time-presets` bar sits between `.chart-panes-host` and `.equity-pane` in the flex column of `.chart-pane`. It should already render correctly as `flex: 0 0 auto`. No change needed.

- [ ] **Step 3: Commit**

```bash
git add frontend/style.css
git commit -m "fix(chart): reduce sub-pane height from 180px to 120px"
```

---

## Task 5: Verify and run tests

- [ ] **Step 1: Run Bun tests**

```bash
cd /mnt/data/home/jango/Git/pynescript && bun test frontend/tests/
```

Expected: 33 pass, 0 fail

- [ ] **Step 2: Run TypeScript check**

```bash
cd /mnt/data/home/jango/Git/pynescript/frontend && bunx tsc --noEmit
```

Expected: no output (clean)

- [ ] **Step 3: Visual verification**

Start the dev server and open http://localhost:8081:
- Main price chart should fill available vertical space
- Volume bars should render at ~120px height below the price chart
- No dead space between panes
- Resize the window — charts should resize proportionally
- Run a demo script (e.g., SMA Cross) — overlays should appear correctly

---

## Summary of All CSS Changes

### Before (broken):
```css
.chart-pane-block {
    flex: 1 1 auto;
    min-height: 60px;
    position: relative;
    border-bottom: 1px solid var(--border-soft);
}

.chart-pane-block.is-subpane {
    flex: 0 0 180px;
}

.chart-host {
    flex: 1 1 auto;
    min-height: 200px;
    position: relative;
}

.volume-host {
    flex: 0 0 100px;
    min-height: 60px;
    position: relative;
    border-top: 1px solid var(--border-soft);
}
```

### After (fixed):
```css
.chart-pane-block {
    display: flex;
    flex-direction: column;
    flex: 1 1 auto;
    min-height: 0;
    position: relative;
    border-bottom: 1px solid var(--border-soft);
    overflow: hidden;
}

.chart-pane-block.is-subpane {
    flex: 0 0 120px;
}

.chart-host {
    flex: 1 1 auto;
    min-height: 0;
    position: relative;
}

.volume-host {
    flex: 1 1 auto;
    min-height: 0;
    position: relative;
}
```
