plugins {
    alias(libs.plugins.fc.jvm.library)
}

dependencies {
    api(projects.core.domain)
    api(libs.junit)
    api(libs.kotlinx.coroutines.test)
}
