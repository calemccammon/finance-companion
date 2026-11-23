plugins {
    alias(libs.plugins.fc.android.application)
    alias(libs.plugins.fc.android.compose)
}

android {
    namespace = "com.calemccammon.financecompanion"

    defaultConfig {
        applicationId = "com.calemccammon.financecompanion"
        versionCode = 1
        versionName = "0.1"
        // Where the agent is. The emulator reaches the computer it runs on at 10.0.2.2.
        buildConfigField("String", "AGENT_URL", "\"http://10.0.2.2:8000/\"")
    }
    buildFeatures {
        buildConfig = true
    }
}

dependencies {
    implementation(projects.catalog)

    implementation(libs.androidx.activity.compose)
    implementation(libs.androidx.lifecycle.runtime.compose)
    implementation(libs.androidx.lifecycle.viewmodel.compose)
    implementation(libs.kotlinx.coroutines.android)
    implementation(libs.kotlinx.serialization.json)
    implementation(libs.okhttp)
    implementation(libs.okhttp.sse)

    testImplementation(libs.okhttp.mockwebserver)
}
