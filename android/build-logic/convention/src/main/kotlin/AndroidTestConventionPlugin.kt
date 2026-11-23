import com.android.build.api.dsl.TestExtension
import com.calemccammon.financecompanion.buildlogic.configureAndroid
import com.calemccammon.financecompanion.buildlogic.configureKotlin
import com.calemccammon.financecompanion.buildlogic.configureStaticAnalysis
import com.calemccammon.financecompanion.buildlogic.libs
import com.calemccammon.financecompanion.buildlogic.version
import org.gradle.api.Plugin
import org.gradle.api.Project
import org.gradle.kotlin.dsl.configure

/** A module of tests that drive another module's app from outside, as the benchmarks do. */
class AndroidTestConventionPlugin : Plugin<Project> {
    override fun apply(target: Project) =
        with(target) {
            pluginManager.apply("com.android.test")

            extensions.configure<TestExtension> {
                configureAndroid(this)
                defaultConfig.targetSdk = libs.version("android-targetSdk").toInt()
            }
            configureKotlin()
            configureStaticAnalysis()
        }
}
