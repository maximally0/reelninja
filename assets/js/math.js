/* ==========================================================================
   REELNINJA — math.js
   The capacity calculator. Every figure it shows is arithmetic on the
   visitor's own inputs and on our PUBLISHED ladder. It never asserts a saving
   we have not priced, and it disqualifies low-volume visitors out loud.

   Our side of the arithmetic uses exactly two published facts:
     1. the published per-video ladder
     2. the published setup floor
   It deliberately does NOT invent a human-minutes-per-video figure for the
   system. Our numbers are rough estimates and nothing is logged, so there is
   no honest figure to print in that cell and a made-up one would cost the
   page its credibility.
   ========================================================================== */

(function () {
  'use strict';

  /* ---- published constants. Change here, changes everywhere. ----
     Source: pricing ladder, offer draft 2026-09-24. NOTE: the two source docs
     disagree on both the setup fee and the per-video tiers; these are the
     volume-tier figures from the business-model doc. */
  var LADDER = [
    { min: 1,   max: 20,       price: 500, label: '1 - 20' },
    { min: 21,  max: 50,       price: 400, label: '21 - 50' },
    { min: 51,  max: 100,      price: 300, label: '51 - 100' },
    { min: 101, max: 250,      price: 200, label: '101 - 250' },
    { min: 251, max: Infinity, price: 150, label: '251 +' }
  ];
  var HOURS_PER_MONTH = 160;   // one full-time editor
  var SETUP_LOW = 50000;       // published setup floor, INR
  var WORKABLE_AT = 100;       // below this the setup cannot pay for itself

  function $(id) { return document.getElementById(id); }

  var el = {
    creators: $('in-creators'), creatorsVal: $('val-creators'),
    videos: $('in-videos'), videosVal: $('val-videos'),
    minutes: $('in-minutes'), minutesVal: $('val-minutes'),
    rate: $('in-rate'),
    out: $('out'),
    big: $('out-big'), bigSub: $('out-big-sub'),
    hours: $('out-hours'), people: $('out-people'),
    costThem: $('out-cost-them'), costUs: $('out-cost-us'),
    cpsThem: $('out-cps-them'), cpsUs: $('out-cps-us'),
    tier: $('out-tier'),
    delta: $('out-delta'), brk: $('out-break'), slot: $('out-slot')
  };
  if (!el.creators || !el.out) return;   // not on this page

  /* ---- formatters: Indian digit grouping, because the ladder is in INR ---- */
  function money(n) { return '\u20b9' + Math.round(n).toLocaleString('en-IN'); }
  function num(n, dp) {
    var v = dp ? n.toFixed(dp) : Math.round(n);
    return Number(v).toLocaleString('en-IN');
  }
  function tierFor(v) {
    for (var i = 0; i < LADDER.length; i++) if (v <= LADDER[i].max) return LADDER[i];
    return LADDER[LADDER.length - 1];
  }

  function read() {
    var rate = parseFloat(el.rate.value);
    if (!isFinite(rate) || rate < 0) rate = 0;
    return {
      creators: +el.creators.value,
      perCreator: +el.videos.value,
      minutes: +el.minutes.value,
      rate: rate
    };
  }

  function compute(i) {
    var videos = i.creators * i.perCreator;
    var hours = (videos * i.minutes) / 60;
    var people = hours / HOURS_PER_MONTH;
    var costThem = hours * i.rate;
    var cpsThem = videos > 0 ? costThem / videos : 0;

    var tier = tierFor(videos);
    var costUs = videos * tier.price;
    var cpsUs = videos > 0 ? costUs / videos : 0;

    /* Break-even: the lowest volume band whose published rate is at or below
       what their editors cost per video. Pure arithmetic. */
    var brk = null;
    for (var k = 0; k < LADDER.length; k++) {
      if (LADDER[k].price <= cpsThem) { brk = LADDER[k].min; break; }
    }

    return {
      videos: videos, hours: hours, people: people,
      costThem: costThem, cpsThem: cpsThem,
      tier: tier, costUs: costUs, cpsUs: cpsUs,
      save: costThem - costUs, brk: brk
    };
  }

  function render() {
    var i = read();
    var r = compute(i);

    el.creatorsVal.textContent = num(i.creators) + (i.creators === 1 ? ' creator' : ' creators');
    el.videosVal.textContent = num(i.perCreator) + ' videos';
    el.minutesVal.textContent = num(i.minutes) + ' min';
    if (document.activeElement !== el.rate) el.rate.value = i.rate;

    el.big.textContent = num(r.videos) + (r.videos === 1 ? ' video' : ' videos') + ' a month';
    el.bigSub.textContent = 'That is ' + num(r.people, 2) + ' full-time editors at ' +
      HOURS_PER_MONTH + ' hours a month, doing nothing else.';

    el.hours.textContent = num(r.hours) + ' hrs';
    el.people.textContent = num(r.people, 2) + ' editors';
    el.costThem.textContent = money(r.costThem);
    el.costUs.textContent = money(r.costUs);
    el.cpsThem.textContent = money(r.cpsThem);
    el.cpsUs.textContent = money(r.cpsUs);
    el.tier.textContent = r.tier.label;

    el.delta.textContent = num(r.videos) + ' videos a month costs you ' + money(r.costThem) +
      ' in editing today. On the system, at your published tier, ' + money(r.costUs) + '.';

    if (r.brk === null) {
      el.brk.innerHTML = 'At ' + money(r.cpsThem) + ' a video your editors are cheaper than our ' +
        'lowest published rate. <strong>We are the wrong call for you, and we would say so on the call.</strong>';
    } else if (r.brk === 1) {
      el.brk.innerHTML = 'At what your editors cost you, we are cheaper at <strong>every volume on our ' +
        'ladder</strong>, starting from a single video a month.';
    } else if (r.videos < r.brk) {
      el.brk.innerHTML = 'We only become cheaper than your editors at <strong>' + num(r.brk) +
        ' videos a month</strong>. You are below that, so the setup does not pay for itself yet.';
    } else {
      el.brk.innerHTML = 'Yes. We are cheaper than your editors from <strong>' + num(r.brk) +
        ' videos a month</strong>, and you are past it.';
    }

    if (r.videos < WORKABLE_AT) {
      el.slot.textContent = num(r.videos) + ' videos a month. Under ' + WORKABLE_AT +
        '. The honest answer is that the setup does not pay for itself at this volume, and we would rather say that now than on a call.';
    } else if (r.save > 0) {
      var months = SETUP_LOW / r.save;
      el.slot.textContent = 'One-time setup from ' + money(SETUP_LOW) +
        ', quoted before you commit. At this volume it pays for itself in under ' +
        (months < 1 ? 'a month' : months.toFixed(1) + ' months') + '.';
    } else {
      el.slot.textContent = 'One-time setup from ' + money(SETUP_LOW) +
        ', quoted before you commit. At this volume we are not cheaper than your current setup.';
    }
  }

  [el.creators, el.videos, el.minutes, el.rate].forEach(function (input) {
    if (!input) return;
    input.addEventListener('input', render);
    input.addEventListener('change', render);
  });
  el.rate.addEventListener('blur', function () {
    var v = parseFloat(el.rate.value);
    if (!isFinite(v) || v < 0) el.rate.value = 0;
    render();
  });

  render();
})();
