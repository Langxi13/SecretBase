import java.util.Properties

plugins {
    id("com.android.application")
    id("dev.flutter.flutter-gradle-plugin")
}

val keystoreProperties = Properties()
val keystorePropertiesFile = rootProject.file("key.properties")
if (keystorePropertiesFile.isFile) {
    keystorePropertiesFile.inputStream().use(keystoreProperties::load)
}

fun signingEnvironment(name: String): String? =
    System.getenv(name)?.takeIf { it.isNotBlank() }

val environmentSigning =
    mapOf(
        "storeFile" to signingEnvironment("SECRETBASE_ANDROID_KEYSTORE_FILE"),
        "storePassword" to signingEnvironment("SECRETBASE_ANDROID_KEYSTORE_PASSWORD"),
        "keyAlias" to signingEnvironment("SECRETBASE_ANDROID_KEY_ALIAS"),
        "keyPassword" to signingEnvironment("SECRETBASE_ANDROID_KEY_PASSWORD"),
    )
val hasAnyEnvironmentSigning = environmentSigning.values.any { it != null }
val hasCompleteEnvironmentSigning = environmentSigning.values.all { it != null }
require(!hasAnyEnvironmentSigning || hasCompleteEnvironmentSigning) {
    "Android signing environment variables must be configured together"
}

if (keystorePropertiesFile.isFile) {
    val missingProperties =
        listOf("storeFile", "storePassword", "keyAlias", "keyPassword")
            .filter { keystoreProperties.getProperty(it).isNullOrBlank() }
    require(missingProperties.isEmpty()) {
        "Missing Android signing properties: ${missingProperties.joinToString()}"
    }
}

android {
    namespace = "io.github.langxi13.secretbase"
    compileSdk = 36
    ndkVersion = "28.2.13676358"

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    defaultConfig {
        applicationId = "io.github.langxi13.secretbase"
        minSdk = 29
        targetSdk = 36
        versionCode = flutter.versionCode
        versionName = flutter.versionName
    }

    signingConfigs {
        if (hasCompleteEnvironmentSigning || keystorePropertiesFile.isFile) {
            create("release") {
                if (hasCompleteEnvironmentSigning) {
                    keyAlias = environmentSigning.getValue("keyAlias")
                    keyPassword = environmentSigning.getValue("keyPassword")
                    storeFile = file(environmentSigning.getValue("storeFile")!!)
                    storePassword = environmentSigning.getValue("storePassword")
                } else {
                    keyAlias = keystoreProperties.getProperty("keyAlias")
                    keyPassword = keystoreProperties.getProperty("keyPassword")
                    storeFile = file(keystoreProperties.getProperty("storeFile"))
                    storePassword = keystoreProperties.getProperty("storePassword")
                }
            }
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = true
            isShrinkResources = true
            signingConfig = signingConfigs.findByName("release")
        }
    }
}

kotlin {
    compilerOptions {
        jvmTarget = org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17
    }
}

flutter {
    source = "../.."
}
