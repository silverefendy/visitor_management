# VMS Scanner APK

APK ini adalah scanner native Android untuk Visitor Management.

## Fitur

- Login ke Frappe server.
- Scan QR/barcode dengan kamera native Android.
- Input manual kode.
- Mode Visitor dan Employee.
- Action Check In dan Check Out.
- Preview data sebelum proses.

## Default Server

```text
http://10.1.0.30:8001
```

URL bisa diubah dari field `Server URL` di aplikasi.

## Format Kode

Visitor dapat memakai:

```text
VIS-2026-05-00001
```

atau:

```json
{"visitor_id":"VIS-2026-05-00001"}
```

Employee dapat memakai:

```text
HR-EMP-00001
```

atau:

```json
{"employee":"HR-EMP-00001"}
```

## Build

```powershell
$env:JAVA_HOME='C:\Program Files\Android\Android Studio\jbr'
$env:ANDROID_HOME='C:\Users\Efendy\AppData\Local\Android\Sdk'
$env:ANDROID_SDK_ROOT=$env:ANDROID_HOME
$env:PATH="$env:JAVA_HOME\bin;$env:ANDROID_HOME\platform-tools;$env:PATH"

& 'C:\Users\Efendy\.gradle\wrapper\dists\gradle-9.4.1-bin\arn2x92ynaizyzdaamcbpbhtj\gradle-9.4.1\bin\gradle.bat' :app:assembleDebug
```

APK debug:

```text
app/build/outputs/apk/debug/app-debug.apk
```
