plugins {
    alias(libs.plugins.fc.android.feature)
}

dependencies {
    implementation(libs.kotlinx.serialization.json)

    testImplementation(libs.a2ui.compose.ui.testing)
}
