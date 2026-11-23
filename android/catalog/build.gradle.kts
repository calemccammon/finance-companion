plugins {
    alias(libs.plugins.fc.android.library)
    alias(libs.plugins.fc.android.compose)
}

dependencies {
    api(libs.a2ui.compose.runtime)
    api(libs.a2ui.compose.ui)
    api(libs.a2ui.material3)

    testImplementation(libs.a2ui.compose.ui.testing)
}
