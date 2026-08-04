// Firefox kiosk profile prefs for the robot face.
// Copied to the kiosk profile dir on deploy; Firefox applies user.js on every start.

// ---- Force GPU acceleration (Firefox blocklists WebRender/canvas accel on
//      aarch64/Tegra, so the Orin's GPU sits idle and everything is software-
//      rasterized). The GL/EGL stack here is healthy, so force it all on. ----
user_pref("gfx.webrender.all", true);                       // GPU compositor (WebRender)
user_pref("gfx.webrender.enabled", true);
user_pref("gfx.webrender.software", false);                 // never fall back to SW WebRender
user_pref("gfx.x11-egl.force-enabled", true);               // EGL backend — required for NVIDIA on X11
user_pref("gfx.canvas.accelerated", true);                  // GPU-accelerate 2D canvas (our workload)
user_pref("gfx.canvas.accelerated.force-enabled", true);
user_pref("layers.acceleration.force-enabled", true);
user_pref("layers.gpu-process.enabled", true);
user_pref("webgl.force-enabled", true);
user_pref("media.hardware-video-decoding.force-enabled", true);

// ---- Kiosk hardening: never show the crash/session-restore page (a robot
//      loses power abruptly — it must boot straight back to its face). ----
user_pref("browser.sessionstore.resume_from_crash", false);
user_pref("browser.sessionstore.max_resumed_crashes", 0);
user_pref("toolkit.startup.max_resumed_crashes", -1);
user_pref("browser.startup.page", 0);

// ---- Kill first-run / update / default-browser / telemetry noise ----
user_pref("browser.shell.checkDefaultBrowser", false);
user_pref("browser.startup.homepage_override.mstone", "ignore");
user_pref("browser.aboutwelcome.enabled", false);
user_pref("datareporting.policy.dataSubmissionEnabled", false);
user_pref("datareporting.healthreport.uploadEnabled", false);
user_pref("app.update.auto", false);
user_pref("app.update.enabled", false);
user_pref("browser.tabs.warnOnClose", false);
user_pref("full-screen-api.warning.timeout", 0);            // no "full screen" toast
user_pref("browser.warnOnQuit", false);
user_pref("signon.rememberSignons", false);                 // don't offer to save the control-panel password
