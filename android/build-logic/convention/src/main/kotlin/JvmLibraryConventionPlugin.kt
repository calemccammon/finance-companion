import com.calemccammon.financecompanion.buildlogic.configureKotlin
import com.calemccammon.financecompanion.buildlogic.configureStaticAnalysis
import com.calemccammon.financecompanion.buildlogic.configureUnitTests
import com.calemccammon.financecompanion.buildlogic.javaVersion
import org.gradle.api.Plugin
import org.gradle.api.Project
import org.gradle.api.plugins.JavaPluginExtension
import org.gradle.kotlin.dsl.configure

/** A plain Kotlin module with no Android in it: the model, the domain and what their tests share. */
class JvmLibraryConventionPlugin : Plugin<Project> {
    override fun apply(target: Project) =
        with(target) {
            pluginManager.apply("org.jetbrains.kotlin.jvm")

            extensions.configure<JavaPluginExtension> {
                sourceCompatibility = javaVersion
                targetCompatibility = javaVersion
            }
            configureKotlin()
            configureStaticAnalysis()
            configureUnitTests()
        }
}
