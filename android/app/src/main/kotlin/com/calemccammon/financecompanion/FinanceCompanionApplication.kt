package com.calemccammon.financecompanion

import android.app.Application
import com.calemccammon.financecompanion.core.data.di.AgentConfig
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.android.HiltAndroidApp
import dagger.hilt.components.SingletonComponent

@HiltAndroidApp
class FinanceCompanionApplication : Application()

/** Where this build's agent is. A test of the whole app puts its own stand-in here. */
@Module
@InstallIn(SingletonComponent::class)
object AgentConfigModule {
    @Provides
    fun agentConfig(): AgentConfig = AgentConfig(BuildConfig.AGENT_URL)
}
