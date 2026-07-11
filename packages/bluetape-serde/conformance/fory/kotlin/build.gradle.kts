plugins {
    kotlin("jvm") version "2.3.20"
    id("com.google.devtools.ksp") version "2.3.7"
    application
}

dependencies {
    implementation("org.apache.fory:fory-kotlin:1.3.0")
    ksp("org.apache.fory:fory-kotlin-ksp:1.3.0")
}

kotlin {
    jvmToolchain(21)
}

application {
    mainClass = "io.bluetape.serde.conformance.ConformanceCliKt"
}

dependencyLocking {
    lockAllConfigurations()
}
