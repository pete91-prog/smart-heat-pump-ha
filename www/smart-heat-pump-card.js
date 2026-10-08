/**
 * smart-heat-pump-card.js
 * Custom Lovelace card for Smart Varmepumpe Styring
 *
 * Visualizes how the integration maintains room temperature using an
 * external Zigbee sensor with hysteresis / dead-band control.
 *
 * Features:
 *  - Live arc gauge showing current deviation from target
 *  - Time-series canvas chart with dead-band zone highlighted
 *  - History pre-loaded from HA WebSocket API
 *  - Animated heating/cooling indicators
 *  - Responsive, dark-mode-aware styling via CSS variables
 *
 * Usage (Lovelace YAML):
 *   type: custom:smart-heat-pump-card
 *   entity: climate.smart_varmepumpe
 *   hours_to_show: 2          # optional, default 2
 *   name: Stue                # optional display name override
 */

(function () {
  'use strict';

  const VERSION = '1.1.0';

  /* ─── Colour palette ───────────────────────────────────────────────── */
  const C = {
    blue:      '#42a5f5',
    blueDark:  '#1565c0',
    blueAlpha: 'rgba(66,165,245,',
    green:     '#66bb6a',
    greenDark: '#2e7d32',
    greenAlpha:'rgba(102,187,106,',
    orange:    '#ff7043',
    orangeDk:  '#bf360c',
    orangeAlp: 'rgba(255,112,67,',
    red:       '#ef5350',
    grey:      'rgba(0,0,0,0.35)',
    greyLight: 'rgba(0,0,0,0.07)',
    white:     '#ffffff',
  };

  /* ─── Tiny helpers ─────────────────────────────────────────────────── */
  const clamp = (v, lo, hi) => Math.min(Math.max(v, lo), hi);
  const lerp  = (a, b, t)   => a + (b - a) * clamp(t, 0, 1);

  function fmtTemp(v)    { return v != null ? v.toFixed(1) + '°C' : '–'; }
  function fmtMins(min)  {
    if (min == null) return '–';
    min = Math.round(min);
    return min < 60 ? `${min} min` : `${(min / 60).toFixed(1)} t`;
  }
  function fmtTime(ms) {
    const d = new Date(ms);
    return d.toLocaleTimeString('nb', { hour: '2-digit', minute: '2-digit' });
  }

  /* ─── Card class ───────────────────────────────────────────────────── */
  class SmartHeatPumpCard extends HTMLElement {
    constructor() {
      super();
      this.attachShadow({ mode: 'open' });
      this._history        = [];   // [{time, roomTemp, targetTemp}]
      this._historyFetched = false;
      this._fetchPending   = false;
      this._hass           = null;
      this._config         = null;
      this._animating      = false;
      this._heatingGlow    = 0;    // 0–1, animated
      this._lastRaf        = null;
    }

    /* ── Config ──────────────────────────────────────────────────────── */
    static getStubConfig() {
      return { entity: 'climate.smart_varmepumpe', hours_to_show: 2 };
    }

    setConfig(config) {
      if (!config.entity) throw new Error('[smart-heat-pump-card] entity is required');
      this._config = {
        entity:       config.entity,
        hours_to_show: config.hours_to_show || 2,
        name:         config.name || null,
      };
      this._buildDOM();
    }

    /* ── DOM structure ───────────────────────────────────────────────── */
    _buildDOM() {
      this.shadowRoot.innerHTML = `
        <style>
          *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

          :host { display: block; }

          ha-card {
            overflow: hidden;
            font-family: var(--primary-font-family, 'Roboto', sans-serif);
            transition: background 0.8s ease;
          }

          /* ── Header ── */
          .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 14px 16px 4px;
          }
          .card-name {
            font-size: 13px;
            font-weight: 500;
            color: var(--secondary-text-color);
            text-transform: uppercase;
            letter-spacing: .08em;
          }
          .badge {
            font-size: 10px;
            font-weight: 700;
            padding: 3px 10px;
            border-radius: 20px;
            text-transform: uppercase;
            letter-spacing: .06em;
          }
          .badge-Komfort { background: #e3f2fd; color: #1565c0; }
          .badge-Økonomi { background: #e8f5e9; color: #2e7d32; }
          .badge-Borte   { background: #f3e5f5; color: #6a1b9a; }
          .badge-Boost   { background: #fff3e0; color: #e65100; }
          .badge-Manuell { background: #f5f5f5; color: #616161; }
          @media (prefers-color-scheme: dark) {
            .badge-Komfort { background: rgba(21,101,192,.25); color: #90caf9; }
            .badge-Økonomi { background: rgba(46,125,50,.25);  color: #a5d6a7; }
            .badge-Borte   { background: rgba(106,27,154,.25); color: #ce93d8; }
            .badge-Boost   { background: rgba(230,81,0,.25);   color: #ffcc80; }
            .badge-Manuell { background: rgba(97,97,97,.25);   color: #bdbdbd; }
          }

          /* ── Gauge row ── */
          .gauge-row {
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 4px 16px 0;
            gap: 12px;
          }
          .gauge-wrap { position: relative; flex-shrink: 0; }
          #gauge-canvas { display: block; }

          .temp-block {
            display: flex;
            flex-direction: column;
            gap: 6px;
            flex: 1;
          }
          .current-temp {
            font-size: 52px;
            font-weight: 300;
            line-height: 1;
            color: var(--primary-text-color);
            display: flex;
            align-items: flex-start;
            gap: 2px;
          }
          .current-temp .deg { font-size: 22px; margin-top: 8px; }
          .pulse-dot {
            width: 10px; height: 10px;
            border-radius: 50%;
            background: ${C.orange};
            margin-top: 14px;
            margin-left: 4px;
            opacity: 0;
            transition: opacity .4s;
          }
          .pulse-dot.on {
            opacity: 1;
            animation: pulse 1.6s ease-in-out infinite;
          }
          @keyframes pulse {
            0%,100% { transform:scale(1);   box-shadow: 0 0 0 0   ${C.orangeAlp}.5); }
            50%      { transform:scale(1.3); box-shadow: 0 0 0 8px ${C.orangeAlp}0); }
          }

          .meta-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 2px 12px;
            font-size: 12px;
            color: var(--secondary-text-color);
          }
          .meta-grid strong { color: var(--primary-text-color); font-weight: 500; }

          /* ── Status banner ── */
          .status-bar {
            margin: 10px 16px 4px;
            padding: 7px 12px;
            border-radius: 8px;
            font-size: 12px;
            font-weight: 500;
            display: flex;
            align-items: center;
            gap: 6px;
            transition: background .4s, color .4s;
          }
          .s-ok      { background:${C.greenAlpha}.1); color:#2e7d32; }
          .s-heat    { background:${C.orangeAlp}.12); color:#bf360c; }
          .s-cool    { background:${C.blueAlpha}.12); color:#1565c0; }
          .s-off     { background:${C.greyLight}; color:var(--secondary-text-color); }
          @media (prefers-color-scheme: dark) {
            .s-ok   { background:${C.greenAlpha}.15); color:#a5d6a7; }
            .s-heat { background:${C.orangeAlp}.18); color:#ffcc80; }
            .s-cool { background:${C.blueAlpha}.18); color:#90caf9; }
          }

          /* ── Chart ── */
          .chart-wrap { padding: 4px 10px 4px; }
          #chart-canvas { display: block; width: 100%; border-radius: 8px; }

          /* ── Stats row ── */
          .stats-row {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            padding: 6px 16px 14px;
            text-align: center;
          }
          .stat-label {
            font-size: 10px;
            text-transform: uppercase;
            letter-spacing: .06em;
            color: var(--secondary-text-color);
          }
          .stat-value {
            font-size: 17px;
            font-weight: 500;
            color: var(--primary-text-color);
            margin-top: 1px;
            transition: color .3s;
          }
          .v-hot  { color: ${C.orange}; }
          .v-cold { color: ${C.blue};   }
          .v-ok   { color: ${C.green};  }
        </style>

        <ha-card id="ha-card">
          <div class="header">
            <span class="card-name" id="card-name">Smart Varmepumpe</span>
            <span class="badge badge-Komfort" id="badge">Komfort</span>
          </div>

          <div class="gauge-row">
            <div class="gauge-wrap">
              <canvas id="gauge-canvas" width="140" height="90"></canvas>
            </div>
            <div class="temp-block">
              <div class="current-temp">
                <span id="cur-val">–</span><span class="deg">°C</span>
                <span class="pulse-dot" id="pulse"></span>
              </div>
              <div class="meta-grid">
                <span>Mål</span>       <strong id="m-target">–</strong>
                <span>Hysterese</span> <strong id="m-hyst">–</strong>
                <span>Setpunkt VP</span><strong id="m-setpt">–</strong>
                <span>Cooldown</span>  <strong id="m-cool">–</strong>
              </div>
            </div>
          </div>

          <div class="status-bar s-ok" id="status-bar">
            <span id="s-icon">✅</span>
            <span id="s-text">Laster…</span>
          </div>

          <div class="chart-wrap">
            <canvas id="chart-canvas" height="130"></canvas>
          </div>

          <div class="stats-row">
            <div>
              <div class="stat-label">Avvik</div>
              <div class="stat-value" id="st-dev">–</div>
            </div>
            <div>
              <div class="stat-label">Siste endring</div>
              <div class="stat-value" id="st-last">–</div>
            </div>
            <div>
              <div class="stat-label">Status</div>
              <div class="stat-value" id="st-status">–</div>
            </div>
          </div>
        </ha-card>
      `;
    }

    /* ── HA state update ─────────────────────────────────────────────── */
    set hass(hass) {
      this._hass = hass;
      if (!this._config) return;

      const state = hass.states[this._config.entity];
      if (!state) return;

      if (!this._historyFetched && !this._fetchPending) {
        this._fetchHistory(state);
      }

      this._appendToBuffer(state);
      this._render(state);
    }

    /* ── History pre-load ────────────────────────────────────────────── */
    async _fetchHistory(state) {
      this._fetchPending = true;
      const hours  = this._config.hours_to_show;
      const start  = new Date(Date.now() - hours * 3_600_000).toISOString();
      const sensorId = state.attributes.sensor_entity;
      const ids    = [this._config.entity, sensorId].filter(Boolean);

      try {
        const result = await this._hass.callWs({
          type: 'history/history_during_period',
          start_time: start,
          entity_ids: ids,
          minimal_response: false,
          significant_changes_only: false,
        });

        const sensorData  = (sensorId && result[sensorId])  || [];
        const climateData = result[this._config.entity] || [];

        /* Build timeline from sensor readings */
        const points = [];
        for (const s of sensorData) {
          const temp = parseFloat(s.state);
          if (isNaN(temp)) continue;
          const t = new Date(s.last_changed).getTime();
          /* Find most recent climate state at this time */
          const cl = climateData.filter(c =>
            new Date(c.last_changed).getTime() <= t
          ).pop();
          points.push({
            time:      t,
            roomTemp:  temp,
            targetTemp: cl ? parseFloat(cl.attributes?.temperature ?? 20) : null,
          });
        }

        /* Fall back: use current_temperature from climate history */
        if (points.length === 0) {
          for (const c of climateData) {
            const t    = parseFloat(c.attributes?.current_temperature);
            const tgt  = parseFloat(c.attributes?.temperature ?? 20);
            if (isNaN(t)) continue;
            points.push({
              time:      new Date(c.last_changed).getTime(),
              roomTemp:  t,
              targetTemp: tgt,
            });
          }
        }

        this._history = points.sort((a, b) => a.time - b.time);
        this._historyFetched = true;
        const cur = this._hass.states[this._config.entity];
        if (cur) this._render(cur);
      } catch (e) {
        console.warn('[smart-heat-pump-card] history fetch failed:', e);
        this._historyFetched = true;
      } finally {
        this._fetchPending = false;
      }
    }

    _appendToBuffer(state) {
      const now  = Date.now();
      const last = this._history.at(-1);
      if (last && now - last.time < 20_000) return; // max 1 point / 20 s

      const rt = state.attributes.current_temperature;
      const tt = state.attributes.temperature;
      if (rt == null) return;

      this._history.push({ time: now, roomTemp: rt, targetTemp: tt });

      const cutoff = now - this._config.hours_to_show * 3_600_000;
      while (this._history.length > 1 && this._history[0].time < cutoff) {
        this._history.shift();
      }
    }

    /* ── Main render ─────────────────────────────────────────────────── */
    _render(state) {
      const a           = state.attributes;
      const roomTemp    = a.current_temperature;
      const targetTemp  = a.temperature;
      const hysteresis  = a.hysteresis  ?? 0.5;
      const preset      = a.preset_mode ?? 'Komfort';
      const hvacAction  = a.hvac_action;
      const minsSince   = a.minutes_since_last_change;
      const minTime     = a.min_time_between_changes_min ?? 30;
      const isOff       = state.state === 'off';
      const isHeating   = hvacAction === 'heating';
      const deviation   = (roomTemp != null && targetTemp != null)
                          ? targetTemp - roomTemp : null;
      const inBand      = deviation != null && Math.abs(deviation) <= hysteresis;

      /* Name */
      this._q('#card-name').textContent =
        this._config.name ?? a.friendly_name ?? 'Smart Varmepumpe';

      /* Badge */
      const badge = this._q('#badge');
      badge.textContent  = preset;
      badge.className    = `badge badge-${preset}`;

      /* Big temp */
      this._q('#cur-val').textContent = roomTemp != null ? roomTemp.toFixed(1) : '–';
      this._q('#pulse').classList.toggle('on', isHeating && !isOff);

      /* Meta */
      this._q('#m-target').textContent = fmtTemp(targetTemp);
      this._q('#m-hyst').textContent   = hysteresis.toFixed(1) + '°C';
      this._q('#m-setpt').textContent  = fmtTemp(targetTemp != null
        ? (isHeating ? targetTemp + (a.overshoot ?? 2) : targetTemp - 1)
        : null);
      const remaining = minsSince != null ? Math.max(0, minTime - minsSince) : null;
      const coolEl    = this._q('#m-cool');
      if (remaining != null && remaining <= 0) {
        coolEl.textContent = 'Klar ✓';
        coolEl.style.color = C.green;
      } else {
        coolEl.textContent = remaining != null ? fmtMins(remaining) : '–';
        coolEl.style.color = '';
      }

      /* Status bar */
      const bar = this._q('#status-bar');
      if (isOff) {
        bar.className = 'status-bar s-off';
        this._q('#s-icon').textContent = '⏸';
        this._q('#s-text').textContent = 'Avslått – manuell kontroll';
      } else if (inBand) {
        bar.className = 'status-bar s-ok';
        this._q('#s-icon').textContent = '✅';
        this._q('#s-text').textContent =
          `Innenfor dead band ±${hysteresis}°C — ingen endring nødvendig`;
      } else if (deviation != null && deviation > hysteresis) {
        bar.className = 'status-bar s-heat';
        this._q('#s-icon').textContent = '🔥';
        this._q('#s-text').textContent =
          `Varmer opp — ${deviation.toFixed(1)}°C under mål`;
      } else if (deviation != null && deviation < -hysteresis) {
        bar.className = 'status-bar s-cool';
        this._q('#s-icon').textContent = '❄️';
        this._q('#s-text').textContent =
          `Over mål — ${Math.abs(deviation).toFixed(1)}°C for varmt, holder igjen`;
      }

      /* Card background tint when heating */
      const card = this._q('#ha-card');
      if (isHeating && !isOff) {
        card.style.background = 'linear-gradient(180deg, rgba(255,112,67,.04) 0%, transparent 120px)';
      } else {
        card.style.background = '';
      }

      /* Stats */
      const devEl = this._q('#st-dev');
      if (deviation != null) {
        const sign = deviation > 0 ? '+' : '';
        devEl.textContent = `${sign}${deviation.toFixed(1)}°C`;
        devEl.className   = 'stat-value ' +
          (inBand ? 'v-ok' : deviation > 0 ? 'v-hot' : 'v-cold');
      } else {
        devEl.textContent = '–';
        devEl.className   = 'stat-value';
      }

      this._q('#st-last').textContent = fmtMins(minsSince);

      const stSt = this._q('#st-status');
      if (isOff)          { stSt.textContent = 'Av';       stSt.className = 'stat-value'; }
      else if (isHeating) { stSt.textContent = 'Varmer 🔥'; stSt.className = 'stat-value v-hot'; }
      else if (inBand)    { stSt.textContent = 'OK ✓';     stSt.className = 'stat-value v-ok'; }
      else                { stSt.textContent = 'Venter';   stSt.className = 'stat-value'; }

      /* Canvases */
      this._drawGauge(deviation, hysteresis, isOff);
      this._drawChart(targetTemp, hysteresis);
    }

    /* ── Deviation arc gauge ─────────────────────────────────────────── */
    _drawGauge(deviation, hysteresis, isOff) {
      const canvas = this._q('#gauge-canvas');
      const ctx    = canvas.getContext('2d');
      const dpr    = window.devicePixelRatio || 1;
      const W = 140, H = 90;
      canvas.width  = W * dpr;
      canvas.height = H * dpr;
      ctx.scale(dpr, dpr);
      ctx.clearRect(0, 0, W, H);

      const cx   = W / 2;
      const cy   = H - 10;
      const r    = 68;
      const startAngle = Math.PI;          // left (−)
      const endAngle   = 0;               // right (+)
      const totalArc   = Math.PI;         // 180°
      const maxDev     = hysteresis * 4;  // gauge full-scale

      /* Background track */
      ctx.beginPath();
      ctx.arc(cx, cy, r, Math.PI, 0);
      ctx.strokeStyle = 'rgba(0,0,0,0.08)';
      ctx.lineWidth   = 14;
      ctx.lineCap     = 'round';
      ctx.stroke();

      if (!isOff && deviation != null) {
        /* Dead-band arc (green zone in the centre) */
        const bandFrac  = hysteresis / maxDev;
        const bandStart = Math.PI - totalArc * (0.5 - bandFrac);
        const bandEnd   = Math.PI - totalArc * (0.5 + bandFrac);
        const deadGrad  = ctx.createConicGradient
          ? null : null; // fallback
        ctx.beginPath();
        ctx.arc(cx, cy, r, bandEnd, bandStart);
        ctx.strokeStyle = C.greenAlpha + '.55)';
        ctx.lineWidth   = 14;
        ctx.lineCap     = 'butt';
        ctx.stroke();

        /* Filled arc showing actual deviation */
        const normDev  = clamp(deviation / maxDev, -1, 1);  // −1…+1
        // deviation > 0 means too cold (need heat), arc goes left of centre
        // deviation < 0 means too warm, arc goes right of centre
        const centreA  = Math.PI - totalArc * 0.5; // pointing straight up
        const needleA  = centreA - normDev * totalArc * 0.5;

        const isWarm   = deviation < -hysteresis;
        const isCold   = deviation > hysteresis;
        const arcColor = isCold ? C.orange : isWarm ? C.blue : C.green;

        ctx.beginPath();
        if (normDev >= 0) {
          ctx.arc(cx, cy, r, needleA, centreA);
        } else {
          ctx.arc(cx, cy, r, centreA, needleA);
        }
        ctx.strokeStyle = arcColor;
        ctx.lineWidth   = 14;
        ctx.lineCap     = 'round';
        ctx.stroke();

        /* Needle dot */
        const nx = cx + r * Math.cos(needleA);
        const ny = cy + r * Math.sin(needleA);
        ctx.beginPath();
        ctx.arc(nx, ny, 7, 0, Math.PI * 2);
        ctx.fillStyle   = arcColor;
        ctx.fill();
        ctx.strokeStyle = '#fff';
        ctx.lineWidth   = 2.5;
        ctx.stroke();
      }

      /* Labels */
      ctx.font      = 'bold 10px sans-serif';
      ctx.fillStyle = C.grey;
      ctx.textAlign = 'center';

      // Left: cold
      ctx.fillText('❄️', cx - r + 2, cy - 2);
      // Right: hot
      ctx.fillText('🔥', cx + r - 2, cy - 2);

      // Centre label: deviation value
      ctx.font      = 'bold 13px sans-serif';
      ctx.fillStyle = 'var(--primary-text-color, #212121)';
      ctx.fillText(
        deviation != null ? (deviation > 0 ? '+' : '') + deviation.toFixed(1) + '°' : '–',
        cx, cy - 16
      );
      ctx.font      = '10px sans-serif';
      ctx.fillStyle = C.grey;
      ctx.fillText('avvik', cx, cy - 3);
    }

    /* ── Time-series chart ───────────────────────────────────────────── */
    _drawChart(targetTemp, hysteresis) {
      const canvas = this._q('#chart-canvas');
      const ctx    = canvas.getContext('2d');
      const dpr    = window.devicePixelRatio || 1;
      const rect   = canvas.getBoundingClientRect();
      const W      = rect.width  || 320;
      const H      = parseInt(canvas.getAttribute('height')) || 130;

      canvas.width  = W * dpr;
      canvas.height = H * dpr;
      ctx.scale(dpr, dpr);
      ctx.clearRect(0, 0, W, H);

      const pts = this._history;

      /* Placeholder when no data yet */
      if (pts.length < 2 || targetTemp == null) {
        ctx.fillStyle = C.greyLight;
        _roundRect(ctx, 0, 0, W, H, 8);
        ctx.fill();
        ctx.fillStyle = 'rgba(0,0,0,.28)';
        ctx.font      = '12px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('Samler temperaturdata…', W / 2, H / 2 + 4);
        return;
      }

      const PAD = { t: 8, r: 10, b: 22, l: 34 };
      const cW  = W - PAD.l - PAD.r;
      const cH  = H - PAD.t - PAD.b;

      /* Y range – enough room for dead band + some margin */
      const allTemps = pts.flatMap(p => [p.roomTemp]);
      const minT = Math.min(...allTemps, targetTemp - hysteresis) - 0.6;
      const maxT = Math.max(...allTemps, targetTemp + hysteresis) + 0.6;
      const rngT = maxT - minT;

      /* Time range */
      const minMs = pts[0].time;
      const maxMs = Date.now();
      const rngMs = Math.max(maxMs - minMs, 1);

      const tx = ms  => PAD.l + ((ms  - minMs) / rngMs) * cW;
      const ty = tmp => PAD.t + cH - ((tmp - minT) / rngT) * cH;

      /* ── Background ── */
      ctx.fillStyle = C.greyLight;
      _roundRect(ctx, 0, 0, W, H, 8);
      ctx.fill();

      /* ── Grid lines ── */
      ctx.strokeStyle = 'rgba(0,0,0,.05)';
      ctx.lineWidth   = 1;
      const steps = 4;
      for (let i = 0; i <= steps; i++) {
        const t = minT + rngT * i / steps;
        const y = ty(t);
        ctx.beginPath();
        ctx.moveTo(PAD.l, y);
        ctx.lineTo(PAD.l + cW, y);
        ctx.stroke();

        ctx.fillStyle = 'rgba(0,0,0,.35)';
        ctx.font      = '9px sans-serif';
        ctx.textAlign = 'right';
        ctx.fillText(t.toFixed(0) + '°', PAD.l - 3, y + 3);
      }

      /* ── Dead-band fill ── */
      const dBandTop = ty(targetTemp + hysteresis);
      const dBandBot = ty(targetTemp - hysteresis);
      const dbGrad   = ctx.createLinearGradient(0, dBandTop, 0, dBandBot);
      dbGrad.addColorStop(0,   C.greenAlpha + '.06)');
      dbGrad.addColorStop(0.5, C.greenAlpha + '.18)');
      dbGrad.addColorStop(1,   C.greenAlpha + '.06)');
      ctx.fillStyle = dbGrad;
      ctx.fillRect(PAD.l, dBandTop, cW, dBandBot - dBandTop);

      /* ── Dead-band dashed borders ── */
      ctx.strokeStyle = C.greenAlpha + '.55)';
      ctx.lineWidth   = 1;
      ctx.setLineDash([4, 4]);
      [targetTemp + hysteresis, targetTemp - hysteresis].forEach(t => {
        ctx.beginPath();
        ctx.moveTo(PAD.l, ty(t));
        ctx.lineTo(PAD.l + cW, ty(t));
        ctx.stroke();
      });
      ctx.setLineDash([]);

      /* ── Target line ── */
      ctx.strokeStyle = C.green;
      ctx.lineWidth   = 1.5;
      ctx.beginPath();
      ctx.moveTo(PAD.l, ty(targetTemp));
      ctx.lineTo(PAD.l + cW, ty(targetTemp));
      ctx.stroke();

      /* Target label */
      ctx.fillStyle = C.green;
      ctx.font      = 'bold 9px sans-serif';
      ctx.textAlign = 'left';
      ctx.fillText(fmtTemp(targetTemp), PAD.l + 3, ty(targetTemp) - 3);

      /* Band label */
      ctx.fillStyle = C.greenAlpha + '.7)';
      ctx.font      = '9px sans-serif';
      ctx.textAlign = 'right';
      ctx.fillText(`±${hysteresis}°`, PAD.l + cW - 2, ty(targetTemp) - 3);

      /* ── Room temperature area fill ── */
      const aGrad = ctx.createLinearGradient(0, ty(maxT), 0, ty(minT));
      aGrad.addColorStop(0,   C.blueAlpha + '.30)');
      aGrad.addColorStop(0.6, C.blueAlpha + '.08)');
      aGrad.addColorStop(1,   C.blueAlpha + '.01)');

      ctx.beginPath();
      ctx.moveTo(tx(pts[0].time), ty(pts[0].roomTemp));
      for (let i = 1; i < pts.length; i++) {
        /* Smooth with cubic bezier */
        const prev = pts[i - 1], curr = pts[i];
        const cpx1 = tx(prev.time) + (tx(curr.time) - tx(prev.time)) * 0.4;
        const cpx2 = tx(curr.time) - (tx(curr.time) - tx(prev.time)) * 0.4;
        ctx.bezierCurveTo(cpx1, ty(prev.roomTemp), cpx2, ty(curr.roomTemp), tx(curr.time), ty(curr.roomTemp));
      }
      const lastPt = pts.at(-1);
      ctx.lineTo(tx(lastPt.time), H - PAD.b);
      ctx.lineTo(tx(pts[0].time), H - PAD.b);
      ctx.closePath();
      ctx.fillStyle = aGrad;
      ctx.fill();

      /* ── Room temperature line ── */
      ctx.beginPath();
      ctx.moveTo(tx(pts[0].time), ty(pts[0].roomTemp));
      for (let i = 1; i < pts.length; i++) {
        const prev = pts[i - 1], curr = pts[i];
        const cpx1 = tx(prev.time) + (tx(curr.time) - tx(prev.time)) * 0.4;
        const cpx2 = tx(curr.time) - (tx(curr.time) - tx(prev.time)) * 0.4;
        ctx.bezierCurveTo(cpx1, ty(prev.roomTemp), cpx2, ty(curr.roomTemp), tx(curr.time), ty(curr.roomTemp));
      }
      ctx.strokeStyle = C.blue;
      ctx.lineWidth   = 2.5;
      ctx.lineJoin    = 'round';
      ctx.stroke();

      /* ── Live dot with glow ── */
      const lx = tx(lastPt.time);
      const ly = ty(lastPt.roomTemp);
      ctx.shadowColor = C.blue;
      ctx.shadowBlur  = 8;
      ctx.beginPath();
      ctx.arc(lx, ly, 4.5, 0, Math.PI * 2);
      ctx.fillStyle = C.blueDark;
      ctx.fill();
      ctx.shadowBlur = 0;
      ctx.strokeStyle = '#fff';
      ctx.lineWidth   = 2;
      ctx.stroke();

      /* ── Time axis labels ── */
      ctx.fillStyle = 'rgba(0,0,0,.38)';
      ctx.font      = '9px sans-serif';
      ctx.textAlign = 'left';
      ctx.fillText(fmtTime(minMs), PAD.l, H - 5);
      ctx.textAlign = 'center';
      ctx.fillText(fmtTime((minMs + maxMs) / 2), PAD.l + cW / 2, H - 5);
      ctx.textAlign = 'right';
      ctx.fillText('Nå', PAD.l + cW, H - 5);
    }

    /* ── Util ─────────────────────────────────────────────────────────── */
    _q(sel) { return this.shadowRoot.querySelector(sel); }
    getCardSize() { return 5; }
  }

  /* ── Standalone roundRect polyfill ─────────────────────────────────── */
  function _roundRect(ctx, x, y, w, h, r) {
    if (ctx.roundRect) {
      ctx.roundRect(x, y, w, h, r);
    } else {
      ctx.beginPath();
      ctx.moveTo(x + r, y);
      ctx.lineTo(x + w - r, y);
      ctx.quadraticCurveTo(x + w, y, x + w, y + r);
      ctx.lineTo(x + w, y + h - r);
      ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
      ctx.lineTo(x + r, y + h);
      ctx.quadraticCurveTo(x, y + h, x, y + h - r);
      ctx.lineTo(x, y + r);
      ctx.quadraticCurveTo(x, y, x + r, y);
      ctx.closePath();
    }
  }

  /* ── Register ───────────────────────────────────────────────────────── */
  if (!customElements.get('smart-heat-pump-card')) {
    customElements.define('smart-heat-pump-card', SmartHeatPumpCard);
    console.info(
      '%c SMART-HEAT-PUMP-CARD %c v' + VERSION + ' ',
      'color:#fff;background:#ff7043;font-weight:bold;padding:2px 4px;border-radius:3px 0 0 3px',
      'color:#ff7043;background:#fff3e0;font-weight:bold;padding:2px 4px;border-radius:0 3px 3px 0',
    );
  }

  window.customCards = window.customCards || [];
  if (!window.customCards.find(c => c.type === 'smart-heat-pump-card')) {
    window.customCards.push({
      type:        'smart-heat-pump-card',
      name:        'Smart Varmepumpe Styring',
      description: 'Visualiserer temperaturkontroll med hysterese og dead band',
      preview:     true,
    });
  }
})();
