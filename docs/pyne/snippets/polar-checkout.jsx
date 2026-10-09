// PYNE Commercial checkout button — RETIRED until launch.
// Commercial licensing is upcoming (see reference/commercial.mdx).
// This snippet renders a disabled placeholder so any lingering import
// stays safe. Do not point it at a live checkout before launch.
export function PolarCheckout() {
  return (
    <span
      aria-disabled="true"
      style={{
        display: "inline-block",
        padding: "12px 22px",
        borderRadius: 10,
        fontWeight: 700,
        textDecoration: "none",
        opacity: 0.55,
        cursor: "not-allowed",
      }}
    >
      Commercial Licence — Upcoming
    </span>
  );
}
