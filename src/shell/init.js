import { mountNav } from "./nav.js";
import { mountStatusStrip, fetchSummary } from "./status.js";
import { mountOnboarding } from "./onboarding.js";

/**
 * @param {{ page: string, showStatus?: boolean, showOnboarding?: boolean }} options
 */
export async function initShell(options) {
  const { page, showStatus = true, showOnboarding = false } = options;

  const navSlot = document.querySelector("#shell-nav");
  const statusSlot = document.querySelector("#shell-status");
  const onboardingSlot = document.querySelector("#shell-onboarding");

  let summary = null;
  if (showStatus && statusSlot) {
    summary = await mountStatusStrip(statusSlot);
  } else if (showOnboarding) {
    summary = await fetchSummary();
  }

  if (navSlot) {
    mountNav(navSlot, page, summary?.agent || {});
  }

  if (showOnboarding && onboardingSlot) {
    mountOnboarding(onboardingSlot, summary);
  }
}
