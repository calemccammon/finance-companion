package com.calemccammon.financecompanion.buildlogic

import com.android.build.api.dsl.CommonExtension
import io.gitlab.arturbosch.detekt.Detekt
import io.gitlab.arturbosch.detekt.extensions.DetektExtension
import org.gradle.api.JavaVersion
import org.gradle.api.Project
import org.gradle.api.artifacts.VersionCatalog
import org.gradle.api.artifacts.VersionCatalogsExtension
import org.gradle.kotlin.dsl.configure
import org.gradle.kotlin.dsl.dependencies
import org.gradle.kotlin.dsl.getByType
import org.gradle.kotlin.dsl.withType
import org.jetbrains.kotlin.gradle.dsl.JvmTarget
import org.jetbrains.kotlin.gradle.tasks.KotlinCompile
import org.jlleitschuh.gradle.ktlint.KtlintExtension

/** The version catalog in `gradle/libs.versions.toml`. */
internal val Project.libs: VersionCatalog
    get() = extensions.getByType<VersionCatalogsExtension>().named("libs")

internal fun VersionCatalog.version(name: String): String = findVersion(name).get().requiredVersion

internal fun VersionCatalog.library(name: String) = findLibrary(name).get()

/** The Java version every module's bytecode is built for. */
internal val javaVersion = JavaVersion.VERSION_17

/** What every Android module, app or library, has in common. */
internal fun Project.configureAndroid(android: CommonExtension) {
    android.apply {
        compileSdk = libs.version("android-compileSdk").toInt()
        defaultConfig.minSdk = libs.version("android-minSdk").toInt()
        compileOptions.sourceCompatibility = javaVersion
        compileOptions.targetCompatibility = javaVersion
        // Tests on the JVM read resources and the manifest through Robolectric.
        testOptions.unitTests.isIncludeAndroidResources = true
        lint.warningsAsErrors = true
        lint.abortOnError = true
        // A newer library version is Dependabot's news, not a lint failure.
        lint.disable += setOf("GradleDependency", "NewerVersionAvailable", "AndroidGradlePluginVersion")
    }
}

/** Kotlin compiler settings, the same in Android and plain JVM modules. */
internal fun Project.configureKotlin() {
    tasks.withType<KotlinCompile>().configureEach {
        compilerOptions {
            jvmTarget.set(JvmTarget.JVM_17)
            allWarningsAsErrors.set(true)
            if (name.contains("Test")) {
                // The tests move a test clock by hand, which the coroutines
                // library still marks as experimental.
                optIn.add("kotlinx.coroutines.ExperimentalCoroutinesApi")
            }
        }
    }
}

/** ktlint for formatting and style, detekt for code smells. */
internal fun Project.configureStaticAnalysis() {
    pluginManager.apply("org.jlleitschuh.gradle.ktlint")
    pluginManager.apply("io.gitlab.arturbosch.detekt")

    extensions.configure<KtlintExtension> {
        filter {
            // Generated code.
            exclude { it.file.path.contains("/build/") }
        }
    }
    extensions.configure<DetektExtension> {
        buildUponDefaultConfig = true
        config.setFrom(rootProject.file("config/detekt/detekt.yml"))
        source.setFrom(fileTree("src") { include("**/*.kt") })
    }
    tasks.withType<Detekt>().configureEach {
        jvmTarget = javaVersion.toString()
    }
}

/** The libraries every module's unit tests use. */
internal fun Project.configureUnitTests() {
    tasks.withType<org.gradle.api.tasks.testing.Test>().configureEach {
        // Lets a test rewrite a committed file it checks, when asked to.
        providers.systemProperty("fc.updateCatalog").orNull?.let { systemProperty("fc.updateCatalog", it) }
    }
    dependencies {
        "testImplementation"(libs.library("junit"))
        "testImplementation"(libs.library("kotlin-test"))
        "testImplementation"(libs.library("kotlinx-coroutines-test"))
        "testImplementation"(libs.library("turbine"))
    }
}
