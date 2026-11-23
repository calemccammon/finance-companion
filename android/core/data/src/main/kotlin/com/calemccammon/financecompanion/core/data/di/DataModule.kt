package com.calemccammon.financecompanion.core.data.di

import android.content.Context
import androidx.room.Room
import com.calemccammon.financecompanion.core.data.OfflineFirstConversationRepository
import com.calemccammon.financecompanion.core.data.database.ConversationDao
import com.calemccammon.financecompanion.core.data.database.ConversationDatabase
import com.calemccammon.financecompanion.core.data.network.AgentClient
import com.calemccammon.financecompanion.core.domain.ConversationRepository
import dagger.Binds
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.android.qualifiers.ApplicationContext
import dagger.hilt.components.SingletonComponent
import okhttp3.OkHttpClient
import java.time.Clock
import java.time.Duration
import javax.inject.Singleton

/** Where the agent is. The app supplies it, since it differs between builds. */
data class AgentConfig(
    val baseUrl: String,
)

@Module
@InstallIn(SingletonComponent::class)
internal abstract class DataModule {
    @Binds
    @Singleton
    abstract fun conversation(repository: OfflineFirstConversationRepository): ConversationRepository

    companion object {
        @Provides
        @Singleton
        fun database(
            @ApplicationContext context: Context,
        ): ConversationDatabase =
            Room.databaseBuilder(context, ConversationDatabase::class.java, "conversation.db").build()

        @Provides
        fun dao(database: ConversationDatabase): ConversationDao = database.conversationDao()

        @Provides
        @Singleton
        fun agentClient(config: AgentConfig): AgentClient =
            AgentClient(
                config.baseUrl,
                OkHttpClient
                    .Builder()
                    // A model may think for a while before its first message; then the stream flows.
                    .readTimeout(Duration.ofSeconds(READ_TIMEOUT_SECONDS))
                    .build(),
            )

        @Provides
        fun clock(): Clock = Clock.systemUTC()

        private const val READ_TIMEOUT_SECONDS = 90L
    }
}
