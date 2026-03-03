import { loadStripe, type Stripe } from "@stripe/stripe-js";

let stripePromise: Promise<Stripe | null>;

export function getStripe() {
  if (!stripePromise) {
    stripePromise = loadStripe(
      process.env.NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY || ""
    );
  }
  return stripePromise;
}

export function redirectToCheckout(sessionUrl: string) {
  window.location.href = sessionUrl;
}

export function redirectToPortal(portalUrl: string) {
  window.location.href = portalUrl;
}
