plugins {
    alias(libs.plugins.android.application)
}

android {
    namespace = "io.github.patrickleondev.youdloader"
    compileSdk = 36

    defaultConfig {
        applicationId = "io.github.patrickleondev.youdloader"
        // 26 et pas 24 (minimum de la bibliothèque) : canaux de notification et
        // startForegroundService existent à partir d'Android 8.0.
        minSdk = 26
        targetSdk = 36
        versionCode = 1
        versionName = "2.1.0"
    }

    // Python, ffmpeg et QuickJS pèsent environ 51 Mo par architecture. Un seul APK pour
    // les quatre ferait 200 Mo : on en fabrique un par architecture.
    // arm64-v8a : presque tous les téléphones depuis 2017 ; armeabi-v7a : les plus anciens ;
    // x86_64 : l'émulateur d'Android Studio.
    splits {
        abi {
            isEnable = true
            reset()
            include("arm64-v8a", "armeabi-v7a", "x86_64")
            isUniversalApk = false
        }
    }

    packaging {
        jniLibs {
            // La bibliothèque exécute python, ffmpeg et qjs comme des programmes : il faut
            // qu'Android les extraie sur le disque à l'installation (extractNativeLibs).
            useLegacyPackaging = true
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            // Signée avec la clé de debug pour pouvoir l'installer directement ;
            // une publication sur le Play Store demanderait une vraie clé.
            signingConfig = signingConfigs.getByName("debug")
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_11
        targetCompatibility = JavaVersion.VERSION_11
    }
}

dependencies {
    implementation(libs.appcompat)
    implementation(libs.material)
    implementation(libs.youtubedl.library)
    implementation(libs.youtubedl.ffmpeg)
}
