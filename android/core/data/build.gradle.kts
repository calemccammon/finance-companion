plugins {
    alias(libs.plugins.fc.android.library)
    alias(libs.plugins.fc.android.room)
    alias(libs.plugins.fc.hilt)
}

dependencies {
    api(projects.core.domain)

    implementation(libs.kotlinx.serialization.json)
    implementation(libs.okhttp)
    implementation(libs.okhttp.sse)

    testImplementation(projects.core.testing)
    testImplementation(libs.androidx.test.core)
    testImplementation(libs.okhttp.mockwebserver)
    testImplementation(libs.robolectric)
}
