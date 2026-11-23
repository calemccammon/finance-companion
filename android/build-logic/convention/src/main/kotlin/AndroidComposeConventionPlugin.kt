import com.android.build.api.dsl.CommonExtension
import com.calemccammon.financecompanion.buildlogic.library
import com.calemccammon.financecompanion.buildlogic.libs
import org.gradle.api.Plugin
import org.gradle.api.Project
import org.jetbrains.kotlin.compose.compiler.gradle.ComposeCompilerGradlePluginExtension
import org.gradle.kotlin.dsl.configure
import org.gradle.kotlin.dsl.dependencies
import org.gradle.api.tasks.PathSensitivity
import org.gradle.kotlin.dsl.getByType
import org.gradle.kotlin.dsl.withType
import org.jetbrains.kotlin.gradle.tasks.KotlinCompile

/**
 * Jetpack Compose for an Android module that already applies the application
 * or library convention: the compiler plugin, the libraries (versions from
 * the Compose BOM) and what its UI tests need.
 */
class AndroidComposeConventionPlugin : Plugin<Project> {
    override fun apply(target: Project) =
        with(target) {
            pluginManager.apply("org.jetbrains.kotlin.plugin.compose")

            extensions.getByType<CommonExtension>().buildFeatures.compose = true

            val reports = layout.buildDirectory.dir("compose-compiler")
            val writeReports = providers.gradleProperty("composeReports").isPresent
            val stabilityFile = rootProject.layout.projectDirectory.file("config/compose-stability.conf")
            // The compiler plugin is given the file's path, so Gradle would
            // not otherwise compile again when what the file says changes.
            tasks.withType<KotlinCompile>().configureEach {
                inputs.file(stabilityFile).withPathSensitivity(PathSensitivity.NONE)
            }
            extensions.configure<ComposeCompilerGradlePluginExtension> {
                stabilityConfigurationFiles.add(stabilityFile)
                // What the compiler made of each class and composable, written
                // only when asked for with -PcomposeReports.
                if (writeReports) reportsDestination.set(reports)
            }
            if (writeReports) {
                // Declared as an output, so a compile whose result is taken
                // from the build cache brings its reports with it.
                tasks.matching { it.name == "compileDebugKotlin" }.configureEach { outputs.dir(reports) }
            }

            // Fails if a class the compiler treats as stable holds something
            // it cannot vouch for. Marking a class @Immutable is a promise the
            // compiler takes on trust: it skips redrawing a composable whose
            // values are "the same", and a promise that is not kept shows as
            // a screen that does not update. This checks the promise field by
            // field: a field the compiler calls unstable, or one it can only
            // judge when the app runs (a plain List, say), fails the build.
            tasks.register("checkComposeStability") {
                group = "verification"
                description = "Fails if a class the Compose compiler treats as stable has an unstable field."
                dependsOn("compileDebugKotlin")
                val directory = reports
                doLast {
                    check(writeReports) { "Run with -PcomposeReports, which has the compiler write what this reads." }
                    val broken = mutableListOf<String>()
                    directory
                        .get()
                        .asFile
                        .walkTopDown()
                        .filter { it.name.endsWith("-classes.txt") }
                        .forEach { report ->
                            var stableClass: String? = null
                            report.forEachLine { line ->
                                when {
                                    line.startsWith("stable class ") -> stableClass = line.removeSuffix(" {")
                                    !line.startsWith(" ") -> stableClass = null
                                    line.trimStart().startsWith("unstable ") ||
                                        line.trimStart().startsWith("runtime ") ->
                                        stableClass?.let { broken += "$it:${line.trimEnd()}" }
                                }
                            }
                        }
                    check(broken.isEmpty()) {
                        "Fields the compiler cannot vouch for, in classes treated as stable:\n" +
                            broken.joinToString("\n")
                    }
                }
            }

            dependencies {
                val bom = platform(libs.library("compose-bom"))
                "implementation"(bom)
                "implementation"(libs.library("compose-runtime"))
                "implementation"(libs.library("compose-foundation"))
                "implementation"(libs.library("compose-material3"))
                "implementation"(libs.library("compose-material-icons-extended"))
                "implementation"(libs.library("compose-ui"))
                "implementation"(libs.library("compose-ui-tooling-preview"))
                // Lists the Compose compiler can see will not change.
                "api"(libs.library("kotlinx-collections-immutable"))
                "debugImplementation"(libs.library("compose-ui-tooling"))

                // Compose tests run on the JVM, drawn by Robolectric.
                "testImplementation"(bom)
                "testImplementation"(libs.library("compose-ui-test-junit4"))
                "testImplementation"(libs.library("robolectric"))
                "testImplementation"(libs.library("androidx-test-core"))
                "testImplementation"(libs.library("androidx-test-ext-junit"))
                "debugImplementation"(libs.library("compose-ui-test-manifest"))
            }
        }
}
