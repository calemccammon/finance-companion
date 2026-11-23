import com.calemccammon.financecompanion.buildlogic.library
import com.calemccammon.financecompanion.buildlogic.libs
import io.github.takahirom.roborazzi.RoborazziExtension
import org.gradle.api.Plugin
import org.gradle.api.Project
import org.gradle.kotlin.dsl.configure
import org.gradle.kotlin.dsl.dependencies

/**
 * A feature module: one screen and its view model.
 *
 * A feature sees the domain and the component catalog, and nothing of where
 * data comes from: it cannot name the database or the network because it does
 * not depend on them.
 */
class AndroidFeatureConventionPlugin : Plugin<Project> {
    override fun apply(target: Project) =
        with(target) {
            pluginManager.apply("fc.android.library")
            pluginManager.apply("fc.android.compose")
            pluginManager.apply("fc.hilt")
            pluginManager.apply("io.github.takahirom.roborazzi")

            extensions.configure<RoborazziExtension> {
                // Pictures of the screens, committed beside the tests that take
                // them. `recordRoborazziDebug` draws them again;
                // `verifyRoborazziDebug` fails if a screen no longer matches.
                outputDir.set(layout.projectDirectory.dir("src/test/snapshots"))
            }

            dependencies {
                "implementation"(project(":core:domain"))
                "implementation"(project(":catalog"))

                "implementation"(libs.library("androidx-hilt-lifecycle-viewmodel-compose"))
                "implementation"(libs.library("androidx-lifecycle-runtime-compose"))
                "implementation"(libs.library("androidx-lifecycle-viewmodel-compose"))
                "implementation"(libs.library("kotlinx-coroutines-android"))

                "testImplementation"(project(":core:testing"))
                "testImplementation"(libs.library("roborazzi"))
                "testImplementation"(libs.library("roborazzi-compose"))
            }
        }
}
