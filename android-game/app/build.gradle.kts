plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
}

android {
    namespace = "com.aquelarre.hoja"
    compileSdk = 34

    defaultConfig {
        applicationId = "com.aquelarre.hoja"
        minSdk = 26
        targetSdk = 34
        versionCode = 1
        versionName = "0.1.0"
    }

    // Sin esto, cada máquina (o cada runner efímero de GitHub Actions)
    // genera su propio debug.keystore aleatorio la primera vez que
    // compila. Como Android no deja instalar una "actualización" de una
    // app si la firma no coincide con la ya instalada, cada build de CI
    // producía un APK firmado con una clave distinta y el teléfono
    // rechazaba la instalación con un conflicto de paquete. Al fijar aquí
    // un debug.keystore concreto (incluido en el repo), todos los builds
    // -- locales o en CI -- quedan firmados siempre igual.
    signingConfigs {
        getByName("debug") {
            storeFile = file("debug.keystore")
            storePassword = "android"
            keyAlias = "androiddebugkey"
            keyPassword = "android"
        }
    }

    buildTypes {
        debug {
            signingConfig = signingConfigs.getByName("debug")
        }
        release {
            isMinifyEnabled = false
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = "17"
    }

    buildFeatures {
        compose = true
    }
}

dependencies {
    implementation(platform("androidx.compose:compose-bom:2024.09.00"))
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-graphics")
    implementation("androidx.compose.ui:ui-tooling-preview")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.activity:activity-compose:1.9.2")
    implementation("androidx.core:core-ktx:1.13.1")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.8.4")

    debugImplementation("androidx.compose.ui:ui-tooling")
}
