plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("com.chaquo.python")
}

android {
    namespace = "com.party.dj"
    compileSdk = 34

    defaultConfig {
        applicationId = "com.party.dj"
        minSdk = 24
        targetSdk = 34
        versionCode = 1
        versionName = "1.0"
        ndk {
            abiFilters += listOf("arm64-v8a", "x86_64")
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }
}

// The DJ itself is the same Python code as on the Mac (copied into src/main/python by the build).
chaquopy {
    defaultConfig {
        version = "3.11"
        pip {
            install("-r", "../../requirements.txt")
        }
        extractPackages("partydj")
    }
}
