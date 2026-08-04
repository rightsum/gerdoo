/*
 * Polar plot of a LaserScan on a canvas.
 *
 * Drawn client-side from JSON rather than rendered server-side as images: the
 * Jetson has better things to do than rasterise plots, and JSON at ~360 points
 * / 5 Hz is a few KB/s. It also means zoom is instant and free.
 *
 * Frame convention: ROS REP-103. x forward, y left, angles counter-clockwise
 * from +x. On screen, forward is UP — so a point at angle 0 draws straight up,
 * and something to the robot's left appears on the left of the plot.
 */
(function () {
  "use strict";

  function LidarView(canvas) {
    this.canvas = canvas;
    this.ctx = canvas.getContext("2d");
    this.scan = null;
    this.maxRange = 6;          // metres shown edge-to-edge; user adjustable
    this.dpr = window.devicePixelRatio || 1;
    this.resize();
    window.addEventListener("resize", this.resize.bind(this));
  }

  LidarView.prototype.resize = function () {
    var rect = this.canvas.getBoundingClientRect();
    var size = Math.max(160, Math.min(rect.width, 520));
    this.canvas.width = size * this.dpr;
    this.canvas.height = size * this.dpr;
    this.canvas.style.height = size + "px";
    this.draw();
  };

  LidarView.prototype.setScan = function (scan) {
    this.scan = scan;
    this.draw();
  };

  LidarView.prototype.setMaxRange = function (m) {
    this.maxRange = m;
    this.draw();
  };

  LidarView.prototype.draw = function () {
    var ctx = this.ctx;
    var W = this.canvas.width, H = this.canvas.height;
    var cx = W / 2, cy = H / 2;
    var R = Math.min(W, H) / 2 - 10 * this.dpr;
    var scale = R / this.maxRange;

    ctx.clearRect(0, 0, W, H);
    ctx.fillStyle = "#070d1c";
    ctx.fillRect(0, 0, W, H);

    // Range rings, one per metre while that stays legible.
    var step = this.maxRange <= 2 ? 0.5 : (this.maxRange <= 8 ? 1 : 2);
    ctx.strokeStyle = "rgba(255,255,255,0.10)";
    ctx.fillStyle = "rgba(255,255,255,0.32)";
    ctx.lineWidth = 1 * this.dpr;
    ctx.font = (10 * this.dpr) + "px -apple-system, system-ui, sans-serif";
    ctx.textAlign = "left";
    for (var r = step; r <= this.maxRange + 1e-6; r += step) {
      ctx.beginPath();
      ctx.arc(cx, cy, r * scale, 0, Math.PI * 2);
      ctx.stroke();
      ctx.fillText(r + " m", cx + 4 * this.dpr, cy - r * scale + 12 * this.dpr);
    }

    // Cross-hairs.
    ctx.strokeStyle = "rgba(255,255,255,0.07)";
    ctx.beginPath();
    ctx.moveTo(cx - R, cy); ctx.lineTo(cx + R, cy);
    ctx.moveTo(cx, cy - R); ctx.lineTo(cx, cy + R);
    ctx.stroke();

    if (!this.scan || !this.scan.ranges) {
      ctx.fillStyle = "rgba(255,255,255,0.30)";
      ctx.textAlign = "center";
      ctx.font = (13 * this.dpr) + "px -apple-system, system-ui, sans-serif";
      ctx.fillText("no scan", cx, cy + 4 * this.dpr);
      this.drawRobot(ctx, cx, cy);
      return;
    }

    var s = this.scan;
    var dot = Math.max(1.4, 1.8 * this.dpr);
    var hits = 0;

    for (var i = 0; i < s.ranges.length; i++) {
      var d = s.ranges[i];
      if (d === null || d === undefined) continue;   // no return
      if (d > this.maxRange) continue;               // beyond the view
      hits++;
      var a = s.angle_min + i * s.angle_increment;

      // ROS: x = d*cos(a) forward, y = d*sin(a) left.
      // Canvas: x right, y DOWN. Forward must point up, left must point left.
      var px = cx - d * Math.sin(a) * scale;
      var py = cy - d * Math.cos(a) * scale;

      // Near points are the ones you can collide with — make them read hotter.
      var t = Math.min(1, d / this.maxRange);
      ctx.fillStyle = "rgb(" + Math.round(255 - 150 * t) + "," +
                               Math.round(90 + 130 * t) + "," +
                               Math.round(60 + 180 * t) + ")";
      ctx.beginPath();
      ctx.arc(px, py, dot, 0, Math.PI * 2);
      ctx.fill();
    }

    this.drawRobot(ctx, cx, cy);

    ctx.fillStyle = "rgba(255,255,255,0.45)";
    ctx.textAlign = "left";
    ctx.font = (10 * this.dpr) + "px ui-monospace, monospace";
    ctx.fillText(hits + "/" + s.ranges.length + " pts", 8 * this.dpr, H - 8 * this.dpr);
  };

  LidarView.prototype.drawRobot = function (ctx, cx, cy) {
    // Robot body plus a heading tick, so "which way is forward" is never a
    // guess when reading the plot.
    ctx.fillStyle = "#5b8cff";
    ctx.beginPath();
    ctx.arc(cx, cy, 4 * this.dpr, 0, Math.PI * 2);
    ctx.fill();
    ctx.strokeStyle = "#5b8cff";
    ctx.lineWidth = 2 * this.dpr;
    ctx.beginPath();
    ctx.moveTo(cx, cy);
    ctx.lineTo(cx, cy - 14 * this.dpr);
    ctx.stroke();
  };

  window.LidarView = LidarView;
})();
