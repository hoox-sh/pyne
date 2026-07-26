import { Component, onCleanup } from 'solid-js';

interface Props {
  /** grow-right: drag right increases width (left-side panels)
   *  grow-left:  drag left increases width (right-side panels) */
  direction: 'grow-right' | 'grow-left';
  getWidth: () => number;
  setWidth: (width: number) => void;
  min?: number;
  max?: number;
  class?: string;
}

/**
 * Vertical drag handle between panels. 2px interactive hit area with Hell Flieder hover.
 */
export const ResizeHandle: Component<Props> = (props) => {
  let dragging = false;
  let startX = 0;
  let startW = 0;

  const onPointerDown = (e: PointerEvent) => {
    e.preventDefault();
    dragging = true;
    startX = e.clientX;
    startW = props.getWidth();
    (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
  };

  const onPointerMove = (e: PointerEvent) => {
    if (!dragging) return;
    const dx = e.clientX - startX;
    const raw = props.direction === 'grow-right' ? startW + dx : startW - dx;
    const min = props.min ?? 140;
    const max = props.max ?? Math.floor(window.innerWidth * 0.8);
    props.setWidth(Math.min(Math.max(raw, min), max));
  };

  const onPointerUp = (e: PointerEvent) => {
    if (!dragging) return;
    dragging = false;
    try { (e.currentTarget as HTMLElement).releasePointerCapture(e.pointerId); } catch {}
    document.body.style.cursor = '';
    document.body.style.userSelect = '';
  };

  onCleanup(() => {
    document.body.style.cursor = '';
    document.body.style.userSelect = '';
  });

  return (
    <div
      class={`sc-resize-handle ${props.class || ''}`}
      role="separator"
      aria-orientation="vertical"
      title="Drag to resize"
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
      onPointerCancel={onPointerUp}
    />
  );
};
