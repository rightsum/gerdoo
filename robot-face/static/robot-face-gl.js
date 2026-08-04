/* <robot-face> — WebGL / signed-distance-field renderer.
   Same element, attributes and behaviour as the 2D robot-face.js, but the whole
   face is drawn in one fragment shader: eyes/lids/hearts/mouth are SDFs and the
   glow is a distance falloff in-shader (no separate CSS blur pass). Guaranteed
   GPU path. Falls back to the 2D component if WebGL is unavailable.

   Perf knobs (WebGL is cheap, so these can go higher than the 2D version): */
(function () {
  // Adaptive frame rate: the face is static most of the time (only slow
  // breathing), so we render fast only while something is actually moving
  // (blinks, eye saccades, expression changes) and idle slowly otherwise.
  // Smoother motion than a flat 30fps AND lower average power.
  const ACTIVE_FPS = 60;   // during motion
  const IDLE_FPS = 10;     // while holding still (breathing only)
  const RENDER_SCALE = 0.75;

  const THIS_SRC = (document.currentScript && document.currentScript.src) || '';

  // ---- shared behaviour (identical to the 2D component) ----
  const BASE = {
    ew: 1, eh: 1, rT: 0.32, rB: 0.32,
    topLid: 0, topSlant: 0, botLid: 0,
    asym: 0, mC: 0.18, mW: 1, mO: 0, dots: 0, heart: 0
  };
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
  function hexRGB(hex) {
    const h = (hex || '#FFAE1E').replace('#', '');
    const n = parseInt(h.length === 3 ? h.replace(/(.)/g, '$1$1') : h, 16);
    return [((n >> 16) & 255) / 255, ((n >> 8) & 255) / 255, (n & 255) / 255];
  }

  // ---- shaders ----
  const VERT = `attribute vec2 a; void main(){ gl_Position = vec4(a, 0.0, 1.0); }`;

  const FRAG = `
  precision highp float;
  uniform vec2  uRes, uCenter, uGaze;
  uniform float uScale, uTime;
  uniform vec3  uColor;
  uniform float uEw,uEh,uRT,uRB,uTopLid,uTopSlant,uBotLid,uAsym,uMC,uMW,uMO,uDots,uHeart,uOpen;

  const float EDGE = 2.0;      // edge softness (design units)
  const float GLOWR = 30.0;    // glow falloff distance
  const float GLOWA = 0.7;     // glow strength

  float dot2(vec2 v){ return dot(v,v); }

  // rounded box, per-corner radius (y-up local coords); r = (TR,BR,TL,BL)
  float sdRoundBox(vec2 p, vec2 b, vec4 r){
    r.xy = (p.x>0.0)? r.xy : r.zw;
    r.x  = (p.y>0.0)? r.x  : r.y;
    vec2 q = abs(p)-b+r.x;
    return min(max(q.x,q.y),0.0)+length(max(q,0.0))-r.x;
  }
  // iq heart SDF (point down, spans roughly [-1,1])
  float sdHeart(vec2 p){
    p.x = abs(p.x);
    if(p.y+p.x>1.0) return sqrt(dot2(p-vec2(0.25,0.75)))-sqrt(2.0)/4.0;
    return sqrt(min(dot2(p-vec2(0.0,1.0)), dot2(p-0.5*max(p.x+p.y,0.0))))*sign(p.x-p.y);
  }
  float sdSegment(vec2 p, vec2 a, vec2 b){
    vec2 pa=p-a, ba=b-a;
    float h=clamp(dot(pa,ba)/dot(ba,ba),0.0,1.0);
    return length(pa-ba*h);
  }
  // iq quadratic bezier distance
  float sdBezier(vec2 pos, vec2 A, vec2 B, vec2 C){
    vec2 a=B-A, b=A-2.0*B+C, c=a*2.0, d=A-pos;
    float kk=1.0/dot(b,b);
    float kx=kk*dot(a,b);
    float ky=kk*(2.0*dot(a,a)+dot(d,b))/3.0;
    float kz=kk*dot(d,a);
    float res=0.0;
    float p=ky-kx*kx;
    float q=kx*(2.0*kx*kx-3.0*ky)+kz;
    float h=q*q+4.0*p*p*p;
    if(h>=0.0){
      h=sqrt(h);
      vec2 x=(vec2(h,-h)-q)/2.0;
      vec2 uv=sign(x)*pow(abs(x),vec2(1.0/3.0));
      float t=clamp(uv.x+uv.y-kx,0.0,1.0);
      vec2 qd=d+(c+b*t)*t;
      res=dot(qd,qd);
    } else {
      float z=sqrt(-p);
      float v=acos(q/(p*z*2.0))/3.0;
      float m=cos(v), n=sin(v)*1.732050808;
      vec3 t=clamp(vec3(m+m,-n-m,n-m)*z-kx,0.0,1.0);
      vec2 qx=d+(c+b*t.x)*t.x;
      vec2 qy=d+(c+b*t.y)*t.y;
      res=min(dot(qx,qx),dot(qy,qy));
    }
    return sqrt(res);
  }

  float sfill(float d){ return 1.0 - smoothstep(-EDGE, EDGE, d); }
  float sglow(float d){ return exp(-max(d,0.0)/GLOWR); }
  // Pure solid core (=1 inside) with a softer halo outside; max (not sum) so the
  // fill stays exactly uColor instead of overshooting/desaturating.
  float lume(float d){ return max(sfill(d), GLOWA*sglow(d)); }

  // one eye SDF (m = -1 left, +1 right)
  float eyeSDF(vec2 dp, float m){
    float asym = 1.0 + uAsym*(m<0.0 ? 0.45 : -0.15);
    float ewF = 290.0*uEw*asym;               // full width
    float ehF = 330.0*uEh*asym*uOpen;          // full height (blink scales)
    vec2  c   = vec2(m*300.0, 0.0) + uGaze;    // eye center
    vec2  le  = dp - c;
    float rT  = clamp(uRT,0.05,0.5)*min(ewF,ehF);
    float rB  = clamp(uRB,0.05,0.5)*min(ewF,ehF);
    float d   = sdRoundBox(vec2(le.x, -le.y), vec2(ewF*0.5, ehF*0.5), vec4(rT,rB,rT,rB));
    // top lid (linear slanted cut)
    float y0    = c.y - ehF*0.5;
    float base  = uTopLid*ehF;
    float slant = uTopSlant*0.4*ehF;
    float innerY= y0 + base + slant*0.5;
    float outerY= y0 + base - slant*0.5;
    float inX   = c.x - m*ewF;
    float outX  = c.x + m*ewF;
    float t     = clamp((dp.x - inX)/(outX - inX), 0.0, 1.0);
    float lidY  = mix(innerY, outerY, t);
    d = max(d, lidY - dp.y);                    // remove above the lid line
    // bottom arch (happy)
    if(uBotLid>0.01){
      float R = ehF*1.5;
      float topEdge = c.y + ehF*0.5 - ehF*uBotLid;
      d = max(d, R - length(dp - vec2(c.x, topEdge + R)));
    }
    return d;
  }

  float heartLume(vec2 dp, float m){
    float asym = 1.0 + uAsym*(m<0.0 ? 0.45 : -0.15);
    float ewF = 290.0*uEw*asym;
    float beat = 1.0 + 0.07*sin(uTime*6.0);
    float s = ewF*0.62*beat*max(uOpen,0.6);
    vec2 c = vec2(m*300.0, 0.0) + uGaze;
    vec2 lh = (dp - c) / s;
    float d = sdHeart(vec2(lh.x, -lh.y + 0.15)) * s;   // +0.15 centres it on the eye
    return lume(d);
  }

  float mouthLume(vec2 dp){
    vec2 mc = vec2(uGaze.x*0.35, 330.0 + uGaze.y*0.35);
    float I = 0.0;
    float oAmt = clamp(uMO*2.0 - 0.15, 0.0, 1.0);
    float mw = 250.0*uMW;
    float curveA = (1.0-uDots)*(1.0-oAmt)*clamp(uMW/0.08, 0.0, 1.0);
    if(curveA>0.01 && uMW>0.02){
      vec2 A=vec2(mc.x-mw*0.5, mc.y);
      vec2 B=vec2(mc.x, mc.y + uMC*95.0);
      vec2 C=vec2(mc.x+mw*0.5, mc.y);
      float dc = (abs(uMC)<0.03) ? sdSegment(dp,A,C) : sdBezier(dp,A,B,C);
      I = max(I, lume(dc - 12.0)*curveA);
    }
    if(oAmt>0.01){
      vec2 oc=vec2(mc.x, mc.y+10.0);
      vec2 rad=vec2(65.0*uMW+30.0, 25.0+75.0*uMO);
      float k=length((dp-oc)/rad);
      I = max(I, lume((k-1.0)*min(rad.x,rad.y))*oAmt);
    }
    if(uDots>0.01){
      for(int i=0;i<3;i++){
        float fi=float(i);
        float a=uDots*(0.2+0.8*clamp(sin(uTime*4.2 - fi*0.9),0.0,1.0));
        I = max(I, lume(length(dp-vec2(mc.x+(fi-1.0)*62.0, mc.y))-15.0)*a);
      }
    }
    return I;
  }

  void main(){
    vec2 fc = gl_FragCoord.xy;
    vec2 dp = (vec2(fc.x, uRes.y - fc.y) - uCenter) / uScale;

    float r = length(dp);
    vec3 bg = vec3(0.027,0.020,0.012) + uColor*0.05*exp(-(r*r)/(700.0*700.0));

    // Cheap bounding early-out: for pixels far from the face bounding box (past
    // where the glow can reach) skip all the per-shape SDF math and just emit bg.
    // This is what makes the SDF renderer competitive — most of the screen is empty.
    vec2 bb = abs(dp - vec2(0.0, 150.0)) - vec2(560.0, 430.0);
    float bd = length(max(bb, 0.0)) + min(max(bb.x, bb.y), 0.0);
    if (bd > 7.0*GLOWR) { gl_FragColor = vec4(bg, 1.0); return; }

    float eL = lume(eyeSDF(dp,-1.0));
    float eR = lume(eyeSDF(dp, 1.0));
    float hL = heartLume(dp,-1.0);
    float hR = heartLume(dp, 1.0);
    float eyes = max(mix(eL,hL,uHeart), mix(eR,hR,uHeart));
    float total = max(eyes, mouthLume(dp));

    vec3 col = bg + uColor*total;
    gl_FragColor = vec4(min(col, vec3(1.0)), 1.0);
  }`;

  function makeProgram(gl) {
    function sh(type, src) {
      const s = gl.createShader(type);
      gl.shaderSource(s, src); gl.compileShader(s);
      if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) {
        console.error('robot-face-gl shader:', gl.getShaderInfoLog(s)); return null;
      }
      return s;
    }
    const vs = sh(gl.VERTEX_SHADER, VERT), fs = sh(gl.FRAGMENT_SHADER, FRAG);
    if (!vs || !fs) return null;
    const p = gl.createProgram();
    gl.attachShader(p, vs); gl.attachShader(p, fs); gl.linkProgram(p);
    if (!gl.getProgramParameter(p, gl.LINK_STATUS)) {
      console.error('robot-face-gl link:', gl.getProgramInfoLog(p)); return null;
    }
    return p;
  }

  class RobotFaceGL extends HTMLElement {
    connectedCallback() {
      this.style.display = 'block';
      this.style.position = this.style.position || 'relative';
      this.style.width = '100%'; this.style.height = '100%'; this.style.overflow = 'hidden';
      this.canvas = document.createElement('canvas');
      this.canvas.style.cssText = 'position:absolute;inset:0;width:100%;height:100%;display:block';
      this.appendChild(this.canvas);
      const gl = this.gl = this.canvas.getContext('webgl', { antialias: false, alpha: false, powerPreference: 'high-performance' })
        || this.canvas.getContext('experimental-webgl');
      this.prog = makeProgram(gl);
      gl.useProgram(this.prog);
      const buf = gl.createBuffer();
      gl.bindBuffer(gl.ARRAY_BUFFER, buf);
      gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
      const loc = gl.getAttribLocation(this.prog, 'a');
      gl.enableVertexAttribArray(loc);
      gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);
      this.u = {};
      ['uRes', 'uCenter', 'uGaze', 'uScale', 'uTime', 'uColor', 'uEw', 'uEh', 'uRT', 'uRB',
       'uTopLid', 'uTopSlant', 'uBotLid', 'uAsym', 'uMC', 'uMW', 'uMO', 'uDots', 'uHeart', 'uOpen']
        .forEach(n => this.u[n] = gl.getUniformLocation(this.prog, n));

      this.p = { ...EMOTIONS.idle };
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
      const elapsed = now - this.last;
      if (elapsed < 1000 / (this.active ? ACTIVE_FPS : IDLE_FPS)) return;
      const speed = clamp(parseFloat(this.getAttribute('speed')) || 1, 0.25, 3);
      // clamp allows real-time stepping down to the idle rate without slowing time
      const dt = Math.min(0.12, elapsed / 1000) * speed;
      this.last = now; this.t += dt;
      const forced = this.getAttribute('emotion');
      const isAuto = !forced || forced === 'auto' || !EMOTIONS[forced];

      if (isAuto) {
        if (this.emotion !== 'idle' && this.t > this.emoUntil) {
          this.emotion = 'idle'; this.nextEmo = this.t + rand(5, 10);
        } else if (this.emotion === 'idle' && this.t > this.nextEmo) {
          const pick = LOOP[Math.floor(Math.random() * LOOP.length)];
          this.emotion = pick;
          this.emoUntil = this.t + (pick === 'sleepy' ? rand(5, 7) : rand(3, 5));
          this.nextGaze = 0;
        }
      } else this.emotion = forced;
      const E = EMOTIONS[this.emotion];

      const k = 1 - Math.exp(-dt * 7);
      for (const key of NUMKEYS) this.p[key] += (E[key] - this.p[key]) * k;

      if (this.t > this.nextGaze) {
        if (E.lock) { this.gtx = E.lock[0]; this.gty = E.lock[1]; }
        else { const r = E.gR; this.gtx = rand(-r, r); this.gty = rand(-r * 0.55, r * 0.55); }
        this.nextGaze = this.t + E.gInt * rand(0.6, 1.4);
      }
      const gk = 1 - Math.exp(-dt * 10);
      this.gx += (this.gtx - this.gx) * gk;
      this.gy += (this.gty - this.gy) * gk;

      const blinkDur = this.emotion === 'sleepy' ? 0.9 : 0.26;
      let open = 1;
      if (this.blinkT >= 0) {
        this.blinkT += dt;
        const ph = this.blinkT / blinkDur;
        if (ph >= 1) this.blinkT = -1;
        else open = ph < 0.42 ? 1 - ph / 0.42 : (ph - 0.42) / 0.58;
      } else if (this.t > this.blinkAt && this.p.heart < 0.5 && this.emotion !== 'surprised') {
        this.blinkT = 0;
        this.blinkAt = this.t + (this.emotion === 'sleepy' ? rand(1.5, 3) : rand(2.5, 6));
      }
      open = clamp(open, 0.05, 1);

      // Decide the rate for the *next* frame: fast while anything is moving or a
      // blink/saccade is imminent (look-ahead avoids wake-up lag), slow when settled.
      let tweenErr = 0;
      for (const key of NUMKEYS) tweenErr += Math.abs(E[key] - this.p[key]);
      const gazeErr = Math.abs(this.gtx - this.gx) + Math.abs(this.gty - this.gy);
      const soon = 0.16;
      this.active = this.blinkT >= 0 || gazeErr > 1.5 || tweenErr > 0.02
        || this.t > this.blinkAt - soon || this.t > this.nextGaze - soon;

      this.draw(open);
    }

    draw(open) {
      const gl = this.gl, p = this.p;
      const cw = this.clientWidth || 2, ch = this.clientHeight || 2;
      const W = Math.round(cw * RENDER_SCALE), H = Math.round(ch * RENDER_SCALE);
      if (this.canvas.width !== W || this.canvas.height !== H) {
        this.canvas.width = W; this.canvas.height = H;
        gl.viewport(0, 0, W, H);
      }
      const S = Math.min(W / 1920, H / 1080);
      const breathe = 1 + 0.008 * Math.sin(this.t * 1.1);
      const bob = 5 * Math.sin(this.t * 1.1);
      const u = this.u;
      gl.uniform2f(u.uRes, W, H);
      gl.uniform2f(u.uCenter, W / 2, H / 2 - 60 * S);
      gl.uniform2f(u.uGaze, this.gx, this.gy + bob);
      gl.uniform1f(u.uScale, S * breathe);
      gl.uniform1f(u.uTime, this.t);
      gl.uniform3fv(u.uColor, hexRGB(this.getAttribute('color') || '#FFAE1E'));
      gl.uniform1f(u.uEw, p.ew); gl.uniform1f(u.uEh, p.eh);
      gl.uniform1f(u.uRT, p.rT); gl.uniform1f(u.uRB, p.rB);
      gl.uniform1f(u.uTopLid, p.topLid); gl.uniform1f(u.uTopSlant, p.topSlant);
      gl.uniform1f(u.uBotLid, p.botLid); gl.uniform1f(u.uAsym, p.asym);
      gl.uniform1f(u.uMC, p.mC); gl.uniform1f(u.uMW, p.mW);
      gl.uniform1f(u.uMO, p.mO); gl.uniform1f(u.uDots, p.dots);
      gl.uniform1f(u.uHeart, p.heart); gl.uniform1f(u.uOpen, open);
      gl.drawArrays(gl.TRIANGLES, 0, 3);
    }
  }

  // ---- register, or fall back to the 2D component ----
  function webglWorks() {
    try {
      const c = document.createElement('canvas');
      const gl = c.getContext('webgl') || c.getContext('experimental-webgl');
      if (!gl) return false;
      return !!makeProgram(gl);   // also verifies the shader actually compiles here
    } catch (e) { return false; }
  }

  if (customElements.get('robot-face')) return;
  if (webglWorks()) {
    customElements.define('robot-face', RobotFaceGL);
  } else {
    console.warn('robot-face-gl: WebGL unavailable, loading 2D fallback');
    const s = document.createElement('script');
    s.src = THIS_SRC.replace('robot-face-gl.js', 'robot-face.js');
    document.head.appendChild(s);
  }
})();
