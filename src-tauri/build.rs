fn main() {
    if std::env::var("CARGO_CFG_TARGET_OS").as_deref() == Ok("windows") {
        // The executable is never linked as a library. Skip unused export artifacts.
        println!("cargo:rustc-link-arg-bin=cts-save-editor=/NOIMPLIB");
        println!("cargo:rustc-link-arg-bin=cts-save-editor=/NOEXP");
    }
    tauri_build::build();
}
