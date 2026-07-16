#![cfg(target_os = "android")]

use std::{panic::AssertUnwindSafe, ptr};

use jni::{
    objects::{JByteArray, JClass, JString},
    sys::jstring,
    JNIEnv,
};
use serde::Serialize;
use serde_json::{json, Value};
use zeroize::Zeroizing;

use crate::mobile::{
    autofill::{self, AutofillSaveDraft, AutofillSelection, AutofillTarget},
    error::MobileError,
    runtime,
};

type NativeResult = Result<Value, MobileError>;

#[no_mangle]
pub extern "system" fn Java_io_github_langxi13_secretbase_autofill_AutofillNativeBridge_openWithCredential(
    mut env: JNIEnv,
    _class: JClass,
    data_root: JString,
    credential: JByteArray,
    target_json: JString,
) -> jstring {
    let result = read_open_inputs(&mut env, data_root, target_json).and_then(|(root, target)| {
        let credential = env
            .convert_byte_array(&credential)
            .map_err(|_| MobileError::new("AUTOFILL_NATIVE_INVALID", "无法读取设备解锁凭据"))?;
        let credential = Zeroizing::new(credential);
        guarded(|| {
            serialize(autofill::open_with_device_credential(
                &root,
                credential.as_slice(),
                target,
            )?)
        })
    });
    return_json(&mut env, result)
}

#[no_mangle]
pub extern "system" fn Java_io_github_langxi13_secretbase_autofill_AutofillNativeBridge_openWithPassword(
    mut env: JNIEnv,
    _class: JClass,
    data_root: JString,
    password_utf8: JByteArray,
    target_json: JString,
) -> jstring {
    let result = read_open_inputs(&mut env, data_root, target_json).and_then(|(root, target)| {
        let password = env
            .convert_byte_array(&password_utf8)
            .map_err(|_| MobileError::new("AUTOFILL_NATIVE_INVALID", "无法读取主密码"))?;
        let password = Zeroizing::new(password);
        let password = std::str::from_utf8(password.as_slice())
            .map_err(|_| MobileError::new("VALIDATION_FAILED", "主密码编码无效"))?;
        guarded(|| serialize(autofill::open_with_password(&root, password, target)?))
    });
    return_json(&mut env, result)
}

#[no_mangle]
pub extern "system" fn Java_io_github_langxi13_secretbase_autofill_AutofillNativeBridge_select(
    mut env: JNIEnv,
    _class: JClass,
    session_token: JString,
    selection_json: JString,
) -> jstring {
    let result = (|| {
        let token = read_string(&mut env, session_token)?;
        let selection: AutofillSelection = parse_json(&read_string(&mut env, selection_json)?)?;
        guarded(|| serialize(autofill::select(&token, selection)?))
    })();
    return_json(&mut env, result)
}

#[no_mangle]
pub extern "system" fn Java_io_github_langxi13_secretbase_autofill_AutofillNativeBridge_cancel(
    mut env: JNIEnv,
    _class: JClass,
    session_token: JString,
) -> jstring {
    let result = read_string(&mut env, session_token).and_then(|token| {
        guarded(|| {
            autofill::cancel(&token);
            Ok(json!({"cancelled": true}))
        })
    });
    return_json(&mut env, result)
}

#[no_mangle]
pub extern "system" fn Java_io_github_langxi13_secretbase_autofill_AutofillNativeBridge_saveWithCredential(
    mut env: JNIEnv,
    _class: JClass,
    data_root: JString,
    credential: JByteArray,
    draft_json: JString,
) -> jstring {
    let result = (|| {
        let root = read_string(&mut env, data_root)?;
        let draft: AutofillSaveDraft = parse_json(&read_string(&mut env, draft_json)?)?;
        let credential = env
            .convert_byte_array(&credential)
            .map_err(|_| MobileError::new("AUTOFILL_NATIVE_INVALID", "无法读取设备解锁凭据"))?;
        let credential = Zeroizing::new(credential);
        guarded(|| {
            let result = runtime::save_autofill_entry_with_device_credential(
                root,
                credential.to_vec(),
                draft.into_entry_draft()?,
            )?;
            Ok(json!({"revision": result.revision, "message": result.message}))
        })
    })();
    return_json(&mut env, result)
}

#[no_mangle]
pub extern "system" fn Java_io_github_langxi13_secretbase_autofill_AutofillNativeBridge_saveWithPassword(
    mut env: JNIEnv,
    _class: JClass,
    data_root: JString,
    password_utf8: JByteArray,
    draft_json: JString,
) -> jstring {
    let result = (|| {
        let root = read_string(&mut env, data_root)?;
        let draft: AutofillSaveDraft = parse_json(&read_string(&mut env, draft_json)?)?;
        let password = env
            .convert_byte_array(&password_utf8)
            .map_err(|_| MobileError::new("AUTOFILL_NATIVE_INVALID", "无法读取主密码"))?;
        let password = Zeroizing::new(password);
        let password = std::str::from_utf8(password.as_slice())
            .map_err(|_| MobileError::new("VALIDATION_FAILED", "主密码编码无效"))?;
        guarded(|| {
            let result = runtime::save_autofill_entry_with_password(
                root,
                password.to_string(),
                draft.into_entry_draft()?,
            )?;
            Ok(json!({"revision": result.revision, "message": result.message}))
        })
    })();
    return_json(&mut env, result)
}

fn read_open_inputs(
    env: &mut JNIEnv,
    data_root: JString,
    target_json: JString,
) -> Result<(String, AutofillTarget), MobileError> {
    let root = read_string(env, data_root)?;
    let target = parse_json(&read_string(env, target_json)?)?;
    Ok((root, target))
}

fn read_string(env: &mut JNIEnv, value: JString) -> Result<String, MobileError> {
    env.get_string(&value)
        .map(|value| value.into())
        .map_err(|_| MobileError::new("AUTOFILL_NATIVE_INVALID", "自动填充参数无效"))
}

fn parse_json<T: serde::de::DeserializeOwned>(content: &str) -> Result<T, MobileError> {
    serde_json::from_str(content)
        .map_err(|_| MobileError::new("AUTOFILL_NATIVE_INVALID", "自动填充参数格式无效"))
}

fn serialize<T: Serialize>(value: T) -> NativeResult {
    serde_json::to_value(value)
        .map_err(|_| MobileError::new("AUTOFILL_NATIVE_FAILED", "无法生成自动填充结果"))
}

fn guarded(operation: impl FnOnce() -> NativeResult) -> NativeResult {
    std::panic::catch_unwind(AssertUnwindSafe(operation)).unwrap_or_else(|_| {
        Err(MobileError::retryable(
            "AUTOFILL_NATIVE_FAILED",
            "自动填充运行状态异常，请重试",
        ))
    })
}

fn return_json(env: &mut JNIEnv, result: NativeResult) -> jstring {
    let payload = match result {
        Ok(data) => json!({"ok": true, "data": data}),
        Err(MobileError::Failure {
            code,
            message,
            retryable,
        }) => json!({
            "ok": false,
            "error": {
                "code": code,
                "message": message,
                "retryable": retryable
            }
        }),
    };
    match env.new_string(payload.to_string()) {
        Ok(value) => value.into_raw(),
        Err(_) => ptr::null_mut(),
    }
}
