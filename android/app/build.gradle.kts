plugins {
    alias(libs.plugins.fc.android.application)
    alias(libs.plugins.fc.android.compose)
    alias(libs.plugins.fc.hilt)
}

android {
    namespace = "com.calemccammon.financecompanion"

    defaultConfig {
        applicationId = "com.calemccammon.financecompanion"
        versionCode = 1
        versionName = "0.1"
        // Where the agent is. The emulator reaches the computer it runs on at 10.0.2.2.
        buildConfigField("String", "AGENT_URL", "\"http://10.0.2.2:8000/\"")

        // Device tests run with Hilt's test application, each in a fresh
        // process with the app's data cleared.
        testInstrumentationRunner = "com.calemccammon.financecompanion.HiltTestRunner"
        testInstrumentationRunnerArguments["clearPackageData"] = "true"
    }
    testOptions {
        execution = "ANDROIDX_TEST_ORCHESTRATOR"
    }
    sourceSets {
        // The recorded agent streams the device tests replay, shared with the agent's tests.
        getByName("androidTest").assets.directories.add("../../catalog/fixtures")
    }
    buildFeatures {
        buildConfig = true
    }
}

dependencies {
    implementation(projects.catalog)
    implementation(projects.core.data)
    implementation(projects.feature.conversation)

    implementation(libs.androidx.activity.compose)

    androidTestImplementation(platform(libs.compose.bom))
    androidTestImplementation(libs.compose.ui.test.junit4)
    androidTestImplementation(libs.androidx.test.ext.junit)
    androidTestImplementation(libs.androidx.test.runner)
    androidTestImplementation(libs.hilt.android.testing)
    androidTestImplementation(libs.kotlin.test)
    androidTestImplementation(libs.okhttp.mockwebserver)
    androidTestUtil(libs.androidx.test.orchestrator)
    kspAndroidTest(libs.hilt.compiler)
}
