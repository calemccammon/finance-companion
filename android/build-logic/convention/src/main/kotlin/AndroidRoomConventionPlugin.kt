import androidx.room.gradle.RoomExtension
import com.calemccammon.financecompanion.buildlogic.library
import com.calemccammon.financecompanion.buildlogic.libs
import org.gradle.api.Plugin
import org.gradle.api.Project
import org.gradle.kotlin.dsl.configure
import org.gradle.kotlin.dsl.dependencies

/** Room, with each version of the database's schema written to `schemas/`. */
class AndroidRoomConventionPlugin : Plugin<Project> {
    override fun apply(target: Project) =
        with(target) {
            pluginManager.apply("androidx.room")
            pluginManager.apply("com.google.devtools.ksp")

            extensions.configure<RoomExtension> {
                // Committed, so a change to the tables shows up in review and
                // a migration can be tested against the version before it.
                schemaDirectory("$projectDir/schemas")
            }

            dependencies {
                "implementation"(libs.library("androidx-room-runtime"))
                "implementation"(libs.library("androidx-room-ktx"))
                "ksp"(libs.library("androidx-room-compiler"))
            }
        }
}
