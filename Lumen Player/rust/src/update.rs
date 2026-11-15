use semver::Version;
use serde_json::Value;
use std::path::PathBuf;
use std::process::Command;
use std::sync::mpsc::{self, Receiver, TryRecvError};
#[cfg(windows)]
use std::os::windows::process::CommandExt;

const LATEST_RELEASE_API: &str = "https://api.github.com/repos/Makerxm800/Lumen/releases/latest";

#[derive(Clone)]
pub(crate) struct UpdateRelease {
    pub version: String,
    pub page_url: String,
    pub asset_name: String,
    asset_url: String,
}

pub(crate) enum UpdateStatus {
    Idle,
    Checking,
    Current(String),
    Available(UpdateRelease),
    Downloading(UpdateRelease),
    Downloaded { release: UpdateRelease, file: PathBuf },
    Error(String),
}

enum UpdateMessage {
    Checked(Result<Option<UpdateRelease>, String>),
    Downloaded(Result<PathBuf, String>),
}

pub(crate) struct Updater {
    pub status: UpdateStatus,
    receiver: Option<Receiver<UpdateMessage>>,
}

impl Default for Updater {
    fn default() -> Self {
        Self { status: UpdateStatus::Idle, receiver: None }
    }
}

impl Updater {
    pub fn check(&mut self) {
        let (tx, rx) = mpsc::channel();
        self.receiver = Some(rx);
        self.status = UpdateStatus::Checking;
        std::thread::spawn(move || {
            let result = fetch_latest_release();
            let _ = tx.send(UpdateMessage::Checked(result));
        });
    }

    pub fn download(&mut self, release: UpdateRelease) {
        let (tx, rx) = mpsc::channel();
        self.receiver = Some(rx);
        self.status = UpdateStatus::Downloading(release.clone());
        std::thread::spawn(move || {
            let result = download_release(&release);
            let _ = tx.send(UpdateMessage::Downloaded(result));
        });
    }

    pub fn poll(&mut self) {
        let received = self.receiver.as_ref().map(|receiver| receiver.try_recv());
        match received {
            Some(Ok(UpdateMessage::Checked(Ok(Some(release))))) => {
                self.receiver = None;
                self.status = UpdateStatus::Available(release);
            }
            Some(Ok(UpdateMessage::Checked(Ok(None)))) => {
                self.receiver = None;
                self.status = UpdateStatus::Current(env!("CARGO_PKG_VERSION").to_owned());
            }
            Some(Ok(UpdateMessage::Checked(Err(error)))) => {
                self.receiver = None;
                self.status = UpdateStatus::Error(error);
            }
            Some(Ok(UpdateMessage::Downloaded(Ok(file)))) => {
                let release = match &self.status {
                    UpdateStatus::Downloading(release) => (*release).clone(),
                    _ => return,
                };
                self.receiver = None;
                self.status = UpdateStatus::Downloaded { release, file };
            }
            Some(Ok(UpdateMessage::Downloaded(Err(error)))) => {
                self.receiver = None;
                self.status = UpdateStatus::Error(error);
            }
            Some(Err(TryRecvError::Disconnected)) => {
                self.receiver = None;
                self.status = UpdateStatus::Error("The update task stopped unexpectedly.".into());
            }
            Some(Err(TryRecvError::Empty)) | None => {}
        }
    }
}

fn platform_asset() -> Option<&'static str> {
    #[cfg(target_os = "windows")]
    { Some("Lumen-Windows-x64.zip") }
    #[cfg(all(target_os = "macos", target_arch = "aarch64"))]
    { Some("Lumen-macOS-arm64.zip") }
    #[cfg(all(target_os = "macos", target_arch = "x86_64"))]
    { Some("Lumen-macOS-x86_64.zip") }
    #[cfg(not(any(target_os = "windows", target_os = "macos")))]
    { None }
    #[cfg(all(target_os = "macos", not(any(target_arch = "aarch64", target_arch = "x86_64"))))]
    { None }
}

fn fetch_latest_release() -> Result<Option<UpdateRelease>, String> {
    let asset_name = platform_asset().ok_or_else(|| "Automatic downloads are available for Windows and macOS only.".to_owned())?;
    let mut curl = Command::new("curl");
    #[cfg(windows)]
    curl.creation_flags(0x0800_0000);
    let output = curl
        .args(["--fail", "--location", "--silent", "--show-error", "--max-time", "35", "--user-agent", "Lumen-Player-Updater", LATEST_RELEASE_API])
        .output()
        .map_err(|e| format!("Could not start the update checker: {e}"))?;
    if !output.status.success() {
        return Err(format!("Could not check GitHub for updates: {}", String::from_utf8_lossy(&output.stderr).trim()));
    }
    let json: Value = serde_json::from_slice(&output.stdout).map_err(|e| format!("GitHub returned an unreadable release response: {e}"))?;
    let tag = json.get("tag_name").and_then(Value::as_str).ok_or("The latest release has no version tag.")?;
    let version_text = tag.strip_prefix('v').unwrap_or(tag);
    let latest = Version::parse(version_text).map_err(|e| format!("The latest release version is invalid: {e}"))?;
    let current = Version::parse(env!("CARGO_PKG_VERSION")).map_err(|e| format!("This app's version is invalid: {e}"))?;
    if latest <= current { return Ok(None); }

    let assets = json.get("assets").and_then(Value::as_array).ok_or("The latest release has no downloadable assets.")?;
    let asset = assets.iter().find(|asset| asset.get("name").and_then(Value::as_str) == Some(asset_name))
        .ok_or_else(|| format!("The latest release does not include {asset_name}."))?;
    let asset_url = asset.get("browser_download_url").and_then(Value::as_str).ok_or("The release download link is missing.")?;
    let page_url = json.get("html_url").and_then(Value::as_str).unwrap_or("https://github.com/Makerxm800/Lumen/releases/latest");
    Ok(Some(UpdateRelease {
        version: latest.to_string(), page_url: page_url.to_owned(), asset_name: asset_name.to_owned(), asset_url: asset_url.to_owned(),
    }))
}

fn download_release(release: &UpdateRelease) -> Result<PathBuf, String> {
    if release.asset_name.contains('/') || release.asset_name.contains('\\') {
        return Err("The update filename is not safe.".into());
    }
    let directory = download_directory();
    std::fs::create_dir_all(&directory).map_err(|e| format!("Could not create the Downloads folder: {e}"))?;
    let destination = directory.join(&release.asset_name);
    let partial = destination.with_extension("zip.part");
    let mut curl = Command::new("curl");
    #[cfg(windows)]
    curl.creation_flags(0x0800_0000);
    let output = curl
        .args(["--fail", "--location", "--silent", "--show-error", "--max-time", "900", "--user-agent", "Lumen-Player-Updater", "--output"])
        .arg(&partial)
        .arg(&release.asset_url)
        .output()
        .map_err(|e| format!("Could not start the update download: {e}"))?;
    if !output.status.success() {
        let _ = std::fs::remove_file(&partial);
        return Err(format!("The update download failed: {}", String::from_utf8_lossy(&output.stderr).trim()));
    }
    if std::fs::metadata(&partial).map(|m| m.len()).unwrap_or(0) < 1024 {
        let _ = std::fs::remove_file(&partial);
        return Err("The downloaded update looks incomplete; please try again.".into());
    }
    if destination.exists() { std::fs::remove_file(&destination).map_err(|e| format!("Could not replace the older download: {e}"))?; }
    std::fs::rename(&partial, &destination).map_err(|e| format!("Could not finish saving the update: {e}"))?;
    Ok(destination)
}

fn download_directory() -> PathBuf {
    #[cfg(windows)]
    let home = std::env::var_os("USERPROFILE").map(PathBuf::from);
    #[cfg(not(windows))]
    let home = std::env::var_os("HOME").map(PathBuf::from);
    home.map(|path| path.join("Downloads")).unwrap_or_else(|| std::env::temp_dir().join("Lumen-Downloads"))
}

pub(crate) fn reveal_file(path: &std::path::Path) -> Result<(), String> {
    #[cfg(target_os = "windows")]
    let result = Command::new("explorer.exe").arg(path.parent().unwrap_or(path)).spawn();
    #[cfg(target_os = "macos")]
    let result = Command::new("open").arg("-R").arg(path).spawn();
    #[cfg(not(any(target_os = "windows", target_os = "macos")))]
    let result = Command::new("xdg-open").arg(path.parent().unwrap_or(path)).spawn();
    result.map(|_| ()).map_err(|e| format!("Could not open the Downloads folder: {e}"))
}
