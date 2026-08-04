# 010 — Hand gesture detection + tracking, and a GPU acceleration evaluation

| | |
|---|---|
| **Date** | 2026-08-04 |
| **Type** | Feature + evaluation |
| **Status** | ✅ CPU version shipped and running · ⏸️ GPU version **evaluated, benchmarked, deliberately not built** |
| **Decision** | Ship CPU now. GPU path proven viable and fully documented below — **resume when tracking needs it**, not before |
| **Artifacts** | `robot-face/gesture_detector.py`, `gesture.py`, `deploy/gesture.service` |

---

## Part 1 — What was built and is running

Detects a **closed fist** (and six other gestures) from the Brio 500, and publishes **where the hand is**, for future neck tracking.

| | |
|---|---|
| Model | MediaPipe `GestureRecognizer`, canned model, 8.0 MB |
| Classes | `Closed_Fist`, `Open_Palm`, `Pointing_Up`, `Thumb_Up`, `Thumb_Down`, `Victory`, `ILoveYou` |
| Rate | 4 Hz |
| Cost | **57 % of one core** (of six) ≈ 9 % of the machine, on demand only |
| Verified | `Thumb_Up`, right hand, score 0.56 — live through the panel |

### Two constraints forced the architecture

**1. Dependency isolation was not optional.** MediaPipe pulls **numpy 2.2.6 and cv2 5.0.0**. The system runs **numpy 1.21.5 and cv2 4.8.0**, which ROS Humble depends on. Installing MediaPipe system-wide would have broken the robot. It lives in `~/gesture-venv` and nothing in the Flask app imports it.

> `python3-venv` is not installed and needs sudo. Worked around with `pip3 install --user virtualenv`, which needs none.

**2. The detector cannot open the camera.** V4L2 permits exactly one reader, and the Flask app owns the device so it can serve the video stream. So frames come over localhost:

```
robot-face (owns camera, MJPEG passthrough)
    │  GET /api/camera/frame.jpg        localhost-only
    ▼
gesture_detector  (own venv, MediaPipe)
    │  POST /api/gesture/ingest         localhost-only
    ▼
robot-face ── SSE ──► control panel
```

Same shape as `scan_bridge.py` ([log 008](008-2026-08-04-control-panel-camera-lidar.md)), for the same reasons: keep an awkward dependency out of the always-on app, and let it crash without taking the face down.

Reading a frame also refreshes the camera's idle timer, so detection keeps the camera alive exactly as a browser viewer would.

### Tracking — position was free

The recogniser computes 21 landmarks per hand *to classify the gesture*. The first version read only the category and threw the landmarks away. Reading them costs nothing:

```json
"pos": {
  "x": 0.62, "y": 0.41,
  "err_x": +0.12, "err_y": -0.09,
  "size": 0.28,
  "wrist_x": 0.60, "wrist_y": 0.47
}
```

- **`err_x` / `err_y`** — offset from frame centre, normalised. This is precisely what a pan/tilt controller consumes: drive the servos until both reach zero.
- **`size`** — bounding-box diagonal, a usable proxy for distance.
- **`wrist_x/y`** — landmark 0. Steadier than the centroid when fingers move, which matters if you track *through* a gesture change.

Normalised 0..1 coordinates, so they stay valid if camera resolution changes.

**Classification is debounced (2 frames); position is not.** Debouncing coordinates would add lag to a control loop, and the reticle should keep following a hand whose gesture is still being classified.

Panel shows a gesture badge plus a tracking reticle (green, yellow for a fist) and a live `x / y / err / size` readout.

---

## Part 2 — GPU evaluation

### Why it came up

120 ms per frame on a board with **1024 CUDA cores and 67 TOPS** is absurd. The GPU sits completely idle.

### MediaPipe on GPU: closed door

```
GPU: FAILED -> ValidatedGraphConfig Initialization failed.
              ImageCloneCalculator: GPU processing is disabled in build flags
```

The prebuilt aarch64 wheel is **compiled CPU-only**. Its own logs say so twice:

```
Created TensorFlow Lite XNNPACK delegate for CPU
Hand Gesture Recognizer contains CPU only ops. Sets acceleration to Xnnpack
```

Not a misconfiguration. Confirmed externally:

| Source | Finding |
|---|---|
| [mediapipe#5690](https://github.com/google-ai-edge/mediapipe/issues/5690) | Same error, same platform (arm64, Ubuntu 22.04, JetPack 6). Opened **Oct 2024**, still open, awaiting a Google engineer. No workaround |
| [NVIDIA forum, JP6.2](https://forums.developer.nvidia.com/t/mediapipe-build-for-jetson-orin-nano-jp6-2/329399) | NVIDIA moderator: *"Unfortunately, they didn't support Jetson officially"* |
| [anion0278/mediapipe-jetson](https://github.com/anion0278/mediapipe-jetson) | Has CUDA — but MediaPipe **0.8.9, JetPack 4.6, CUDA 10.2**. Jetson Nano era, useless here |
| [PINTO0309/mediapipe-bin](https://github.com/PINTO0309/mediapipe-bin) | aarch64 wheels, **CPU only** |

**Conclusion: there is no MediaPipe GPU path on Orin + JetPack 6 short of building from source with GPU flags — which upstream does not support.**

### ⚠️ A benchmarking mistake worth remembering

The first measurement said **65 ms/frame**. That was taken on a **blank `np.zeros` image**, where MediaPipe finds no hand and **skips the landmark stage entirely**.

On a real camera frame it is **120 ms** — nearly double. Every timing below is on real frames.

Related: resolution barely matters, because MediaPipe rescales internally.

| Input | Time |
|---|---|
| 1280×720 | 119.7 ms |
| 640×360 | 116.8 ms |

So decoding at half size (`IMREAD_REDUCED_COLOR_2`) gave **no** improvement — 92 % CPU vs 89.8 %. The cost is inference, not decode. A reasonable-sounding optimisation that measurement disproved.

`VIDEO` running mode also showed no gain (115 ms vs 103 ms) — but that test also lacked a hand, so tracking never engaged. **Its benefit remains unmeasured** and is worth retesting with a hand in frame.

---

## Part 3 — TensorRT: benchmarked, viable, not built

TensorRT **10.3.0 with Python bindings is already installed** (JetPack 6.2), and `trtexec` is at `/usr/src/tensorrt/bin/trtexec`. No PyTorch needed.

### Measured on this hardware

Both engines built from ONNX and benchmarked with `trtexec --fp16`:

| Stage | GPU compute (mean) | Throughput | Engine size |
|---|---|---|---|
| Palm detection | **2.83 ms** | 352 qps | 2.5 MB |
| Hand landmarks | **1.41 ms** | 704 qps | 2.4 MB |
| **Combined** | **≈ 4.2 ms** | | 4.9 MB |

**Versus 120 ms on CPU — roughly 28× faster.** Palm detection latency percentiles: min 2.63 ms, median 2.67 ms, p99 5.47 ms.

That would take gesture work from 4 Hz to comfortably 30 Hz+, and free the 57 % core.

### Everything needed to resume

**Models** — note the **LFS media endpoint**; the normal `raw.githubusercontent.com` URL returns a 132-byte Git LFS *pointer*, not the model:

```bash
curl -sSL -o palm.onnx \
  "https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/palm_detection_mediapipe/palm_detection_mediapipe_2023feb.onnx"
curl -sSL -o handpose.onnx \
  "https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/handpose_estimation_mediapipe/handpose_estimation_mediapipe_2023feb.onnx"
# 3.8 MB and 4.0 MB respectively
```

**Build the engines** (~2.5 min each; engines are specific to this GPU *and* TensorRT version, so rebuild rather than copy):

```bash
/usr/src/tensorrt/bin/trtexec --onnx=palm.onnx     --saveEngine=palm.engine     --fp16
/usr/src/tensorrt/bin/trtexec --onnx=handpose.onnx --saveEngine=handpose.engine --fp16
```

**Tensor shapes** — note **NHWC**, not the NCHW usually assumed:

```
palm.engine
  INPUT   input_1      (1, 192, 192, 3)  FLOAT
  OUTPUT  Identity     (1, 2016, 18)     FLOAT   # 2016 anchors x 18 (box + 7 keypoints)
  OUTPUT  Identity_1   (1, 2016, 1)      FLOAT   # per-anchor score

handpose.engine
  INPUT   input_1      (1, 224, 224, 3)  FLOAT
  OUTPUT  Identity     (1, 63)           FLOAT   # 21 landmarks x 3, screen space
  OUTPUT  Identity_1   (1, 1)            FLOAT   # hand presence confidence
  OUTPUT  Identity_2   (1, 1)            FLOAT   # handedness
  OUTPUT  Identity_3   (1, 63)           FLOAT   # 21 landmarks x 3, world space
```

**Reference pre/post-processing** — the real work, and the reason this is an afternoon not an install:

```
https://raw.githubusercontent.com/opencv/opencv_zoo/main/models/palm_detection_mediapipe/mp_palmdet.py
https://raw.githubusercontent.com/opencv/opencv_zoo/main/models/handpose_estimation_mediapipe/mp_handpose.py
```

Remaining work is what MediaPipe did for free:
1. Letterbox the frame to 192×192
2. Decode 2016 anchors + NMS → oriented hand box
3. Crop and **rotate** to 224×224 for the landmark stage
4. Map landmarks back to full-frame coordinates
5. Classify fist from landmark geometry (a fingertip is curled when it is closer to the wrist than its own middle joint)

Step 5 is a **gain**, not a cost: thresholds become ours instead of an inherited black box.

### Path not taken: `trt_pose_hand`

[NVIDIA-AI-IOT/trt_pose_hand](https://github.com/NVIDIA-AI-IOT/trt_pose_hand) is NVIDIA's own GPU hand-gesture project and has `fist` among its six classes. Rejected in favour of the ONNX route:

| | trt_pose_hand | ONNX → TensorRT |
|---|---|---|
| Dependencies | PyTorch (~2 GB) + torchvision (**build from source**, 30–60 min on Jetson) + torch2trt + trt_pose | **none** — TensorRT 10.3 already present |
| JetPack 6 status | torch2trt *"seems to work… issues with some models"*; trt_pose dates to 2019 | engines **built and benchmarked here** |
| Model size | 85 MB ResNet18 | **3.8 + 4.0 MB** |
| Output | 6 fixed classes | **21 landmarks** — the format `gesture_detector.py` already consumes |
| Tested on this board | no | **yes, above** |

The decisive point is the output format: the ONNX route returns the same 21 landmarks, so the existing position/`err_x`/`err_y` tracking survives untouched. `trt_pose_hand` would mean rewriting it.

---

## Part 4 — Why we stopped, and when to resume

**Stopped because nothing currently needs it.** Detection at 4 Hz is fine — a human cannot change gesture faster. The CPU cost is 9 % of the machine, on demand.

**The trigger to resume is neck tracking.** That is where the current numbers genuinely fail:

```
inference        ~120 ms
sample interval  ~250 ms  (4 Hz)
+ transport hops
──────────────────────────
total lag        ~300-400 ms
```

Move your hand and the neck starts moving a third of a second later — visibly laggy, and slow enough that any useful gain will oscillate. **Detection at 4 Hz is acceptable; tracking at 4 Hz is not.**

At 4.2 ms the same loop runs at 30 Hz with ~30 ms lag, which feels instant.

**Do it once, for everything.** When the two OV9281 global-shutter cameras arrive, continuous stereo vision will be GPU-bound for real. Porting the whole vision stack to TensorRT together beats porting gestures now and everything else again later.

### Cheaper things to try first, if lag is the only problem

1. Raise `GESTURE_HZ` (env var) — costs CPU linearly, and there are 6 cores
2. Put a **P-controller with a deadzone on the Teensy** rather than commanding absolute angles from the Jetson, so servo motion stays smooth between updates
3. Retest MediaPipe `VIDEO` mode **with a hand in frame** — its benefit is genuinely unmeasured

### "Always look at the eyes"

Same pipeline, different model — swap `GestureRecognizer` for MediaPipe's `FaceLandmarker` and publish eye-landmark position. Faces move slower than hands, so 4 Hz is genuinely adequate there. No GPU work needed for that specific goal.

---

## Takeaways

1. **Benchmark on representative input.** A blank frame skipped the landmark stage and under-reported cost by ~2×, which would have led to picking a frame rate the hardware could not sustain.
2. **Measure the optimisation you assume is obvious.** Half-size decode looked certain to help; it changed nothing, because inference not decode was the cost.
3. **Check the output format before choosing a model.** Matching MediaPipe's 21 landmarks means the tracking code survives a backend swap — worth more than the 85 MB vs 8 MB difference.
4. **Isolate dependencies that fight the system.** numpy 2.2 vs 1.21 would have broken ROS; a venv and a localhost push kept both alive.
5. **Position is often already computed.** The landmarks needed for classification are exactly the landmarks needed for tracking.
6. **A proven-but-unbuilt path is a legitimate deliverable.** Engines built, numbers measured, shapes and URLs recorded — the decision can be made later on evidence rather than guesswork.

## Related

- [008](008-2026-08-04-control-panel-camera-lidar.md) — the panel and camera this extends; MJPEG passthrough
- [002](002-2026-08-04-usb-topology-and-peripheral-split.md) — USB bandwidth ceiling for the OV9281 pair
- `ACTION-PLAN.md` — section D (neck hardware) gates the tracking work
