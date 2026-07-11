package io.bluetape.serde.conformance

import org.apache.fory.Fory
import org.apache.fory.annotation.ForyField
import org.apache.fory.annotation.ForyStruct
import org.apache.fory.kotlin.ForyKotlin
import org.apache.fory.kotlin.register
import java.io.Serializable
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.nio.file.Files
import java.nio.file.Path
import kotlin.io.path.readBytes

private const val HEADER_SIZE = 20
private const val SCHEMA_ID = 1_112_819_289L
private const val SCHEMA_VERSION = 1
private const val TYPE_ID = 1001L

@ForyStruct(evolving = false)
data class ConformanceRecord(
    @field:ForyField(id = 1) val recordId: Long,
    @field:ForyField(id = 2) val name: String,
    @field:ForyField(id = 3) val active: Boolean,
    @field:ForyField(id = 4) val scores: List<Int>,
) : Serializable {
    private companion object {
        const val serialVersionUID: Long = 1L
    }
}

private val expected = ConformanceRecord(
    recordId = 7,
    name = "blue",
    active = true,
    scores = listOf(1, 2, 3),
)

private fun newFory(): Fory = ForyKotlin.builder()
    .withXlang(true)
    .withCompatible(false)
    .requireClassRegistration(true)
    .withRefTracking(false)
    .withMaxDepth(64)
    .withMaxTypeFields(256)
    .withMaxTypeMetaBytes(4096)
    .withMaxSchemaVersionsPerType(8)
    .withMaxAverageSchemaVersionsPerType(2)
    .build()
    .also { it.register<ConformanceRecord>(TYPE_ID) }

private fun wrap(body: ByteArray): ByteArray = ByteBuffer
    .allocate(HEADER_SIZE + body.size)
    .order(ByteOrder.BIG_ENDIAN)
    .put("BTFY".toByteArray(Charsets.US_ASCII))
    .put(1)
    .put(0)
    .putInt(SCHEMA_ID.toInt())
    .putShort(SCHEMA_VERSION.toShort())
    .putInt(TYPE_ID.toInt())
    .putInt(body.size)
    .put(body)
    .array()

private fun unwrap(data: ByteArray): ByteArray {
    require(data.size >= HEADER_SIZE) { "invalid bluetape Fory envelope" }
    val buffer = ByteBuffer.wrap(data).order(ByteOrder.BIG_ENDIAN)
    val magic = ByteArray(4).also(buffer::get)
    require(magic.contentEquals("BTFY".toByteArray(Charsets.US_ASCII))) {
        "invalid bluetape Fory envelope"
    }
    require(buffer.get().toInt() == 1 && buffer.get().toInt() == 0) {
        "unsupported bluetape Fory envelope"
    }
    require(
        buffer.int.toLong() and 0xFFFF_FFFFL == SCHEMA_ID &&
            buffer.short.toInt() and 0xFFFF == SCHEMA_VERSION &&
            buffer.int.toLong() and 0xFFFF_FFFFL == TYPE_ID,
    ) { "bluetape Fory registration mismatch" }
    val bodyLength = buffer.int
    require(bodyLength > 0 && bodyLength == data.size - HEADER_SIZE) {
        "invalid bluetape Fory body length"
    }
    return data.copyOfRange(HEADER_SIZE, data.size)
}

private fun generate(path: Path) {
    Files.write(path, wrap(newFory().serialize(expected)))
}

private fun verify(path: Path) {
    val result = newFory().deserialize(unwrap(path.readBytes()), ConformanceRecord::class.java)
    require(result == expected) { "Fory conformance value does not match the canonical record" }
}

fun main(args: Array<String>) {
    require(args.size == 2 && args[0] in setOf("generate", "verify")) {
        "usage: fory-conformance generate|verify PATH"
    }
    val path = Path.of(args[1])
    if (args[0] == "generate") generate(path) else verify(path)
}
