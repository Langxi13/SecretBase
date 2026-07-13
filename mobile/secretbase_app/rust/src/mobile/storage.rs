use std::{
    fs::{self, File, OpenOptions},
    io::Write,
    path::{Path, PathBuf},
    time::{SystemTime, UNIX_EPOCH},
};

#[cfg(unix)]
use std::os::unix::fs::OpenOptionsExt;

use uuid::Uuid;

use super::{error::MobileError, models::RecoverySnapshot};

pub const VAULT_FILENAME: &str = "secretbase.vault";
pub const SECURE_SETTINGS_FILENAME: &str = "secure-settings.vault";
const RECOVERY_LIMIT: usize = 10;

pub fn vault_path(root: &Path) -> PathBuf {
    root.join(VAULT_FILENAME)
}

pub fn secure_settings_path(root: &Path) -> PathBuf {
    root.join(SECURE_SETTINGS_FILENAME)
}

pub fn read_secure_settings(root: &Path) -> Result<Option<Vec<u8>>, MobileError> {
    let path = secure_settings_path(root);
    if !path.is_file() {
        return Ok(None);
    }
    Ok(Some(fs::read(path)?))
}

pub fn persist_secure_settings(root: &Path, content: &[u8]) -> Result<(), MobileError> {
    atomic_write(&secure_settings_path(root), content)
}

pub fn delete_secure_settings(root: &Path) -> Result<(), MobileError> {
    let path = secure_settings_path(root);
    if path.exists() {
        fs::remove_file(path)?;
    }
    Ok(())
}

fn recovery_dir(root: &Path) -> PathBuf {
    root.join("backups").join("recovery")
}

fn unix_millis() -> u128 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map_or(0, |duration| duration.as_millis())
}

pub fn read_vault(root: &Path) -> Result<Vec<u8>, MobileError> {
    Ok(fs::read(vault_path(root))?)
}

pub fn persist_vault(root: &Path, content: &[u8], backup_current: bool) -> Result<(), MobileError> {
    fs::create_dir_all(root)?;
    let target = vault_path(root);
    if backup_current && target.is_file() {
        let current = fs::read(&target)?;
        if current != content {
            save_recovery(root, &current)?;
        }
    }
    atomic_write(&target, content)
}

pub fn atomic_write(path: &Path, content: &[u8]) -> Result<(), MobileError> {
    let parent = path
        .parent()
        .ok_or_else(|| MobileError::new("INVALID_PATH", "本机数据路径无效"))?;
    fs::create_dir_all(parent)?;
    let temporary = parent.join(format!(
        ".{}.{}.tmp",
        path.file_name().and_then(|v| v.to_str()).unwrap_or("vault"),
        Uuid::new_v4()
    ));
    let mut options = OpenOptions::new();
    options.create_new(true).write(true);
    #[cfg(unix)]
    options.mode(0o600);
    let result = (|| -> Result<(), MobileError> {
        let mut file = options.open(&temporary)?;
        file.write_all(content)?;
        file.flush()?;
        file.sync_all()?;
        fs::rename(&temporary, path)?;
        if let Ok(directory) = File::open(parent) {
            let _ = directory.sync_all();
        }
        Ok(())
    })();
    if temporary.exists() {
        let _ = fs::remove_file(&temporary);
    }
    result
}

fn save_recovery(root: &Path, content: &[u8]) -> Result<(), MobileError> {
    let directory = recovery_dir(root);
    fs::create_dir_all(&directory)?;
    let filename = format!("recovery-{}-{}.vault", unix_millis(), Uuid::new_v4());
    atomic_write(&directory.join(filename), content)?;
    cleanup_recovery(&directory)
}

fn cleanup_recovery(directory: &Path) -> Result<(), MobileError> {
    let mut files = recovery_files(directory)?;
    files.sort_by(|left, right| right.0.cmp(&left.0));
    for (_, path) in files.into_iter().skip(RECOVERY_LIMIT) {
        fs::remove_file(path)?;
    }
    Ok(())
}

fn recovery_files(directory: &Path) -> Result<Vec<(String, PathBuf)>, MobileError> {
    if !directory.is_dir() {
        return Ok(Vec::new());
    }
    let mut files = Vec::new();
    for entry in fs::read_dir(directory)? {
        let entry = entry?;
        let path = entry.path();
        let Some(name) = path.file_name().and_then(|value| value.to_str()) else {
            continue;
        };
        if path.is_file() && name.starts_with("recovery-") && name.ends_with(".vault") {
            files.push((name.to_string(), path));
        }
    }
    Ok(files)
}

pub fn list_recovery(root: &Path) -> Result<Vec<RecoverySnapshot>, MobileError> {
    let mut files = recovery_files(&recovery_dir(root))?;
    files.sort_by(|left, right| right.0.cmp(&left.0));
    files
        .into_iter()
        .map(|(id, path)| {
            let metadata = fs::metadata(&path)?;
            let created_at = id
                .strip_prefix("recovery-")
                .and_then(|value| value.split('-').next())
                .unwrap_or("")
                .to_string();
            Ok(RecoverySnapshot {
                id,
                created_at,
                size_bytes: metadata.len(),
            })
        })
        .collect()
}

pub fn read_recovery(root: &Path, id: &str) -> Result<Vec<u8>, MobileError> {
    if Path::new(id).file_name().and_then(|value| value.to_str()) != Some(id)
        || !id.starts_with("recovery-")
        || !id.ends_with(".vault")
    {
        return Err(MobileError::new("INVALID_RECOVERY", "恢复记录无效"));
    }
    Ok(fs::read(recovery_dir(root).join(id))?)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn persist_keeps_only_ten_recovery_snapshots() {
        let directory = tempfile::tempdir().unwrap();
        persist_vault(directory.path(), b"version-0", false).unwrap();
        for version in 1..=12 {
            persist_vault(
                directory.path(),
                format!("version-{version}").as_bytes(),
                true,
            )
            .unwrap();
        }

        let recovery = list_recovery(directory.path()).unwrap();
        assert_eq!(recovery.len(), RECOVERY_LIMIT);
        assert_eq!(read_vault(directory.path()).unwrap(), b"version-12");
        for snapshot in recovery {
            assert!(read_recovery(directory.path(), &snapshot.id).is_ok());
        }
    }

    #[test]
    fn recovery_ids_cannot_escape_the_private_directory() {
        let directory = tempfile::tempdir().unwrap();
        for id in [
            "../secretbase.vault",
            "/tmp/recovery-x.vault",
            "invalid.vault",
        ] {
            assert!(read_recovery(directory.path(), id).is_err());
        }
    }

    #[test]
    fn atomic_write_replaces_content_without_leaving_temp_files() {
        let directory = tempfile::tempdir().unwrap();
        let target = directory.path().join("settings.vault");
        atomic_write(&target, b"first").unwrap();
        atomic_write(&target, b"second").unwrap();

        assert_eq!(fs::read(&target).unwrap(), b"second");
        let leftovers = fs::read_dir(directory.path())
            .unwrap()
            .filter_map(Result::ok)
            .filter(|entry| entry.file_name().to_string_lossy().ends_with(".tmp"))
            .count();
        assert_eq!(leftovers, 0);
    }
}
