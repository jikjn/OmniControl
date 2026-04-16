function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function fetchJson(url) {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Request failed: ${url} (${response.status})`);
  }
  return response.json();
}

function scoreInspectableTarget(target, preferNeedle = "") {
  if (!target || !target.webSocketDebuggerUrl) {
    return Number.NEGATIVE_INFINITY;
  }

  const normalizedPrefer = String(preferNeedle || "").toLowerCase();
  const title = target.title ?? "";
  const url = target.url ?? "";
  const normalizedTitle = title.toLowerCase();
  const normalizedUrl = url.toLowerCase();
  const type = target.type ?? "";
  let score = 0;

  if (normalizedPrefer) {
    if (normalizedTitle.includes(normalizedPrefer)) score += 1000;
    if (normalizedUrl.includes(normalizedPrefer)) score += 950;
  }

  if (type === "page") score += 200;
  else if (type === "webview") score += 150;
  else if (type === "iframe") score += 100;
  else score += 50;

  if (url && url !== "about:blank") score += 25;
  if (title) score += 10;
  if (normalizedUrl.startsWith("devtools://") || normalizedUrl.startsWith("chrome-devtools://")) score -= 500;
  if (normalizedUrl.startsWith("chrome-extension://")) score -= 200;
  if (normalizedTitle.startsWith("devtools")) score -= 100;

  return score;
}

function pickInspectableTarget(targets, preferNeedle = "", options = {}) {
  const requirePreference = Boolean(options.requirePreference);
  const normalizedPrefer = String(preferNeedle || "").toLowerCase();
  const ranked = [...targets]
    .map((target) => ({ target, score: scoreInspectableTarget(target, preferNeedle) }))
    .filter((item) => Number.isFinite(item.score))
    .filter((item) => !requirePreference || targetMatchesPreference(item.target, normalizedPrefer))
    .sort((left, right) => right.score - left.score);
  return ranked[0]?.target ?? null;
}

async function waitForInspectableTarget(baseUrl, preferNeedle = "", timeoutMs = 30000, intervalMs = 250, allowGenericFallback = true) {
  const deadline = Date.now() + timeoutMs;
  const preferDeadline = preferNeedle
    ? Date.now() + Math.min(timeoutMs - intervalMs, Math.max(5000, Math.floor(timeoutMs * 0.6)))
    : Date.now();
  let lastTargets = [];
  let lastError = null;
  let attempts = 0;

  while (Date.now() < deadline) {
    attempts += 1;
    try {
      lastTargets = await fetchJson(`${baseUrl}/json/list`);
      const preferredTarget = pickInspectableTarget(lastTargets, preferNeedle, { requirePreference: Boolean(preferNeedle) });
      if (preferredTarget) {
        return attachSelectionMeta(preferredTarget, attempts, true);
      }

      const fallbackTarget = pickInspectableTarget(lastTargets);
      if (fallbackTarget && (!preferNeedle || (allowGenericFallback && Date.now() >= preferDeadline))) {
        return attachSelectionMeta(fallbackTarget, attempts, false);
      }
    } catch (error) {
      lastError = error;
    }
    await sleep(intervalMs);
  }

  const reason = lastError
    ? lastError.message
    : `Saw ${lastTargets.length} targets but none were inspectable. Last targets: ${JSON.stringify(summarizeTargets(lastTargets))}`;
  throw new Error(`No inspectable target found. ${reason}`);
}

function attachSelectionMeta(target, attempts, preferMatched) {
  return {
    ...target,
    __omniSelectionAttempts: attempts,
    __omniPreferMatched: preferMatched,
  };
}

function targetMatchesPreference(target, normalizedPrefer) {
  if (!normalizedPrefer) {
    return true;
  }
  const title = String(target?.title || "").toLowerCase();
  const url = String(target?.url || "").toLowerCase();
  return title.includes(normalizedPrefer) || url.includes(normalizedPrefer);
}

function summarizeTargets(targets) {
  return (Array.isArray(targets) ? targets : []).slice(0, 8).map((target) => ({
    type: target?.type ?? "",
    title: target?.title ?? "",
    url: target?.url ?? "",
    hasDebugger: Boolean(target?.webSocketDebuggerUrl),
  }));
}

module.exports = {
  pickInspectableTarget,
  summarizeTargets,
  waitForInspectableTarget,
};
