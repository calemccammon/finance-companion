package com.calemccammon.financecompanion.core.data.database

import androidx.room.ColumnInfo
import androidx.room.Dao
import androidx.room.Database
import androidx.room.Embedded
import androidx.room.Entity
import androidx.room.ForeignKey
import androidx.room.Index
import androidx.room.Insert
import androidx.room.PrimaryKey
import androidx.room.Query
import androidx.room.Relation
import androidx.room.RoomDatabase
import androidx.room.Transaction
import kotlinx.coroutines.flow.Flow

/** A question asked, and the surface its answer is drawn on once the agent has made one. */
@Entity(tableName = "exchanges", indices = [Index("surface_id")])
data class ExchangeEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val question: String,
    /** Milliseconds since the epoch. */
    @ColumnInfo(name = "asked_at") val askedAt: Long,
    @ColumnInfo(name = "surface_id") val surfaceId: String? = null,
)

/** One A2UI message of an answer, as JSON. Ids grow as messages arrive, so they give the order. */
@Entity(
    tableName = "messages",
    indices = [Index("exchange_id")],
    foreignKeys = [
        ForeignKey(ExchangeEntity::class, ["id"], ["exchange_id"], onDelete = ForeignKey.CASCADE),
    ],
)
data class MessageEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    @ColumnInfo(name = "exchange_id") val exchangeId: Long,
    val json: String,
)

data class ExchangeWithMessages(
    @Embedded val exchange: ExchangeEntity,
    @Relation(parentColumn = "id", entityColumn = "exchange_id")
    val messages: List<MessageEntity>,
)

@Dao
interface ConversationDao {
    @Transaction
    @Query("SELECT * FROM exchanges ORDER BY id")
    fun observe(): Flow<List<ExchangeWithMessages>>

    @Insert
    suspend fun insert(exchange: ExchangeEntity): Long

    @Insert
    suspend fun insert(message: MessageEntity)

    @Query("UPDATE exchanges SET surface_id = :surfaceId WHERE id = :exchangeId")
    suspend fun setSurface(
        exchangeId: Long,
        surfaceId: String,
    )

    @Query("SELECT id FROM exchanges WHERE surface_id = :surfaceId")
    suspend fun exchangeFor(surfaceId: String): Long?

    @Query("DELETE FROM exchanges WHERE id = :exchangeId")
    suspend fun delete(exchangeId: Long)
}

@Database(entities = [ExchangeEntity::class, MessageEntity::class], version = 1, exportSchema = true)
abstract class ConversationDatabase : RoomDatabase() {
    abstract fun conversationDao(): ConversationDao
}
