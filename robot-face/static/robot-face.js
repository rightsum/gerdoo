/* <robot-face> — animated robot face web component.
   Attributes: color (hex), speed (0.5–1.5), emotion ("auto" or a name).

   Performance notes (tuned for Jetson / software-rendered Firefox canvas):
   - The glow is a GPU CSS drop-shadow filter, NOT per-frame canvas shadowBlur
     (shadowBlur over a full 1080p canvas is the single biggest cost and was the
     source of the lag). Shapes are drawn crisp, once, to a transparent canvas.
   - The dark background + ambient tint is a static layer, not re-filled per frame.
   - Frame rate is capped (RENDER_FPS) and the backing store can render below
     display resolution (RENDER_SCALE) — the glow hides the softening. */
(function () {
  // A calm face doesn't need 60fps of full-screen GPU work. 30fps at 0.75 scale
  // roughly quarters the per-second GPU load vs. 60fps/native — smoother (leaves
  // headroom so frames never drop) and lower power. The soft glow hides the
  // slightly reduced backing resolution. Bump these back up if you want.
  // Adaptive frame rate: render fast only while something moves (blinks, eye
  // saccades, expression changes), idle slowly otherwise. Smoother motion than a
  // flat 30fps AND lower average power.
  const ACTIVE_FPS = 60;      // during motion
  const IDLE_FPS = 10;        // while holding still (breathing only)
  const RENDER_SCALE = 0.75;  // backing-store resolution vs. display (1 = native)

  const BASE = {
    ew: 1, eh: 1, rT: 0.32, rB: 0.32,
    topLid: 0, topSlant: 0, botLid: 0,
    asym: 0, mC: 0.18, mW: 1, mO: 0, dots: 0, heart: 0
  };
  // gR = gaze wander radius, gInt = seconds between gaze retargets, lock = fixed gaze
  const EMOTIONS = {
    idle:      { ...BASE, gR: 45, gInt: 2.6 },
    happy:     { ...BASE, ew: 1.02, eh: 0.96, rT: 0.42, rB: 0.42, botLid: 0.42, mC: 1, mW: 1.15, gR: 30, gInt: 2 },
    curious:   { ...BASE, ew: 0.95, eh: 1.03, topLid: 0.06, asym: 0.3, mC: 0.3, mW: 0.55, mO: 0.0, gR: 150, gInt: 0.9 },
    sleepy:    { ...BASE, eh: 0.9, topLid: 0.55, topSlant: -0.2, mC: 0.05, mW: 0.6, gR: 12, gInt: 4.5 },
    surprised: { ...BASE, ew: 1.14, eh: 1.16, rT: 0.5, rB: 0.5, mC: 0, mW: 0.5, mO: 1, gR: 8, gInt: 3 },
    sad:       { ...BASE, ew: 0.95, eh: 0.85, topLid: 0.26, topSlant: -1, mC: -1, mW: 0.85, gR: 20, gInt: 3.5, lock: [0, 55] },
    angry:     { ...BASE, ew: 1.02, eh: 0.78, rT: 0.26, topLid: 0.32, topSlant: 1, mC: -0.45, mW: 0.9, gR: 18, gInt: 2.4 },
    love:      { ...BASE, heart: 1, mC: 1, mW: 1.1, gR: 15, gInt: 2.5 },
    thinking:  { ...BASE, topLid: 0.2, topSlant: 0.35, dots: 1, mW: 0, gR: 0, gInt: 9, lock: [95, -60] }
  };
  const LOOP = ['happy', 'curious', 'surprised', 'thinking', 'love', 'sleepy', 'sad', 'angry'];
  const NUMKEYS = Object.keys(BASE);
  const rand = (a, b) => a + Math.random() * (b - a);
  const clamp = (v, a, b) => Math.min(b, Math.max(a, v));

  // "#RRGGBB" -> "rgba(r,g,b,alpha)"
  function hexA(hex, alpha) {
    const h = (hex || '#FFAE1E').replace('#', '');
    const n = parseInt(h.length === 3 ? h.replace(/(.)/g, '$1$1') : h, 16);
    return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${alpha})`;
  }

  class RobotFace extends HTMLElement {
    connectedCallback() {
      this.style.display = 'block';
      this.style.position = this.style.position || 'relative';
      this.style.width = '100%';
      this.style.height = '100%';
      this.style.overflow = 'hidden';

      // Static dark background + ambient tint (re-tinted only when color changes).
      this.bg = document.createElement('div');
      this.bg.style.cssText = 'position:absolute;inset:0;background:#070503';
      this.appendChild(this.bg);

      // One canvas: crisp shapes only. Glow is a GPU CSS filter on this element.
      this.canvas = document.createElement('canvas');
      this.canvas.style.cssText =
        'position:absolute;inset:0;width:100%;height:100%;display:block;background:transparent';
      this.appendChild(this.canvas);
      this.ctx = this.canvas.getContext('2d');
      this._lastColor = '';

      this.p = { ...EMOTIONS.idle };          // current tweened params
      this.emotion = 'idle';
      this.t = 0; this.last = performance.now();
      this.nextEmo = 3.5; this.emoUntil = 0;
      this.gx = 0; this.gy = 0; this.gtx = 0; this.gty = 0; this.nextGaze = 1;
      this.blinkAt = 2; this.blinkT = -1;
      this.active = true;

      this._raf = requestAnimationFrame(this.tick.bind(this));
    }
    disconnectedCallback() { cancelAnimationFrame(this._raf); }

    tick(now) {
      this._raf = requestAnimationFrame(this.tick.bind(this));
      // ---- adaptive frame-rate cap: fast while moving, slow while settled ----
      const elapsed = now - this.last;
      if (elapsed < 1000 / (this.active ? ACTIVE_FPS : IDLE_FPS)) return;

      const speed = clamp(parseFloat(this.getAttribute('speed')) || 1, 0.25, 3);
      // clamp allows real-time stepping down to the idle rate without slowing time
      const dt = Math.min(0.12, elapsed / 1000) * speed;
      this.last = now; this.t += dt;
      const forced = this.getAttribute('emotion');
      const isAuto = !forced || forced === 'auto' || !EMOTIONS[forced];

      // ---- emotion scheduler ----
      if (isAuto) {
        if (this.emotion !== 'idle' && this.t > this.emoUntil) {
          this.emotion = 'idle';
          this.nextEmo = this.t + rand(5, 10);
        } else if (this.emotion === 'idle' && this.t > this.nextEmo) {
          const pick = LOOP[Math.floor(Math.random() * LOOP.length)];
          this.emotion = pick;
          this.emoUntil = this.t + (pick === 'sleepy' ? rand(5, 7) : rand(3, 5));
          this.nextGaze = 0; // retarget gaze on emotion change
        }
      } else this.emotion = forced;
      const E = EMOTIONS[this.emotion];

      // ---- tween params ----
      const k = 1 - Math.exp(-dt * 7);
      for (const key of NUMKEYS) this.p[key] += (E[key] - this.p[key]) * k;

      // ---- gaze / saccades ----
      if (this.t > this.nextGaze) {
        if (E.lock) { this.gtx = E.lock[0]; this.gty = E.lock[1]; }
        else {
          const r = E.gR;
          this.gtx = rand(-r, r); this.gty = rand(-r * 0.55, r * 0.55);
        }
        this.nextGaze = this.t + E.gInt * rand(0.6, 1.4);
      }
      const gk = 1 - Math.exp(-dt * 10);
      this.gx += (this.gtx - this.gx) * gk;
      this.gy += (this.gty - this.gy) * gk;

      // ---- blinks ----
      const blinkDur = this.emotion === 'sleepy' ? 0.9 : 0.26;
      let open = 1;
      if (this.blinkT >= 0) {
        this.blinkT += dt;
        const ph = this.blinkT / blinkDur;
        if (ph >= 1) { this.blinkT = -1; }
        else open = ph < 0.42 ? 1 - ph / 0.42 : (ph - 0.42) / 0.58;
      } else if (this.t > this.blinkAt && this.p.heart < 0.5 && this.emotion !== 'surprised') {
        this.blinkT = 0;
        this.blinkAt = this.t + (this.emotion === 'sleepy' ? rand(1.5, 3) : rand(2.5, 6));
      }
      open = clamp(open, 0.05, 1);

      // Decide the rate for the next frame: fast while moving or a blink/saccade
      // is imminent (look-ahead avoids wake-up lag), slow when settled.
      let tweenErr = 0;
      for (const key of NUMKEYS) tweenErr += Math.abs(E[key] - this.p[key]);
      const gazeErr = Math.abs(this.gtx - this.gx) + Math.abs(this.gty - this.gy);
      const soon = 0.16;
      this.active = this.blinkT >= 0 || gazeErr > 1.5 || tweenErr > 0.02
        || this.t > this.blinkAt - soon || this.t > this.nextGaze - soon;

      this.draw(open);
    }

    draw(open) {
      const cw = this.clientWidth || 2, ch = this.clientHeight || 2;
      const W = Math.round(cw * RENDER_SCALE), H = Math.round(ch * RENDER_SCALE);
      if (this.canvas.width !== W || this.canvas.height !== H) {
        this.canvas.width = W; this.canvas.height = H;
      }
      const S = Math.min(W / 1920, H / 1080);
      const color = this.getAttribute('color') || '#FFAE1E';
      const p = this.p, t = this.t;

      // Glow + ambient tint: update only when the colour actually changes.
      if (color !== this._lastColor) {
        this._lastColor = color;
        const disp = ch / 1080;
        // Single blur pass (large-radius blur is the priciest GPU op per frame).
        this.canvas.style.filter = `drop-shadow(0 0 ${(18 * disp).toFixed(1)}px ${color})`;
        this.bg.style.background =
          `radial-gradient(60% 55% at 50% 42%, ${hexA(color, 0.06)}, rgba(7,5,3,0) 70%), #070503`;
      }

      const a = this.ctx;
      a.setTransform(1, 0, 0, 1, 0, 0);
      a.clearRect(0, 0, W, H);
      a.save();

      // breathing micro-movement
      const breathe = 1 + 0.008 * Math.sin(t * 1.1);
      const bobY = 5 * S * Math.sin(t * 1.1);
      const gx = this.gx * S, gy = this.gy * S + bobY;

      a.translate(W / 2, H / 2 - 60 * S);
      a.scale(breathe, breathe);
      a.fillStyle = color; a.strokeStyle = color;

      const ew0 = 290 * S * p.ew, eh0 = 330 * S * p.eh * open;
      const sep = 300 * S;

      for (const m of [-1, 1]) { // m=-1 left eye, +1 right
        const asymScale = 1 + p.asym * (m < 0 ? 0.45 : -0.15);
        const ew = ew0 * asymScale, eh = eh0 * asymScale;
        const cx = m * sep + gx, cy = gy;
        const x0 = cx - ew / 2, y0 = cy - eh / 2;
        const rT = clamp(p.rT, 0.05, 0.5) * Math.min(ew, eh);
        const rB = clamp(p.rB, 0.05, 0.5) * Math.min(ew, eh);

        if (p.heart < 0.98) {
          a.save();
          a.globalAlpha = 1 - p.heart;
          a.beginPath();
          this.rr(a, x0, y0, ew, eh, rT, rB);
          a.fill();
          a.clip();
          // top lid (slanted): topSlant>0 angry (inner low), <0 sad (outer low)
          if (p.topLid > 0.01 || Math.abs(p.topSlant) > 0.01) {
            const base = p.topLid * eh;
            const slant = p.topSlant * 0.4 * eh;
            const innerY = y0 + base + slant * 0.5;
            const outerY = y0 + base - slant * 0.5;
            const inX = cx + m * -ew, outX = cx + m * ew; // inner toward center
            a.globalCompositeOperation = 'destination-out';
            a.beginPath();
            a.moveTo(inX, y0 - eh); a.lineTo(outX, y0 - eh);
            a.lineTo(outX, outerY); a.lineTo(inX, innerY);
            a.closePath(); a.fill();
            a.globalCompositeOperation = 'source-over';
          }
          // bottom lid: big circle bulging up => happy arch
          if (p.botLid > 0.01) {
            const R = eh * 1.5;
            const topEdge = y0 + eh * (1 - p.botLid);
            a.globalCompositeOperation = 'destination-out';
            a.beginPath();
            a.arc(cx, topEdge + R, R, 0, Math.PI * 2);
            a.fill();
            a.globalCompositeOperation = 'source-over';
          }
          a.restore();
        }
        if (p.heart > 0.02) {
          const beat = 1 + 0.07 * Math.sin(t * 6);
          a.save();
          a.globalAlpha = p.heart;
          this.heart(a, cx, cy, ew * 0.62 * beat * open);
          a.restore();
        }
      }

      // ---- mouth ----
      const my = 330 * S + gy * 0.35, mgx = gx * 0.35;
      const lw = 24 * S;
      a.lineWidth = lw; a.lineCap = 'round'; a.lineJoin = 'round';
      const oAmt = clamp(p.mO * 2 - 0.15, 0, 1);
      const curveAlpha = (1 - p.dots) * (1 - oAmt) * (p.mW > 0.08 ? 1 : p.mW / 0.08);
      if (curveAlpha > 0.02 && p.mW > 0.02) {
        const mw = 250 * S * p.mW;
        a.save(); a.globalAlpha = curveAlpha;
        a.beginPath();
        a.moveTo(mgx - mw / 2, my);
        a.quadraticCurveTo(mgx, my + p.mC * 95 * S, mgx + mw / 2, my);
        a.stroke(); a.restore();
      }
      if (oAmt > 0.02) { // surprised "o"
        a.save(); a.globalAlpha = oAmt;
        a.beginPath();
        a.ellipse(mgx, my + 10 * S, 65 * S * p.mW + 30 * S, (25 + 75 * p.mO) * S, 0, 0, Math.PI * 2);
        a.fill(); a.restore();
      }
      if (p.dots > 0.02) { // thinking "..."
        a.save();
        for (let i = 0; i < 3; i++) {
          a.globalAlpha = p.dots * (0.2 + 0.8 * clamp(Math.sin(t * 4.2 - i * 0.9), 0, 1));
          a.beginPath();
          a.arc(mgx + (i - 1) * 62 * S, my, 15 * S, 0, Math.PI * 2);
          a.fill();
        }
        a.restore();
      }

      a.restore();
    }

    rr(ctx, x, y, w, h, rt, rb) { // rounded rect, separate top/bottom radii
      ctx.moveTo(x + rt, y);
      ctx.lineTo(x + w - rt, y);
      ctx.arcTo(x + w, y, x + w, y + rt, rt);
      ctx.lineTo(x + w, y + h - rb);
      ctx.arcTo(x + w, y + h, x + w - rb, y + h, rb);
      ctx.lineTo(x + rb, y + h);
      ctx.arcTo(x, y + h, x, y + h - rb, rb);
      ctx.lineTo(x, y + rt);
      ctx.arcTo(x, y, x + rt, y, rt);
      ctx.closePath();
    }
    heart(ctx, x, y, s) {
      ctx.beginPath();
      ctx.save();
      ctx.translate(x, y);
      ctx.scale(s, s);
      ctx.moveTo(0, -0.22);
      ctx.bezierCurveTo(-0.55, -0.78, -1.15, -0.05, 0, 0.75);
      ctx.bezierCurveTo(1.15, -0.05, 0.55, -0.78, 0, -0.22);
      ctx.restore();
      ctx.fill();
    }
  }
  if (!customElements.get('robot-face')) customElements.define('robot-face', RobotFace);
})();
