/* Portfolio advertising. No requests until every operator release gate passes.
 * Google CMP manages consent; these gates never represent a visitor's choice.
 * API: https://developers.google.com/funding-choices/fc-api-docs
 */
(() => {
  'use strict';
  const ownScript = document.currentScript;
  const host = ownScript && ownScript.dataset.host;
  const approved = ownScript && ownScript.dataset.approved === 'true';
  const consentReady = ownScript && ownScript.dataset.consentReady === 'true';
  const slot = ownScript && ownScript.dataset.slot;
  function publicContext(messagingOnly = false) {
    if (location.hostname !== host || !/^\/(index\.html)?$/.test(location.pathname) || location.hash || location.search.length > 512) return false;
    const values = [...new URLSearchParams(location.search).entries()];
    if (values.length === 0) return true;
    if (!messagingOnly || values.length !== 2 || new Set(values.map(([key]) => key)).size !== 2) return false;
    const query = new URLSearchParams(location.search);
    return query.get('fc') === 'alwaysshow' && ['gdpr','ccpa','usnat','usfl'].includes(query.get('fctype'));
  }
  // Public static directory landing pages only. Searches and private URLs never
  // reach the advertising service. Preview/deployment hosts remain excluded.
  if (!publicContext(true) || !approved || !consentReady || !/^\d+$/.test(slot || '')) return;
  const publisher = 'ca-pub-6925791999163076';
  const messaging = window.googlefc = window.googlefc || {};
  messaging.callbackQueue = messaging.callbackQueue || [];
  messaging.callbackQueue.push({CONSENT_API_READY: () => {
    const choice = document.querySelector('[data-ad-privacy]');
    if (!choice || typeof messaging.showRevocationMessage !== 'function') return;
    choice.hidden = false;
    choice.addEventListener('click', () => messaging.showRevocationMessage());
  }});
  const script = document.createElement('script');
  script.async = true; script.crossOrigin = 'anonymous';
  script.setAttribute('data-privacy-treatments','disablePersonalization');
  script.src = 'https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=' + publisher;
  document.head.appendChild(script);
  // Official CMP test parameters may load messaging, never manual inventory.
  if (!publicContext()) return;
  const region = document.querySelector('[data-portfolio-ad]');
  if (!region) return;
  region.hidden = false;
  // Reserve the same geometry during fill, no-fill and blocked-script states.
  region.style.cssText = 'box-sizing:border-box;max-width:970px;min-height:300px;margin:32px auto;padding:16px 12px;border-block:1px solid currentColor;clear:both';
  const label = document.createElement('p'); label.textContent = 'Advertisement';
  label.style.cssText = 'font:12px/1.5 system-ui;text-align:center;margin:0 0 12px';
  const unit = document.createElement('ins'); unit.className = 'adsbygoogle';
  unit.style.cssText = 'display:block;min-height:250px';
  unit.setAttribute('data-ad-client',publisher); unit.setAttribute('data-ad-slot',slot);
  unit.setAttribute('data-ad-format','auto'); unit.setAttribute('data-full-width-responsive','true');
  unit.setAttribute('data-restrict-data-processing','1');
  region.append(label,unit);
  let queued = false, visible = !('IntersectionObserver' in window);
  let viewportObserver = null, sizeObserver = null;
  const request = () => {
    if (queued || !visible || !publicContext() || unit.getBoundingClientRect().width <= 0) return;
    try {
      (window.adsbygoogle = window.adsbygoogle || []).push({}); queued = true;
      viewportObserver?.disconnect(); sizeObserver?.disconnect();
    }
    catch { /* Ad blocking must not break the directory. */ }
  };
  // A visible slot can still be zero-width during layout. Retry when its size
  // becomes available, retaining visibility, URL and single-request checks.
  if ('ResizeObserver' in window) {
    sizeObserver = new ResizeObserver(request);
    sizeObserver.observe(unit);
  }
  // Request only when the below-content placement approaches the viewport.
  if ('IntersectionObserver' in window) {
    viewportObserver = new IntersectionObserver(entries => {
      visible = entries.some(entry => entry.isIntersecting);
      request();
    }, {rootMargin:'200px'});
    viewportObserver.observe(region);
  } else request();
})();
