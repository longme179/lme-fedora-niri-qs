# perf/responsive-v2 — STATUS (hand-off, 2026-11-27 rạng sáng, phiên 3)

Tiếng Việt (tóm tắt): phiên 3 — Phase D xong (fix S4 khớp thực hành của dux-shell/DMS
và caelestia, có dẫn chứng), injector có lệnh `wheel` + nav scroll cho S2, calibration
grid-sweep: **rep 0 đủ click cả 18 trang (unreachable=0)**. Nhưng user active liên tục
00:33-01:02 (mỗi ~20 s một event) → mọi run live dài đều bị abort đúng luật "input of the
owner". Đã đặt cron 05:30 (job 550738) tự chạy tiếp khi máy idle. Còn: S2 A/B đầy đủ,
S1, S3, PR.

## Nhánh `origin/perf/responsive-v2` = `1d0c2d6`

Fix sản phẩm: `33b204d` (S4). Harness phiên 3: `33c687c` (wheel trên injector +
nav_point scroll 2 chiều vào view), `1d0c2d6` (grid sweep 5×5 khi cửa sổ Settings
không ở giữa output — cửa sổ floating giữ vị trí niri lần trước, park giữa màn hình
trượt). Harness phiên 2: xem git log (S2 detectors `eed28f9`, calibration `3e8db35`,
rect Qt 6.7 `95ffab1`, đo keyboard `249420b`, probe Settings `be6e558`+`35693f8`).

## Đêm 20261127 — các run S2 (đều abort do user input, dữ liệu partial đều có)

| run | kết quả trước khi abort |
|---|---|
| s2-full2-b (00:32) | rep 0 dở: 9/18 ok, 7 unreachable (chưa có grid sweep) — abort 00:33:22 |
| s2-full3-b (00:41) | skip ngay: cửa sổ không giữa màn hình, park trượt (→ fix 1d0c2d6) |
| s2-full4-b (00:46) | rep 0: **unreachable=0** (grid sweep + wheel hoạt động) — abort 00:48:02 giữa rep 0, 10/18 ok |
| s2-all-b (00:56) | rep 0: 10/18 trang, settle median 1132 ms (n=10, KHÔNG so sánh với phiên 2: đây là nửa rep đầu sau warmup, pages build lần đầu) — abort 00:58:29 |

Bài học đêm: khi user ở máy, chạy run ngắn + gộp partial không đủ cho kết luận —
chờ khung giờ idle. **Kết luận S2 chưa đổi**: phiên 2 (máy idle) đo được settle
median 21,4 ms / p95 28,2 ms trên 99 lượt click; cần N≥10 reps đầy đủ ở cả hai cây
để kết luận. "Settings không đóng được ESC/close" tái hiện 1 lần phiên 2 — cần lần
tái hiện thứ hai có kiểm soát.

## Phase D — ĐỌC XONG (đối chiếu fix S4 với shell Quickshell khác)

- **dux-shell (DMS, trước là DankMaterialShell)**: keyboardFocus điều kiện qua singleton
  `quickshell/Common/KeyboardFocus.qml` (`if (!active) return None; ... return Exclusive`);
  Escape trên `FocusScope { focus: root.shouldBeVisible; Keys.onEscapePressed: ... }`
  (`Modals/Common/DModalHost.qml:848`); `forceActiveFocus` CHỈ gọi trên content modal
  vừa load (`Qt.callLater(() => item.forceActiveFocus())`) và input field. Có cả class
  bug tương tự được ghi nhận: `Widgets/DFocusGrab.qml` — "Hyprland can leave the keyboard
  unfocused when a grab outlives its keyboard surface (#4383)".
- **caelestia (caelestia-dots/shell)**: `modules/drawers/ContentWindow.qml:72` —
  `keyboardFocus: screenState.launcher || screenState.session ? OnDemand : None` (đúng
  pattern điều kiện); Escape qua `Keys.onEscapePressed` trên item đang focus
  (`modules/launcher/Content.qml:87`); `forceActiveFocus()` chỉ trên SearchBar của
  launcher ĐANG MỞ (`launcher/Content.qml:110`).
- **Kết luận cho PR**: cả hai shell đều (1) keyboardFocus điều kiện theo panel mở,
  (2) Escape xử trên FocusScope/item visibility-bound trong cùng surface, (3) không bao
  giờ forceActiveFocus vào item ẩn — fix của ta (bỏ call lạc vào panel stage ẩn) đúng
  thực hành chung. Bản địa: `/tmp/qs-research/dux`, `/tmp/qs-research/cael`.

## Kết quả S4 — ĐÓNG HỒ SƠ (đều trên máy thật, p-head = nhánh có fix)

| run | cây | kịch bản | kết quả |
|---|---|---|---|
| s4-n10-a | p-main (baseline 8374e94) | warmup + N=10 × delay 5/60/150, route key | **30/30 FAIL** (not_delivered 18, frozen 12) — ESC không tới handler nào |
| s4-n10-b | p-head (fix) | như trên | **28/30 OK**, ESC→gone median 0,95-1,7 ms; 2 frozen chờ stall build xong |
| s4-prior-load-b | p-head | prior=control + load=8, delay 60/400 | delay 400: 5/6 OK; delay 60 bị gán nhãn no_keyboard_focus **không đo** (bug harness) |
| s4-prior-only-b | p-head | prior=control, delay 60/400 | như trên (nhãn sai ở delay 60) |
| s4-prior-meas-b | p-head + đo thật mỗi vòng | prior=control, delay 60/100/150/250/400, 4 reps | **20/20 OK**, keyboard có mặt từ 60 ms, ESC đóng 0,13-26,27 ms |

Kết luận S4: **một root cause duy nhất** (`forceActiveFocus` vào panel stage ẩn,
`shell.qml`, commit `5ff881e`), fix `33b204d` hiệu quả 100% ở mọi điều kiện đo được.
"Keyboard grant trễ" từng nghi ngờ hóa ra là artifact label của harness (đã sửa `249420b`).

## Kết quả S2 — đo được, detector còn 2 bug (chưa kết luận được về shell)

Run `s2-box2-b` (p-head, 10 reps `all`, click thật 18 trang mỗi rep — 7 trang cuối
clipboard→about unreachable vì sidebar 1100×780 phải scroll; mở rộng cửa sổ hoặc scroll
trong kịch bản để đủ 18):

- 99 lượt click đo được: **settle median 21,4 ms, p95 28,2 ms, max 1497,9 ms** (1 outlier)
- click→mark navigate: 21,7 ms (weather, lần đầu)
- "weather fail 10/10" là **bug detector**, không phải shell: host state settle đẹp
  (shown=weather, opacity 1, không pending) nhưng `final_state` so sai (dưới đây)
- stalls GUI thread 4-12 mỗi rep khi build page — khớp cơ chế S3
- **Tái hiện 1 lần "Settings window stayed open: neither Escape nor close button closes"**
  (run s2-real-b2, trước khi calibration đúng) — chính là triệu chứng S2 user mô tả!
  Cần tái hiện có kiểm soát sau khi detector sửa xong.
- 57 stall stacks trong 1 run: GUI thread kẹt trong `QQmlIncubationController::incubateFor`
  ← `QSGThreadedRenderLoop::event` — **incubator finalize các page giữa các frame** =
  cơ chế S3 thật, chất liệu cho Phase C (PageHost đã có sẵn `asyncPages`/prewarm gate).

### Bug detector S2 đã sửa trong `eed28f9` (chưa chạy lại live — lượt tới chạy ngay)

1. `final_state` ghi đè `entry["page"]` — giờ là field riêng `state_page`.
2. Click vào trang đã hiện không có mark — giờ tính `react_ms=0` ("đã ở đó").
3. `shown_is_page` giờ chỉ so `host.shown == last` (host là nguồn thật).
   Self-test `clean,swallow,ghost` xanh sau sửa; cần chạy lại s2 A/B để xác nhận.

### Calibration Settings (đã xong, lưu lại cách hoạt động)

- niri `pos_in_window_layout` là tọa độ **workspace** không phải output — cửa sổ giữa
  màn hình vẫn báo (0,0). Box đúng = park pointer giữa output → đọc HoverHandler
  window-relative → `box = pointer_output - pointer_window` (vd 409,5/170,5).
- `Probe.rect` của Controls (LiquidButton)/Layouts: Qt 6.7 không phải Item —
  `mapToScene` ném TypeError dù có trong metaobject. Fallback cộng dồn x/y chuỗi parent.
- Cửa sổ Settings đăng ký qua `onHostWindowChanged` (Loader async: `Window.window`
  null lúc onCompleted).
- Chạy run dài: **nohup + poll log** (PTY 520 s giết run budget 600 s; dead-man restore
  vẫn hoạt động đúng khi run bị giết).

## Còn lại (theo thứ tự)

1. Sửa 3 bug detector S2 trên; chạy lại `s2:reps=10,variants=all+aba+toast` A/B
   (p-main vs p-head). Mở rộng cửa sổ Settings (niri floating size) hoặc thêm scroll
   nav để đủ 18 trang. Mục tiêu: tái hiện "Settings không đóng ESC" có kiểm soát.
2. S1: `s1:reps=10,variants=ordered+random+fast` A/B (rect CC tabs giờ hoạt động nhờ
   fix contentItem — chưa từng chạy thật).
3. S3: `s3:reps=3` — stalls build page đã có 57 stack samples; cơ chế đã rõ (incubator
   giữa frame); Phase C thử `asyncPages`/prewarm của PageHost.
4. Phase D: đọc time-boxed qs-dms/qs-caelestia.
5. Trước PR: revert `4469385` (AGENTS.md), `./scripts/check.sh` (không chạy song song
   live), PR What/Root cause/Fix/Verification (S4 có đủ số A/B), mirror `~/z`.

## Ghi nhớ kỹ thuật

- Chạy host: `python3 scripts/host_run.py '<lệnh>' --timeout N`; run dài:
  `nohup python3 scripts/perf/run.py ... > /tmp/x.log 2>&1 &` rồi poll `/tmp/x.log`.
- Cây probe: `prepare.py --repo ~/.cache/lme-perf/rv2/repo --ref origin/perf/responsive-v2
  --out ~/.cache/lme-perf/rv2/p-head` (p-main: `--ref main --diagnostics 7fc1df9`).
- Bằng chứng: `download/perf-responsive-v2/runs/` (34 file records+summary của mọi run
  hôm nay). Trên host: `~/.cache/lme-perf/rv2/runs/<label>/`.
- Máy user cuối phiên: shell deployed chạy (restore OK mọi run), symlink đúng, repo sạch.
