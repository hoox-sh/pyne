// PYNE Commercial checkout button (Polar.sh, zero-ops).
// Usage in MDX: import { PolarCheckout } from "/snippets/polar-checkout.jsx"
// Set NEXT_PUBLIC_POLAR_CHECKOUT_URL or default below after creating the
// Polar product (one product: PYNE Commercial Licence, EUR 299 one-time).
export function PolarCheckout() {
  const url =
    (typeof process !== "undefined" && process.env?.NEXT_PUBLIC_POLAR_CHECKOUT_URL) ||
    "https://polar.sh/hoox/checkout/pyne-commercial";
  return (
    <a
      href={url}
      style={{
        display: "inline-block",
        padding: "12px 22px",
        borderRadius: 10,
        fontWeight: 700,
        textDecoration: "none",
      }}
    >
      Buy Commercial Licence — €299 one-time
    </a>
  );
}
