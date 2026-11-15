#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use eframe::egui::{self, Align, Color32, FontId, Layout, RichText, Sense, Stroke, Vec2};
use raw_window_handle::{HasWindowHandle, RawWindowHandle};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::collections::HashSet;
use std::fs;
use std::io::{BufRead, BufReader, Read, Write};
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::mpsc::{self, Receiver, TryRecvError};
#[cfg(windows)]
use std::os::windows::process::CommandExt;
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};

mod update;
use update::{UpdateRelease, UpdateStatus, Updater};

const BG: Color32 = Color32::from_rgb(10, 10, 17);
const SIDE: Color32 = Color32::from_rgb(15, 15, 25);
const CARD: Color32 = Color32::from_rgb(21, 21, 33);
const CARD2: Color32 = Color32::from_rgb(29, 29, 45);
const BORDER: Color32 = Color32::from_rgb(41, 41, 61);
const TEXT: Color32 = Color32::from_rgb(245, 245, 251);
const SUB: Color32 = Color32::from_rgb(159, 159, 184);
const ACCENT: Color32 = Color32::from_rgb(139, 92, 246);
const CYAN: Color32 = Color32::from_rgb(52, 232, 192);

const MEDIA_EXT: &[&str] = &[
    "mp4", "m4v", "mkv", "avi", "mov", "wmv", "webm", "flv", "mpg", "mpeg", "m2ts", "mts", "ts",
    "3gp", "ogv", "vob", "asf", "rm", "rmvb", "mp3", "flac", "wav", "ogg", "oga", "opus", "m4a",
    "aac", "wma", "aiff", "aif", "ape", "ac3", "amr", "wv",
];

#[derive(Serialize, Deserialize)]
#[serde(default)]
struct Saved {
    language: String,
    library: Vec<PathBuf>,
    volume: f32,
    speed: f64,
    repeat: bool,
    shuffle: bool,
    ambient: bool,
    volume_boost: bool,
    stable_volume: bool,
    annotations: bool,
}

impl Default for Saved {
    fn default() -> Self {
        Self { language: "system".into(), library: Vec::new(), volume: 80.0, speed: 1.0, repeat: false, shuffle: false,
            ambient: false, volume_boost: false, stable_volume: false, annotations: true }
    }
}

#[derive(Clone, Copy, PartialEq)]
enum Page {
    Player,
    Library,
}

trait ReadWrite: Read + Write {}
impl<T: Read + Write> ReadWrite for T {}

#[cfg(windows)]
#[derive(Default)]
struct NativeVideo {
    parent: usize,
    child: usize,
}

#[cfg(not(windows))]
#[derive(Default)]
struct NativeVideo;

#[cfg(not(windows))]
impl NativeVideo {
    fn place(&self, _rect: egui::Rect, _scale: f32, _visible: bool, _mpv: &mut Mpv) {}
    fn hide(&self) {}
    fn window_id(&self) -> Option<usize> { None }
}

#[cfg(windows)]
impl NativeVideo {
    fn ensure(&mut self, handle: RawWindowHandle) {
        let RawWindowHandle::Win32(win32) = handle else { return };
        let parent = win32.hwnd.get() as usize;
        if parent == self.parent && self.child != 0 { return; }
        self.parent = parent;
        let class: Vec<u16> = "STATIC\0".encode_utf16().collect();
        let empty = [0u16];
        unsafe {
            let instance = GetModuleHandleW(std::ptr::null());
            let child = CreateWindowExW(
                0, class.as_ptr(), empty.as_ptr(), WS_CHILD | WS_CLIPSIBLINGS,
                0, 0, 0, 0, parent as *mut _, std::ptr::null_mut(), instance, std::ptr::null_mut(),
            );
            self.child = child as usize;
        }
    }

    fn place(&self, rect: egui::Rect, scale: f32, visible: bool, mpv: &mut Mpv) {
        if self.child == 0 { return; }
        mpv.window_id = Some(self.child);
        let x = (rect.min.x * scale).round() as i32;
        let y = (rect.min.y * scale).round() as i32;
        let w = (rect.width() * scale).round().max(1.0) as i32;
        let h = (rect.height() * scale).round().max(1.0) as i32;
        unsafe {
            SetWindowPos(self.child as *mut _, std::ptr::null_mut(), x, y, w, h, SWP_NOZORDER | SWP_NOACTIVATE);
            ShowWindow(self.child as *mut _, if visible { SW_SHOW } else { SW_HIDE });
        }
    }

    fn hide(&self) {
        if self.child != 0 { unsafe { ShowWindow(self.child as *mut _, SW_HIDE); } }
    }

    fn window_id(&self) -> Option<usize> { (self.child != 0).then_some(self.child) }
}

#[cfg(windows)]
impl Drop for NativeVideo {
    fn drop(&mut self) {
        if self.child != 0 { unsafe { DestroyWindow(self.child as *mut _); } }
    }
}

#[cfg(windows)]
const WS_CHILD: u32 = 0x4000_0000;
#[cfg(windows)]
const WS_CLIPSIBLINGS: u32 = 0x0400_0000;
#[cfg(windows)]
const SW_HIDE: i32 = 0;
#[cfg(windows)]
const SW_SHOW: i32 = 5;
#[cfg(windows)]
const SWP_NOZORDER: u32 = 0x0004;
#[cfg(windows)]
const SWP_NOACTIVATE: u32 = 0x0010;

#[cfg(windows)]
#[link(name = "user32")]
unsafe extern "system" {
    fn CreateWindowExW(ex_style: u32, class: *const u16, title: *const u16, style: u32,
        x: i32, y: i32, width: i32, height: i32, parent: *mut std::ffi::c_void,
        menu: *mut std::ffi::c_void, instance: *mut std::ffi::c_void, param: *mut std::ffi::c_void,
    ) -> *mut std::ffi::c_void;
    fn SetWindowPos(hwnd: *mut std::ffi::c_void, after: *mut std::ffi::c_void,
        x: i32, y: i32, width: i32, height: i32, flags: u32) -> i32;
    fn ShowWindow(hwnd: *mut std::ffi::c_void, command: i32) -> i32;
    fn DestroyWindow(hwnd: *mut std::ffi::c_void) -> i32;
}

#[cfg(windows)]
#[link(name = "kernel32")]
unsafe extern "system" {
    fn GetModuleHandleW(name: *const u16) -> *mut std::ffi::c_void;
}

#[derive(Clone)]
struct MpvTrack {
    id: i64,
    label: String,
    selected: bool,
    subtitle: bool,
}

struct Mpv {
    child: Option<Child>,
    ipc: Option<PathBuf>,
    path: Option<PathBuf>,
    error: Option<String>,
    paused: bool,
    ended: bool,
    position: f64,
    duration: f64,
    volume: f32,
    volume_max: f32,
    speed: f64,
    stable_volume: bool,
    annotations: bool,
    tracks: Vec<MpvTrack>,
    tracks_dirty: bool,
    eof_checked: bool,
    last_poll: Instant,
    window_id: Option<usize>,
}

impl Default for Mpv {
    fn default() -> Self {
        Self {
            child: None, ipc: None, path: None, error: None, paused: true, ended: false,
            position: 0.0, duration: 0.0, volume: 80.0, volume_max: 100.0, speed: 1.0,
            stable_volume: false, annotations: true, tracks: Vec::new(), tracks_dirty: true, eof_checked: false,
            last_poll: Instant::now(), window_id: None,
        }
    }
}

impl Mpv {
    fn executable() -> Option<PathBuf> {
        let exe_dir = std::env::current_exe().ok()?.parent()?.to_path_buf();
        let name = if cfg!(windows) { "mpv.exe" } else { "mpv" };
        let mut candidates = vec![exe_dir.join("runtime").join(name), exe_dir.join(name)];
        #[cfg(target_os = "macos")]
        candidates.extend([PathBuf::from("/opt/homebrew/bin/mpv"), PathBuf::from("/usr/local/bin/mpv"), PathBuf::from("/opt/local/bin/mpv")]);
        for candidate in candidates {
            if candidate.is_file() { return Some(candidate); }
        }
        std::env::var_os("PATH").and_then(|paths| std::env::split_paths(&paths).map(|p| p.join(name)).find(|p| p.is_file()))
    }

    fn start(&mut self) -> Result<(), String> {
        if self.child.as_mut().and_then(|c| c.try_wait().ok()).flatten().is_none() && self.child.is_some() { return Ok(()); }
        let program = Self::executable().ok_or_else(|| {
            if cfg!(target_os = "macos") {
                "mpv was not found. Install the playback engine with `brew install mpv`, then reopen Lumen.".to_owned()
            } else {
                "mpv runtime not found. Put mpv.exe and its complete portable runtime in the app's runtime folder.".to_owned()
            }
        })?;
        let data = data_dir();
        fs::create_dir_all(&data).map_err(|e| format!("Cannot create player data folder: {e}"))?;
        #[cfg(windows)]
        let ipc = PathBuf::from(format!(r"\\.\pipe\lumen-mpv-{}", std::process::id()));
        #[cfg(not(windows))]
        let ipc = { let p = data.join("mpv.sock"); let _ = fs::remove_file(&p); p };
        let mut command = Command::new(&program);
        command.arg(format!("--input-ipc-server={}", ipc.display()))
            .arg(format!("--volume-max={}", self.volume_max))
            .arg(format!("--speed={}", self.speed))
            .arg(format!("--sid={}", if self.annotations { "auto" } else { "no" }))
            .args(["--idle=yes", "--keep-open=yes", "--no-terminal", "--title=Lumen Player"]);
        if self.stable_volume { command.arg("--af=@lumen:acompressor=threshold=0.12:ratio=3"); }
        command
            .stdin(Stdio::null()).stdout(Stdio::null()).stderr(Stdio::null());
        #[cfg(windows)]
        if let Some(window_id) = self.window_id { command.arg(format!("--wid={window_id}")); }
        if let Some(parent) = program.parent() { command.current_dir(parent); }
        #[cfg(windows)]
        command.creation_flags(0x0800_0000);
        self.child = Some(command.spawn().map_err(|e| format!("Could not start mpv: {e}"))?);
        self.ipc = Some(ipc);
        std::thread::sleep(Duration::from_millis(25));
        Ok(())
    }

    fn connect(&self) -> Option<Box<dyn ReadWrite>> {
        let path = self.ipc.as_ref()?;
        for _ in 0..20 {
            #[cfg(unix)]
            if let Ok(stream) = std::os::unix::net::UnixStream::connect(path) {
                let _ = stream.set_read_timeout(Some(Duration::from_millis(100)));
                return Some(Box::new(stream));
            }
            #[cfg(windows)]
            if let Ok(stream) = fs::OpenOptions::new().read(true).write(true).open(path) {
                return Some(Box::new(stream));
            }
            #[cfg(not(any(unix, windows)))]
            { let _ = path; return None; }
            std::thread::sleep(Duration::from_millis(10));
        }
        None
    }

    fn request(&mut self, command: Value) -> Option<Value> {
        let mut stream = self.connect()?;
        serde_json::to_writer(&mut stream, &command).ok()?;
        stream.write_all(b"\n").ok()?;
        stream.flush().ok()?;
        let mut line = String::new();
        BufReader::new(stream).read_line(&mut line).ok()?;
        serde_json::from_str(&line).ok()
    }

    fn command(&mut self, args: Vec<Value>) {
        if let Err(e) = self.start() { self.error = Some(e); return; }
        match self.request(json!({"command": args, "request_id": 1})) {
            Some(response) if response.get("error").and_then(Value::as_str).map(|e| e != "success").unwrap_or(false) => {
                self.error = response.get("error").and_then(Value::as_str).map(str::to_owned);
            }
            None => self.error = Some("Could not communicate with the mpv playback engine.".into()),
            _ => {}
        }
    }

    fn open(&mut self, path: PathBuf) {
        self.error = None;
        self.command(vec![json!("loadfile"), json!(path.to_string_lossy()), json!("replace")]);
        self.path = Some(path); self.paused = false; self.ended = false; self.eof_checked = false; self.tracks_dirty = true; self.tracks.clear(); self.position = 0.0; self.duration = 0.0;
    }

    fn toggle(&mut self) { self.command(vec![json!("cycle"), json!("pause")]); self.paused = !self.paused; }
    fn seek(&mut self, seconds: f64) { self.command(vec![json!("seek"), json!(seconds), json!("absolute")]); self.position = seconds.max(0.0); }
    fn set_volume(&mut self, value: f32) {
        self.volume = value.clamp(0.0, self.volume_max);
        if self.child.is_some() { self.command(vec![json!("set_property"), json!("volume"), json!(self.volume)]); }
    }

    fn set_volume_boost(&mut self, enabled: bool) {
        self.volume_max = if enabled { 130.0 } else { 100.0 };
        if self.child.is_some() { self.command(vec![json!("set_property"), json!("volume-max"), json!(self.volume_max)]); }
        if !enabled { self.set_volume(self.volume.min(100.0)); }
    }

    fn set_speed(&mut self, speed: f64) {
        self.speed = speed.clamp(0.25, 3.0);
        if self.child.is_some() { self.command(vec![json!("set_property"), json!("speed"), json!(self.speed)]); }
    }

    fn set_stable_volume(&mut self, enabled: bool) {
        self.stable_volume = enabled;
        if self.child.is_none() { return; }
        let args = if enabled {
            vec![json!("af"), json!("add"), json!("@lumen:acompressor=threshold=0.12:ratio=3")]
        } else {
            vec![json!("af"), json!("remove"), json!("@lumen")]
        };
        self.command(args);
    }

    fn set_annotations(&mut self, enabled: bool) {
        self.annotations = enabled;
        if self.child.is_some() {
            self.command(vec![json!("set_property"), json!("sid"), json!(if enabled { "auto" } else { "no" })]);
        }
    }

    fn poll(&mut self) {
        if self.child.is_none() || self.path.is_none() || self.last_poll.elapsed() < Duration::from_millis(350) { return; }
        self.last_poll = Instant::now();
        if self.child.as_mut().and_then(|child| child.try_wait().ok()).flatten().is_some() {
            self.child = None; self.ipc = None; return;
        }
        if let Some(response) = self.request(json!({"command": ["get_property", "time-pos"], "request_id": 20})) {
            if let Some(position) = response.get("data").and_then(Value::as_f64()) { self.position = position.max(0.0); }
        }
        if let Some(response) = self.request(json!({"command": ["get_property", "duration"], "request_id": 21})) {
            if let Some(duration) = response.get("data").and_then(Value::as_f64()) { self.duration = duration.max(0.0); }
        }
        if self.tracks_dirty {
            if let Some(response) = self.request(json!({"command": ["get_property", "track-list"], "request_id": 22})) {
                if let Some(list) = response.get("data").and_then(Value::as_array) {
                    self.tracks = list.iter().filter_map(|item| {
                        let kind = item.get("type")?.as_str()?;
                        if kind != "audio" && kind != "sub" { return None; }
                        let id = item.get("id")?.as_i64()?;
                        let title = item.get("title").and_then(Value::as_str).unwrap_or("");
                        let lang = item.get("lang").and_then(Value::as_str).unwrap_or("");
                        let base = if title.is_empty() { format!("{} track {id}", if kind == "audio" { "Audio" } else { "Subtitle" }) } else { title.to_owned() };
                        Some(MpvTrack { id, label: if lang.is_empty() { base } else { format!("{base} · {lang}") }, selected: item.get("selected").and_then(Value::as_bool).unwrap_or(false), subtitle: kind == "sub" })
                    }).collect();
                    self.tracks_dirty = false;
                }
            }
        }
        if !self.eof_checked && self.duration > 0.0 && self.position >= self.duration - 0.2 {
            if let Some(response) = self.request(json!({"command": ["get_property", "eof-reached"], "request_id": 23})) {
                if response.get("data").and_then(Value::as_bool).unwrap_or(false) {
                    self.ended = true;
                    self.eof_checked = true;
                }
            }
        }
    }
}

impl Drop for Mpv {
    fn drop(&mut self) { if let Some(child) = self.child.as_mut() { let _ = child.kill(); } }
}

struct LumenApp {
    page: Page,
    saved: Saved,
    config_path: PathBuf,
    mpv: Mpv,
    video: NativeVideo,
    queue: Vec<PathBuf>,
    queue_index: usize,
    library_revision: u64,
    library_filter_revision: u64,
    library_filter_query: String,
    library_filter: Vec<usize>,
    search: String,
    settings_open: bool,
    updater: Updater,
    folder_scan: Option<Receiver<Vec<PathBuf>>>,
    last_save: Instant,
}

impl LumenApp {
    fn new(cc: &eframe::CreationContext<'_>) -> Self {
        let mut style = (*cc.egui_ctx.style()).clone();
        style.visuals = egui::Visuals::dark();
        style.spacing.item_spacing = Vec2::new(10.0, 10.0);
        style.visuals.window_corner_radius = egui::CornerRadius::same(14);
        cc.egui_ctx.set_style(style);
        let config_path = data_dir().join("library.json");
        let mut saved: Saved = fs::read(&config_path).ok().and_then(|v| serde_json::from_slice(&v).ok()).unwrap_or_default();
        if saved.language.is_empty() { saved.language = "system".into(); }
        if !(0.25..=3.0).contains(&saved.speed) { saved.speed = 1.0; }
        saved.volume = saved.volume.clamp(0.0, if saved.volume_boost { 130.0 } else { 100.0 });
        let queue = saved.library.clone();
        let mut mpv = Mpv::default();
        mpv.volume = saved.volume;
        mpv.speed = saved.speed;
        mpv.volume_max = if saved.volume_boost { 130.0 } else { 100.0 };
        mpv.stable_volume = saved.stable_volume;
        mpv.annotations = saved.annotations;
        let mut app = Self { page: Page::Player, saved, config_path, mpv, video: NativeVideo::default(), queue, queue_index: 0,
            search: String::new(), settings_open: false, updater: Updater::default(), folder_scan: None, library_revision: 0,
            library_filter_revision: u64::MAX, library_filter_query: String::new(), library_filter: Vec::new(), last_save: Instant::now() };
        app.updater.check();
        app
    }

    fn french(&self) -> bool {
        self.saved.language == "fr" || (self.saved.language == "system" && std::env::var("LANG").unwrap_or_default().starts_with("fr"))
    }
    fn tr<'a>(&self, en: &'a str, fr: &'a str) -> &'a str { if self.french() { fr } else { en } }
    fn save(&mut self) {
        self.saved.library = self.queue.clone();
        if let Some(parent) = self.config_path.parent() { let _ = fs::create_dir_all(parent); }
        if let Ok(bytes) = serde_json::to_vec_pretty(&self.saved) {
            let tmp = self.config_path.with_extension("tmp");
            if fs::write(&tmp, bytes).is_ok() {
                #[cfg(windows)]
                if self.config_path.exists() { let _ = fs::remove_file(&self.config_path); }
                let _ = fs::rename(tmp, &self.config_path);
            }
        }
        self.last_save = Instant::now();
    }

    fn add_paths(&mut self, paths: Vec<PathBuf>) {
        let old_len = self.queue.len();
        let mut known: HashSet<PathBuf> = self.queue.iter().cloned().collect();
        for path in paths {
            if path.is_file() && is_media(&path) && known.insert(path.clone()) { self.queue.push(path); }
        }
        if self.queue_index >= self.queue.len() { self.queue_index = self.queue.len().saturating_sub(1); }
        if self.queue.len() != old_len { self.library_revision = self.library_revision.wrapping_add(1); }
        self.save();
    }
    fn open_dialog(&mut self) {
        if let Some(paths) = rfd::FileDialog::new().add_filter("Media", MEDIA_EXT).pick_files() {
            self.add_paths(paths.clone());
            if let Some(path) = paths.first() { self.play_path(path.clone()); }
        }
    }
    fn play_path(&mut self, path: PathBuf) {
        self.add_paths(vec![path.clone()]);
        if let Some(i) = self.queue.iter().position(|p| p == &path) { self.queue_index = i; }
        self.mpv.open(path);
        self.mpv.set_volume(self.saved.volume);
        self.saved.volume = self.mpv.volume;
    }
    fn next(&mut self, backwards: bool) {
        if self.queue.is_empty() { return; }
        self.queue_index = if backwards { self.queue_index.saturating_sub(1) }
        else if self.saved.shuffle && self.queue.len() > 1 {
            let pick = SystemTime::now().duration_since(UNIX_EPOCH).unwrap_or_default().subsec_nanos() as usize % (self.queue.len() - 1);
            if pick >= self.queue_index { pick + 1 } else { pick }
        }
        else if self.queue_index + 1 < self.queue.len() { self.queue_index + 1 }
        else if self.saved.repeat { 0 } else { return; };
        self.play_path(self.queue[self.queue_index].clone());
    }
    fn icon_button(ui: &mut egui::Ui, label: &str, tooltip: &str, size: f32, primary: bool) -> egui::Response {
        let text = RichText::new(label).size(if primary { 22.0 } else { 17.0 }).color(TEXT);
        let mut button = egui::Button::new(text).corner_radius(egui::CornerRadius::same((size / 2.0) as u8));
        if primary { button = button.fill(ACCENT); }
        let response = ui.add_sized([size, size], button);
        let hover = ui.ctx().animate_value_with_time(
            ui.make_persistent_id(("icon-hover", tooltip)),
            if response.hovered() || response.is_pointer_button_down_on() { 1.0 } else { 0.0 },
            0.12,
        );
        if hover > 0.01 {
            ui.painter().rect_filled(response.rect, egui::CornerRadius::same((size / 2.0) as u8), Color32::from_rgba_unmultiplied(192, 168, 255, (hover * 22.0) as u8));
        }
        response.on_hover_text(tooltip)
    }
    fn topbar(&mut self, ui: &mut egui::Ui) {
        ui.horizontal(|ui| {
            let title = match self.page { Page::Player => self.tr("Now Playing", "En lecture"), Page::Library => self.tr("Your Library", "Votre bibliothèque") };
            ui.label(RichText::new(title).size(23.0).strong().color(TEXT));
            ui.with_layout(Layout::right_to_left(Align::Center), |ui| {
                if Self::icon_button(ui, "⚙", "Settings", 40.0, false).clicked() { self.settings_open = true; }
                if Self::icon_button(ui, "＋", "Open media", 40.0, false).clicked() { self.open_dialog(); }
                ui.add_space(8.0); ui.label(RichText::new("LUMEN  /  MEDIA PLAYER").size(10.0).strong().color(SUB));
            });
        });
    }
    fn sidebar(&mut self, ui: &mut egui::Ui) {
        ui.vertical_centered(|ui| {
            ui.add_space(18.0); ui.label(RichText::new("▷").size(34.0).strong().color(ACCENT));
            ui.label(RichText::new("L U M E N").size(9.0).strong().color(SUB)); ui.add_space(30.0);
            for (page, icon, text) in [(Page::Player, "▶", self.tr("Player", "Lecteur")), (Page::Library, "▦", self.tr("Library", "Bibliothèque"))] {
                let selected = self.page == page;
                let fill = if selected { Color32::from_rgb(47, 37, 77) } else { SIDE };
                let color = if selected { Color32::from_rgb(192, 168, 255) } else { SUB };
                let button = egui::Button::new(RichText::new(format!("{icon}\n{text}")).size(11.0).color(color)).fill(fill).stroke(Stroke::NONE).corner_radius(egui::CornerRadius::same(14));
                if ui.add_sized([68.0, 62.0], button).clicked() { self.page = page; }
                ui.add_space(7.0);
            }
        });
    }
    fn player_page(&mut self, ui: &mut egui::Ui, scale: f32) {
        let available = ui.available_size();
        let queue_width = if available.x > 760.0 { 278.0 } else { 0.0 };
        ui.horizontal_top(|ui| {
            ui.allocate_ui_with_layout(Vec2::new((available.x - queue_width - 14.0).max(280.0), available.y), Layout::top_down(Align::Min), |ui| {
                self.now_playing(ui, scale); ui.add_space(12.0); self.transport(ui);
            });
            if queue_width > 0.0 { ui.add_space(12.0); self.queue_panel(ui, queue_width); }
        });
    }
    fn now_playing(&mut self, ui: &mut egui::Ui, scale: f32) {
        let path = self.mpv.path.clone();
        let media_is_video = path.as_ref().map(|p| !is_audio(p)).unwrap_or(false);
        egui::Frame::new().fill(CARD).stroke(Stroke::new(1.0, BORDER)).corner_radius(egui::CornerRadius::same(20)).inner_margin(20).show(ui, |ui| {
            let width = ui.available_width();
            let height = (ui.available_height() - 112.0).max(210.0).min(440.0);
            let (rect, response) = ui.allocate_exact_size(Vec2::new(width, height), Sense::click());
            self.video.place(rect, scale, media_is_video, &mut self.mpv);
            if !media_is_video {
                let painter = ui.painter_at(rect);
                painter.rect_filled(rect, egui::CornerRadius::same(16), Color32::from_rgb(8, 8, 14));
                let center = rect.center();
                let pulse = ui.ctx().animate_value_with_time(egui::Id::new("music-pulse"), if self.mpv.paused { 0.0 } else { 1.0 }, 0.8);
                for i in (0..7).rev() {
                    let radius = 46.0 + i as f32 * 24.0 + pulse * 4.0;
                    let alpha = 16 + (6 - i) as u8 * 4;
                    painter.circle_filled(center, radius, Color32::from_rgba_unmultiplied(124, 92, 252, alpha));
                }
                painter.circle_filled(center, 47.0 + pulse * 2.0, Color32::from_rgba_unmultiplied(CYAN.r(), CYAN.g(), CYAN.b(), 48));
                painter.circle_filled(center, 47.0, Color32::from_rgb(32, 26, 53));
                painter.text(center, egui::Align2::CENTER_CENTER, "▶", FontId::proportional(38.0), Color32::from_rgb(211, 195, 255));
                if self.saved.ambient {
                    let t = ui.ctx().input(|i| i.time) as f32;
                    let bars = 31;
                    let bar_width = (rect.width() - 100.0) / bars as f32;
                    let baseline = rect.bottom() - 22.0;
                    for i in 0..bars {
                        let phase = t * 2.0 + i as f32 * 0.51;
                        let wave = (phase.sin() * 0.5 + (phase * 0.73).cos() * 0.5).abs();
                        let h = 4.0 + wave * (rect.height() * 0.15).min(34.0);
                        let x = rect.left() + 50.0 + i as f32 * bar_width;
                        painter.rect_filled(egui::Rect::from_min_size(egui::pos2(x, baseline - h), Vec2::new((bar_width * 0.55).max(2.0), h)), egui::CornerRadius::same(2), Color32::from_rgba_unmultiplied(52, 232, 192, 115));
                    }
                    ui.ctx().request_repaint_after(Duration::from_millis(50));
                }
                if path.is_none() { painter.text(egui::pos2(center.x, rect.bottom() - 48.0), egui::Align2::CENTER_CENTER, self.tr("Open a media file to begin", "Ouvrez un fichier média pour commencer"), FontId::proportional(15.0), SUB); }
            }
            if response.hovered() {
                let wheel = ui.ctx().input(|i| i.raw_scroll_delta.y);
                if wheel.abs() > 0.0 {
                    let value = (self.mpv.volume + wheel.signum() * (wheel.abs() / 12.0).max(2.0)).clamp(0.0, self.mpv.volume_max);
                    self.mpv.set_volume(value); self.saved.volume = value;
                }
            }
            if response.double_clicked() { self.toggle_play(); }
            ui.add_space(15.0);
            ui.horizontal(|ui| {
                ui.vertical(|ui| {
                    let title = path.as_ref().and_then(|p| p.file_stem()).and_then(|s| s.to_str()).unwrap_or("Nothing playing");
                    ui.label(RichText::new(title).size(18.0).strong().color(TEXT));
                    ui.label(RichText::new(path.as_ref().map(|p| p.display().to_string()).unwrap_or_else(|| "Your music and videos, in one place".into())).size(11.0).color(SUB));
                });
                ui.with_layout(Layout::right_to_left(Align::Center), |ui| {
                    if Self::icon_button(ui, "＋", "Add files", 38.0, false).clicked() { self.open_dialog(); }
                    if Self::icon_button(ui, "↗", "Open folder", 38.0, false).clicked() { if let Some(folder) = rfd::FileDialog::new().pick_folder() { self.scan_folder(folder); } }
                });
            });
        });
    }
    fn toggle_play(&mut self) {
        if self.mpv.path.is_some() { self.mpv.toggle(); } else if let Some(path) = self.queue.get(self.queue_index).cloned() { self.play_path(path); } else { self.open_dialog(); }
    }
    fn transport(&mut self, ui: &mut egui::Ui) {
        egui::Frame::new().fill(CARD).stroke(Stroke::new(1.0, BORDER)).corner_radius(egui::CornerRadius::same(18)).inner_margin(egui::Margin::symmetric(18, 12)).show(ui, |ui| {
            let max = self.mpv.duration.max(1.0) as f32;
            let mut position = self.mpv.position.clamp(0.0, max as f64) as f32;
            ui.horizontal(|ui| {
                ui.label(RichText::new(time_text(self.mpv.position)).size(11.0).color(SUB));
                let seek = ui.add_sized([ui.available_width() - 108.0, 20.0], egui::Slider::new(&mut position, 0.0..=max).show_value(false));
                if seek.changed() && (seek.drag_stopped() || seek.clicked()) { self.mpv.seek(position as f64); }
                ui.label(RichText::new(time_text(self.mpv.duration)).size(11.0).color(SUB));
            });
            ui.add_space(8.0);
            ui.horizontal_wrapped(|ui| {
                if ui.selectable_label(self.saved.shuffle, "⤨").on_hover_text(self.tr("Shuffle queue", "Lecture aléatoire")).clicked() { self.saved.shuffle = !self.saved.shuffle; }
                if Self::icon_button(ui, "|◀", self.tr("Previous", "Précédent"), 38.0, false).clicked() { self.next(true); }
                if Self::icon_button(ui, if self.mpv.paused { "▶" } else { "Ⅱ" }, self.tr("Play / pause", "Lecture / pause"), 52.0, true).clicked() { self.toggle_play(); }
                if Self::icon_button(ui, "▶|", self.tr("Next", "Suivant"), 38.0, false).clicked() { self.next(false); }
                if ui.selectable_label(self.saved.repeat, "↻").on_hover_text(self.tr("Repeat queue", "Répéter la file")).clicked() { self.saved.repeat = !self.saved.repeat; }
                ui.separator();
                let mut speed = self.mpv.speed;
                egui::ComboBox::from_id_salt("speed").selected_text(format!("{speed}×")).show_ui(ui, |ui| {
                    for rate in [0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 3.0] { ui.selectable_value(&mut speed, rate, format!("{rate}×")); }
                });
                if (speed - self.mpv.speed).abs() > f64::EPSILON { self.mpv.set_speed(speed); self.saved.speed = speed; }
                let tracks = self.mpv.tracks.clone();
                let audio_tracks: Vec<MpvTrack> = tracks.iter().filter(|t| !t.subtitle).cloned().collect();
                let subtitle_tracks: Vec<MpvTrack> = tracks.iter().filter(|t| t.subtitle).cloned().collect();
                if !subtitle_tracks.is_empty() {
                    let original = subtitle_tracks.iter().find(|t| t.selected).map(|t| t.id);
                    let mut selected = original;
                    egui::ComboBox::from_id_salt("subtitle-track").selected_text("CC").show_ui(ui, |ui| {
                        ui.selectable_value(&mut selected, None, self.tr("Subtitles off", "Sous-titres désactivés"));
                        for track in &subtitle_tracks { ui.selectable_value(&mut selected, Some(track.id), &track.label); }
                    });
                    if selected != original { self.mpv.command(vec![json!("set_property"), json!("sid"), selected.map(Value::from).unwrap_or(json!("no"))]); }
                }
                if audio_tracks.len() > 1 {
                    let original = audio_tracks.iter().find(|t| t.selected).map(|t| t.id);
                    let mut selected = original;
                    egui::ComboBox::from_id_salt("audio-track").selected_text("Audio").show_ui(ui, |ui| {
                        for track in &audio_tracks { ui.selectable_value(&mut selected, Some(track.id), &track.label); }
                    });
                    if selected != original { if let Some(id) = selected { self.mpv.command(vec![json!("set_property"), json!("aid"), json!(id)]); } }
                }
                ui.separator();
                if Self::icon_button(ui, if self.mpv.volume <= 0.0 { "×" } else { "◖" }, self.tr("Mute / unmute", "Muet / son"), 36.0, false).clicked() {
                    let v = if self.mpv.volume <= 0.0 { self.saved.volume.max(1.0) } else { self.saved.volume = self.mpv.volume; 0.0 };
                    self.mpv.set_volume(v);
                }
                let mut volume = self.mpv.volume;
                if ui.add_sized([88.0, 18.0], egui::Slider::new(&mut volume, 0.0..=self.mpv.volume_max).show_value(false)).changed() {
                    self.mpv.set_volume(volume); self.saved.volume = volume;
                }
                ui.label(RichText::new(format!("{}%", self.mpv.volume.round() as i32)).size(11.0).color(SUB));
                if Self::icon_button(ui, "□", self.tr("Fullscreen", "Plein écran"), 36.0, false).clicked() { self.mpv.command(vec![json!("cycle"), json!("fullscreen")]); }
            });
            if let Some(error) = &self.mpv.error { ui.add_space(8.0); ui.label(RichText::new(error).color(Color32::from_rgb(255, 140, 150)).size(11.0)); }
        });
    }

    fn queue_panel(&mut self, ui: &mut egui::Ui, width: f32) {
        egui::Frame::new().fill(CARD).stroke(Stroke::new(1.0, BORDER)).corner_radius(egui::CornerRadius::same(20)).inner_margin(14).show(ui, |ui| {
            ui.set_min_width(width - 28.0); ui.set_max_width(width - 28.0);
            ui.horizontal(|ui| {
                ui.vertical(|ui| {
                    ui.label(RichText::new(self.tr("PLAY QUEUE", "FILE DE LECTURE")).size(10.0).strong().color(ACCENT));
                    ui.label(RichText::new(self.tr("Ready when you are", "À vous de choisir")).size(17.0).strong().color(TEXT));
                });
                ui.with_layout(Layout::right_to_left(Align::Center), |ui| { ui.label(RichText::new(format!("{}", self.queue.len())).size(12.0).color(SUB)); });
            });
            ui.add_space(10.0);
            if self.folder_scan.is_some() {
                ui.horizontal(|ui| { ui.spinner(); ui.label(RichText::new(self.tr("Scanning folders…", "Analyse des dossiers…")).size(10.0).color(SUB)); });
            }
            let mut chosen = None;
            let mut remove = None;
            let scroll_height = (ui.available_height() - 48.0).clamp(120.0, 520.0);
            let mut scroll = egui::ScrollArea::vertical().max_height(scroll_height).auto_shrink([false, false]);
            if self.queue.is_empty() {
                scroll.show(ui, |ui| {
                    ui.add_space(20.0);
                    ui.label(RichText::new(self.tr("Your queue is empty. Add music or video to get started.", "Votre file est vide. Ajoutez de la musique ou une vidéo pour commencer.")).size(12.0).color(SUB));
                });
            } else {
                scroll.show_rows(ui, 54.0, self.queue.len(), |ui, rows| {
                    for index in rows {
                        let path = &self.queue[index];
                        let selected = self.mpv.path.as_ref() == Some(path);
                        let title = path.file_stem().and_then(|s| s.to_str()).unwrap_or("Media");
                        let type_icon = if is_audio(path) { "♫" } else { "▣" };
                        let fill = if selected { Color32::from_rgb(43, 34, 67) } else { CARD2 };
                        let text_color = if selected { Color32::from_rgb(211, 194, 255) } else { TEXT };
                        egui::Frame::new().fill(fill).corner_radius(egui::CornerRadius::same(11)).inner_margin(8).show(ui, |ui| {
                            ui.horizontal(|ui| {
                                ui.label(RichText::new(type_icon).size(19.0).color(if selected { ACCENT } else { CYAN }));
                                ui.vertical(|ui| {
                                    ui.add(egui::Label::new(RichText::new(title).size(12.0).strong().color(text_color)).truncate());
                                    ui.label(RichText::new(path.extension().and_then(|s| s.to_str()).unwrap_or("MEDIA").to_uppercase()).size(9.0).color(SUB));
                                });
                                ui.with_layout(Layout::right_to_left(Align::Center), |ui| {
                                    if ui.small_button("×").on_hover_text(self.tr("Remove from queue", "Retirer de la file")).clicked() { remove = Some(index); }
                                    if ui.small_button(if selected { "♫" } else { "▶" }).on_hover_text(self.tr("Play this item", "Lire cet élément")).clicked() { chosen = Some(path.to_path_buf()); }
                                });
                            });
                        });
                    }
                });
            }
            if let Some(index) = remove {
                self.queue.remove(index);
                self.library_revision = self.library_revision.wrapping_add(1);
                if self.queue.is_empty() { self.queue_index = 0; }
                else if index < self.queue_index { self.queue_index -= 1; }
                else if self.queue_index >= self.queue.len() { self.queue_index = self.queue.len() - 1; }
                self.save();
            }
            if let Some(path) = chosen { self.play_path(path); }
            if ui.add_sized([width - 54.0, 34.0], egui::Button::new(RichText::new(format!("＋  {}", self.tr("Add media", "Ajouter des médias"))).color(TEXT)).fill(CARD2)).clicked() { self.open_dialog(); }
        });
    }

    fn library_page(&mut self, ui: &mut egui::Ui) {
        let search_hint = self.tr("Search your library", "Rechercher dans la bibliothèque");
        ui.horizontal(|ui| {
            ui.add_sized([ui.available_width() - 230.0, 36.0], egui::TextEdit::singleline(&mut self.search).hint_text(search_hint));
            if ui.button(self.tr("Add files", "Ajouter des fichiers")).clicked() { self.open_dialog(); }
            if ui.button(self.tr("Add folder", "Ajouter un dossier")).clicked() { if let Some(folder) = rfd::FileDialog::new().pick_folder() { self.scan_folder(folder); } }
        });
        if self.folder_scan.is_some() {
            ui.horizontal(|ui| { ui.spinner(); ui.label(RichText::new(self.tr("Scanning folders in the background…", "Analyse des dossiers en arrière-plan…")).size(11.0).color(SUB)); });
        }
        ui.add_space(10.0);
        let query = self.search.trim().to_lowercase();
        if query != self.library_filter_query || self.library_filter_revision != self.library_revision {
            self.library_filter_query = query.clone();
            self.library_filter_revision = self.library_revision;
            self.library_filter = self.queue.iter().enumerate().filter_map(|(index, path)| {
                let matches = query.is_empty() || path.file_name().and_then(|name| name.to_str()).unwrap_or("").to_lowercase().contains(&query);
                matches.then_some(index)
            }).collect();
        }
        let filtered_count = self.library_filter.len();
        ui.label(RichText::new(format!("{} {}", filtered_count, self.tr("items in your library", "éléments dans la bibliothèque"))).color(SUB));
        let mut chosen = None;
        egui::ScrollArea::vertical().show_rows(ui, 62.0, filtered_count, |ui, rows| {
            for row in rows {
                let path = &self.queue[self.library_filter[row]];
                let name = path.file_stem().and_then(|s| s.to_str()).unwrap_or("Media");
                let ext = path.extension().and_then(|s| s.to_str()).unwrap_or("").to_uppercase();
                let location = path.parent().unwrap_or(Path::new("")).display().to_string();
                let response = egui::Frame::new().fill(CARD).stroke(Stroke::new(1.0, BORDER)).corner_radius(egui::CornerRadius::same(12)).inner_margin(12).show(ui, |ui| {
                    ui.horizontal(|ui| {
                        ui.label(RichText::new(if is_audio(path) { "♫" } else { "▶" }).size(22.0).color(ACCENT));
                        ui.vertical(|ui| {
                            ui.add(egui::Label::new(RichText::new(name).strong().color(TEXT)).truncate());
                            ui.add(egui::Label::new(RichText::new(format!("{ext}   ·   {location}")).size(10.0).color(SUB)).truncate());
                        });
                        ui.with_layout(Layout::right_to_left(Align::Center), |ui| {
                            if ui.button(self.tr("Play", "Lire")).clicked() { chosen = Some(path.to_path_buf()); }
                        });
                    });
                });
                if response.response.clicked() { chosen = Some(path.to_path_buf()); }
            }
        });
        if let Some(path) = chosen { self.play_path(path); }
    }

    fn settings_popup(&mut self, ctx: &egui::Context) {
        if !self.settings_open { return; }
        let mut open = self.settings_open;
        let mut changed = false;
        let mut close_clicked = false;
        let title = self.tr("Lumen settings", "Réglages de Lumen");
        let subtitle = self.tr("Make the player yours", "Personnalisez votre lecteur");
        let preferences = self.tr("PREFERENCES", "PRÉFÉRENCES");
        let language_label = self.tr("Language", "Langue");
        let system_language = self.tr("System default", "Langue du système");
        let volume_label = self.tr("Default volume", "Volume par défaut");
        let playback_label = self.tr("PLAYBACK", "LECTURE");
        let repeat_label = self.tr("Repeat queue", "Répéter la file");
        let shuffle_label = self.tr("Shuffle", "Aléatoire");
        let ambient_label = self.tr("Ambient visuals", "Visuels ambiants");
        let boost_label = self.tr("Volume boost", "Amplification du volume");
        let stable_label = self.tr("Stable volume", "Volume régulier");
        let annotations_label = self.tr("Subtitles and annotations", "Sous-titres et annotations");
        let engine_label = self.tr("Playback engine", "Moteur de lecture");
        let engine_hint = self.tr("Lumen uses mpv with FFmpeg. Windows portable builds need the runtime folder; on macOS install mpv with Homebrew.", "Lumen utilise mpv avec FFmpeg. Sous Windows, le dossier runtime est requis; sur macOS, installez mpv avec Homebrew.");
        let done_label = self.tr("Done", "Terminé");
        let shortcut_hint = self.tr("Space: play · arrows: seek/volume · F: fullscreen", "Espace : lire · flèches : recherche/volume · F : plein écran");
        egui::Window::new(title)
            .id(egui::Id::new("settings-popup"))
            .anchor(egui::Align2::CENTER_CENTER, Vec2::ZERO)
            .default_width(500.0)
            .resizable(false)
            .collapsible(false)
            .open(&mut open)
            .frame(egui::Frame::new().fill(CARD).stroke(Stroke::new(1.0, BORDER)).corner_radius(egui::CornerRadius::same(20)).inner_margin(22))
            .show(ctx, |ui| {
                ui.set_min_width(450.0);
                ui.label(RichText::new(subtitle).size(13.0).color(SUB));
                ui.add_space(14.0);
                ui.label(RichText::new(preferences).size(10.0).strong().color(ACCENT));
                ui.horizontal(|ui| {
                    ui.label(language_label);
                    let selected_language = match self.saved.language.as_str() { "fr" => "Français", "en" => "English", _ => system_language };
                    egui::ComboBox::from_id_salt("language").selected_text(selected_language).show_ui(ui, |ui| {
                        changed |= ui.selectable_value(&mut self.saved.language, "system".to_owned(), system_language).changed();
                        changed |= ui.selectable_value(&mut self.saved.language, "en".to_owned(), "English").changed();
                        changed |= ui.selectable_value(&mut self.saved.language, "fr".to_owned(), "Français").changed();
                    });
                });
                ui.horizontal(|ui| {
                    ui.label(volume_label);
                    let maximum = self.mpv.volume_max;
                    if ui.add(egui::Slider::new(&mut self.saved.volume, 0.0..=maximum).suffix("%")).changed() {
                        self.mpv.set_volume(self.saved.volume); changed = true;
                    }
                });
                ui.add_space(10.0);
                ui.label(RichText::new(playback_label).size(10.0).strong().color(ACCENT));
                ui.horizontal_wrapped(|ui| {
                    let response = ui.checkbox(&mut self.saved.repeat, repeat_label); changed |= response.changed();
                    let response = ui.checkbox(&mut self.saved.shuffle, shuffle_label); changed |= response.changed();
                    let response = ui.checkbox(&mut self.saved.ambient, ambient_label); changed |= response.changed();
                });
                ui.horizontal_wrapped(|ui| {
                    let response = ui.checkbox(&mut self.saved.volume_boost, boost_label);
                    if response.changed() {
                        self.mpv.set_volume_boost(self.saved.volume_boost);
                        self.saved.volume = self.mpv.volume;
                        changed = true;
                    }
                    let response = ui.checkbox(&mut self.saved.stable_volume, stable_label);
                    if response.changed() { self.mpv.set_stable_volume(self.saved.stable_volume); changed = true; }
                });
                let response = ui.checkbox(&mut self.saved.annotations, annotations_label);
                if response.changed() { self.mpv.set_annotations(self.saved.annotations); changed = true; }
                ui.add_space(10.0);
                egui::Frame::new().fill(CARD2).corner_radius(egui::CornerRadius::same(12)).inner_margin(12).show(ui, |ui| {
                    ui.label(RichText::new(engine_label).strong().color(TEXT));
                    ui.label(RichText::new(engine_hint).size(11.0).color(SUB));
                });
                ui.add_space(12.0);
                ui.label(RichText::new(self.tr("SOFTWARE UPDATES", "MISES À JOUR")).size(10.0).strong().color(ACCENT));
                let mut check_updates = false;
                let mut download_update = None;
                let mut reveal_update = None;
                ui.horizontal_wrapped(|ui| {
                    match &self.updater.status {
                        UpdateStatus::Idle => { ui.label(RichText::new(self.tr("Check whether a newer Lumen build is available.", "Vérifiez si une nouvelle version de Lumen est disponible.")).size(11.0).color(SUB)); }
                        UpdateStatus::Checking => { ui.spinner(); ui.label(RichText::new(self.tr("Checking GitHub for updates…", "Recherche de mises à jour sur GitHub…")).size(11.0).color(SUB)); }
                        UpdateStatus::Current(version) => { ui.label(RichText::new(format!("{} · v{version}", self.tr("You have the latest version", "Vous avez la dernière version"))).size(11.0).color(CYAN)); }
                        UpdateStatus::Available(release) => {
                            ui.label(RichText::new(format!("{} · v{}", self.tr("Update available", "Mise à jour disponible"), release.version)).strong().color(TEXT));
                            if ui.button(self.tr("Download update", "Télécharger la mise à jour")).clicked() { download_update = Some((*release).clone()); }
                            ui.hyperlink_to(self.tr("Release notes", "Notes de version"), release.page_url.as_str());
                        }
                        UpdateStatus::Downloading(release) => { ui.spinner(); ui.label(RichText::new(format!("{} v{}…", self.tr("Downloading", "Téléchargement de"), release.version)).size(11.0).color(SUB)); }
                        UpdateStatus::Downloaded { release, file } => {
                            ui.label(RichText::new(format!("{} v{}", self.tr("Downloaded", "Téléchargée"), release.version)).strong().color(CYAN));
                            if ui.button(self.tr("Show download", "Afficher le fichier")).clicked() { reveal_update = Some(file.to_path_buf()); }
                        }
                        UpdateStatus::Error(error) => { ui.label(RichText::new(error).size(11.0).color(Color32::from_rgb(255, 140, 150))); }
                    }
                    if matches!(&self.updater.status, UpdateStatus::Idle | UpdateStatus::Current(_) | UpdateStatus::Error(_))
                        && ui.button(self.tr("Check for updates", "Vérifier les mises à jour")).clicked() { check_updates = true; }
                });
                if check_updates { self.updater.check(); }
                if let Some(release) = download_update { self.updater.download(release); }
                if let Some(file) = reveal_update {
                    if let Err(error) = update::reveal_file(&file) { self.updater.status = UpdateStatus::Error(error); }
                }
                if matches!(&self.updater.status, UpdateStatus::Downloaded { .. }) {
                    ui.label(RichText::new(self.tr("Close Lumen, extract the ZIP, and replace the existing app files.", "Fermez Lumen, décompressez le ZIP et remplacez les fichiers de l’application.")).size(10.0).color(SUB));
                }
                ui.add_space(8.0);
                ui.with_layout(Layout::right_to_left(Align::Center), |ui| {
                    if ui.button(done_label).clicked() { close_clicked = true; }
                    ui.label(RichText::new(shortcut_hint).size(10.0).color(SUB));
                });
            });
        self.settings_open = open && !close_clicked;
        if changed { self.save(); }
    }

    fn scan_folder(&mut self, folder: PathBuf) {
        if self.folder_scan.is_some() { return; }
        let (sender, receiver) = mpsc::channel();
        self.folder_scan = Some(receiver);
        std::thread::spawn(move || {
            let mut stack = vec![folder];
            let mut found = Vec::new();
            while let Some(directory) = stack.pop() {
                let Ok(entries) = fs::read_dir(directory) else { continue };
                for entry in entries.flatten() {
                    let path = entry.path();
                    if entry.file_type().map(|kind| kind.is_dir()).unwrap_or(false) { stack.push(path); }
                    else if is_media(&path) { found.push(path); }
                }
            }
            let _ = sender.send(found);
        });
    }

    fn poll_folder_scan(&mut self) {
        let result = self.folder_scan.as_ref().map(|receiver| receiver.try_recv());
        match result {
            Some(Ok(paths)) => { self.folder_scan = None; self.add_paths(paths); }
            Some(Err(TryRecvError::Disconnected)) => { self.folder_scan = None; }
            Some(Err(TryRecvError::Empty)) | None => {}
        }
    }
}

impl eframe::App for LumenApp {
    fn update(&mut self, ctx: &egui::Context, frame: &mut eframe::Frame) {
        let current_zoom = ctx.zoom_factor();
        let window_size = ctx.input(|input| input.viewport().inner_rect.map(|rect| rect.size()))
            .unwrap_or_else(|| ctx.available_rect().size());
        let unzoomed_size = window_size * current_zoom;
        let responsive_zoom = (unzoomed_size.x / 1280.0).min(unzoomed_size.y / 800.0).clamp(0.75, 1.15);
        if (responsive_zoom - current_zoom).abs() > 0.015 { ctx.set_zoom_factor(responsive_zoom); }
        #[cfg(windows)]
        if let Ok(handle) = frame.window_handle() { self.video.ensure(handle.as_raw()); }
        self.mpv.window_id = self.video.window_id();
        self.updater.poll();
        self.poll_folder_scan();
        self.mpv.poll();
        if self.mpv.ended { self.mpv.ended = false; self.next(false); }
        let dropped = ctx.input(|i| i.raw.dropped_files.iter().filter_map(|f| f.path.clone()).collect::<Vec<_>>());
        if !dropped.is_empty() {
            self.add_paths(dropped.clone());
            if self.mpv.path.is_none() { if let Some(path) = dropped.first() { self.play_path(path.clone()); } }
        }
        let text_input_active = ctx.wants_keyboard_input() || self.settings_open;
        ctx.input(|i| {
            if !text_input_active {
                if i.key_pressed(egui::Key::Space) { self.toggle_play(); }
                if i.key_pressed(egui::Key::ArrowRight) { self.mpv.seek(self.mpv.position + 10.0); }
                if i.key_pressed(egui::Key::ArrowLeft) { self.mpv.seek((self.mpv.position - 10.0).max(0.0)); }
                if i.key_pressed(egui::Key::ArrowUp) { self.mpv.set_volume(self.mpv.volume + 5.0); self.saved.volume = self.mpv.volume; }
                if i.key_pressed(egui::Key::ArrowDown) { self.mpv.set_volume(self.mpv.volume - 5.0); self.saved.volume = self.mpv.volume; }
                if i.key_pressed(egui::Key::F) { self.mpv.command(vec![json!("cycle"), json!("fullscreen")]); }
            }
            if i.modifiers.command && i.key_pressed(egui::Key::O) { self.open_dialog(); }
        });
        if self.page != Page::Player { self.video.hide(); }
        if self.last_save.elapsed() > Duration::from_secs(8) { self.save(); }
        egui::SidePanel::left("sidebar").exact_width(86.0).frame(egui::Frame::new().fill(SIDE).inner_margin(8)).show(ctx, |ui| self.sidebar(ui));
        egui::CentralPanel::default().frame(egui::Frame::new().fill(BG).inner_margin(egui::Margin::symmetric(24, 18))).show(ctx, |ui| {
            self.topbar(ui); ui.add_space(18.0);
            match self.page { Page::Player => self.player_page(ui, ctx.pixels_per_point()), Page::Library => self.library_page(ui) }
        });
        self.settings_popup(ctx);
        ctx.request_repaint_after(Duration::from_millis(80));
    }
    fn on_exit(&mut self, _gl: Option<&eframe::glow::Context>) { self.save(); }
}

fn data_dir() -> PathBuf {
    #[cfg(windows)]
    let root = std::env::var_os("APPDATA").map(PathBuf::from).unwrap_or_else(|| std::env::current_dir().unwrap_or_default());
    #[cfg(not(windows))]
    let root = std::env::var_os("XDG_CONFIG_HOME").map(PathBuf::from).unwrap_or_else(|| std::env::var_os("HOME").map(PathBuf::from).unwrap_or_default().join(".config"));
    root.join("Lumen")
}
fn is_media(path: &Path) -> bool { path.extension().and_then(|e| e.to_str()).map(|e| MEDIA_EXT.contains(&e.to_ascii_lowercase().as_str())).unwrap_or(false) }
fn is_audio(path: &Path) -> bool { path.extension().and_then(|e| e.to_str()).map(|e| ["mp3", "flac", "wav", "ogg", "opus", "m4a", "aac", "wma", "aiff", "ape"].contains(&e.to_ascii_lowercase().as_str())).unwrap_or(false) }
fn time_text(seconds: f64) -> String {
    let s = seconds.max(0.0) as u64; let h = s / 3600; let m = (s % 3600) / 60; let sec = s % 60;
    if h > 0 { format!("{h}:{m:02}:{sec:02}") } else { format!("{m}:{sec:02}") }
}
fn app_icon() -> Option<egui::IconData> {
    let image = image::load_from_memory(include_bytes!("../../icon.png")).ok()?.to_rgba8();
    let (width, height) = image.dimensions();
    Some(egui::IconData { rgba: image.into_raw(), width, height })
}

fn main() -> eframe::Result {
    let mut viewport = egui::ViewportBuilder::default().with_title("Lumen Player").with_inner_size([1280.0, 800.0]).with_min_inner_size([760.0, 540.0]);
    if let Some(icon) = app_icon() { viewport = viewport.with_icon(icon); }
    let options = eframe::NativeOptions { viewport, ..Default::default() };
    eframe::run_native("Lumen Player", options, Box::new(|cc| Ok(Box::new(LumenApp::new(cc)))))
}

#[cfg(test)]
mod tests {
    use super::{is_audio, is_media, time_text, Saved};
    use std::path::Path;

    #[test]
    fn media_extension_checks_are_case_insensitive() {
        assert!(is_media(Path::new("clip.MKV")));
        assert!(is_media(Path::new("song.flac")));
        assert!(!is_media(Path::new("notes.txt")));
    }

    #[test]
    fn identifies_audio_separately_from_video() {
        assert!(is_audio(Path::new("song.MP3")));
        assert!(!is_audio(Path::new("movie.mp4")));
    }

    #[test]
    fn formats_elapsed_time_with_hours_when_needed() {
        assert_eq!(time_text(65.0), "1:05");
        assert_eq!(time_text(3661.0), "1:01:01");
    }

    #[test]
    fn older_settings_files_keep_defaults_for_new_options() {
        let saved: Saved = serde_json::from_str(r#"{"language":"en","library":[],"volume":0.0}"#).unwrap();
        assert_eq!(saved.speed, 1.0);
        assert!(!saved.repeat);
        assert!(!saved.shuffle);
        assert!(saved.annotations);
        assert_eq!(saved.volume, 0.0);
    }
}
