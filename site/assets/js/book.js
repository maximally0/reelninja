/* ==========================================================================
   REELNINJA — book.js
   Loads the third-party scheduler on THIS page only, polls the slot for the
   real iframe, and keeps a plain outbound link as the fallback. A spinner that
   never resolves is worse than a link that always works.
   ========================================================================== */

(function () {
  // -------------------------------------------------------------------------
  // SWAP THIS ONE LINE for the live booking handle before deploying.
  // Format is "<username>/<event-slug>" exactly as it appears in the cal.com
  // URL. The same value is repeated in the fallback href in book/index.html.
  // -------------------------------------------------------------------------
  var CAL_LINK = 'reelninja/20min';

  var CAL_ORIGIN = 'https://cal.com';
  var EMBED_SRC = 'https://app.cal.com/embed/embed.js';
  var LOAD_DEADLINE_MS = 12000;

  // The namespace cal.com keys its queue on. Same as the event slug.
  var NS = CAL_LINK.split('/')[1] || 'call';

  var slot = document.getElementById('cal-slot');
  if (!slot) return;

  var loading = document.getElementById('cal-loading');
  var fallback = document.getElementById('cal-fallback');
  var fallbackHref = CAL_ORIGIN + '/' + CAL_LINK;
  if (fallback) fallback.setAttribute('href', fallbackHref);

  function clearPlaceholder() {
    if (loading && loading.parentNode) {
      loading.parentNode.removeChild(loading);
      loading = null;
    }
  }

  function showFallbackNote() {
    if (slot.querySelector('iframe') || slot.querySelector('.book__offline')) return;
    clearPlaceholder();
    var note = document.createElement('p');
    note.className = 'book__fallback book__offline';
    var a = document.createElement('span');
    a.textContent = 'The calendar did not load. ';
    var link = document.createElement('a');
    link.className = 'link-u';
    link.href = fallbackHref;
    link.target = '_blank';
    link.rel = 'noopener';
    link.textContent = 'Open it in a new tab';
    var tail = document.createElement('span');
    tail.textContent = ' instead.';
    note.appendChild(a);
    note.appendChild(link);
    note.appendChild(tail);
    slot.insertBefore(note, slot.firstChild);
  }

  // Poll for the real child. The widget appends into the slot rather than
  // replacing it, so without this the "Loading" line stays visible directly
  // above a perfectly live calendar.
  function waitForCalendar(started) {
    if (slot.querySelector('iframe')) {
      clearPlaceholder();
      slot.classList.add('is-ready');
      // The escape hatch belongs under the calendar, not stacked on top of it.
      var wrap = document.getElementById('cal-fallback-wrap');
      if (wrap && wrap.parentNode === slot) slot.appendChild(wrap);
      return;
    }
    if (Date.now() - started > LOAD_DEADLINE_MS) {
      showFallbackNote();
      return;
    }
    window.setTimeout(function () { waitForCalendar(started); }, 250);
  }

  // -------------------------------------------------------------------------
  // cal.com's own loader stub. This is load-bearing: it is what defines
  // window.Cal as a queue and lazily appends embed.js. Appending embed.js
  // directly does nothing at all, because embed.js expects the queue to
  // already exist.
  // -------------------------------------------------------------------------
  (function (C, A, L) {
    var p = function (a, ar) { a.q.push(ar); };
    var d = C.document;
    C.Cal = C.Cal || function () {
      var cal = C.Cal;
      var ar = arguments;
      if (!cal.loaded) {
        cal.ns = {};
        cal.q = cal.q || [];
        d.head.appendChild(d.createElement('script')).src = A;
        cal.loaded = true;
      }
      if (ar[0] === L) {
        var api = function () { p(api, arguments); };
        var namespace = ar[1];
        api.q = api.q || [];
        if (typeof namespace === 'string') {
          cal.ns[namespace] = cal.ns[namespace] || api;
          p(cal.ns[namespace], ar);
          p(cal, ['initNamespace', namespace]);
        } else {
          p(cal, ar);
        }
        return;
      }
      p(cal, ar);
    };
  })(window, EMBED_SRC, 'init');

  if (typeof window.Cal !== 'function') {
    showFallbackNote();
    return;
  }

  try {
    window.Cal('init', NS, { origin: CAL_ORIGIN });
    window.Cal.ns[NS]('inline', {
      elementOrSelector: '#cal-slot',
      config: { layout: 'month_view', theme: 'dark' },
      calLink: CAL_LINK
    });
    window.Cal.ns[NS]('ui', { theme: 'dark', layout: 'month_view', hideEventTypeDetails: false });
  } catch (e) {
    showFallbackNote();
    return;
  }

  waitForCalendar(Date.now());
})();
