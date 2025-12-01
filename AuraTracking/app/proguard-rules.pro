# Add project specific ProGuard rules here.
# You can control the set of applied configuration files using the
# proguardFiles setting in build.gradle.kts.
#
# For more details, see
#   http://developer.android.com/guide/developing/tools/proguard.html

# If your project uses WebView with JS, uncomment the following
# and specify the fully qualified class name to the JavaScript interface
# class:
#-keepclassmembers class fqcn.of.javascript.interface.for.webview {
#   public *;
#}

# Uncomment this to preserve the line number information for
# debugging stack traces.
-keepattributes SourceFile,LineNumberTable

# If you keep the line number information, uncomment this to
# hide the original source file name.
#-renamesourcefileattribute SourceFile

# ===========================
# KOTLINX SERIALIZATION
# ===========================
-keepattributes *Annotation*, InnerClasses
-dontnote kotlinx.serialization.AnnotationsKt

# Keep serializers
-keep,includedescriptorclasses class com.aura.tracking.**$$serializer { *; }
-keepclassmembers class com.aura.tracking.** {
    *** Companion;
}
-keepclasseswithmembers class com.aura.tracking.** {
    kotlinx.serialization.KSerializer serializer(...);
}

# Serialization core
-keep class kotlinx.serialization.** { *; }
-keep class kotlin.Metadata { *; }

# ===========================
# KTOR
# ===========================
-keep class io.ktor.** { *; }
-keep class kotlinx.coroutines.** { *; }
-dontwarn io.ktor.**
-dontwarn kotlinx.coroutines.**

# Ktor uses reflection
-keepclassmembers class io.ktor.** { volatile <fields>; }
-keepclassmembers class io.ktor.client.** { volatile <fields>; }

# Ktor Android engine
-keep class io.ktor.client.engine.android.** { *; }

# ===========================
# ROOM
# ===========================
-keep class * extends androidx.room.RoomDatabase
-keep @androidx.room.Entity class *
-dontwarn androidx.room.paging.**

# Keep Room DAOs
-keep interface com.aura.tracking.data.room.*Dao { *; }
-keep class com.aura.tracking.data.room.*Dao_Impl { *; }

# ===========================
# COROUTINES
# ===========================
-keepnames class kotlinx.coroutines.internal.MainDispatcherFactory {}
-keepnames class kotlinx.coroutines.CoroutineExceptionHandler {}
-keepclassmembers class kotlinx.coroutines.** {
    volatile <fields>;
}

# ===========================
# DATA MODELS
# ===========================
# Keep all data model classes used with Supabase
-keep class com.aura.tracking.data.model.** { *; }
-keep class com.aura.tracking.data.room.** { *; }

# ===========================
# PLAY SERVICES
# ===========================
-keep class com.google.android.gms.** { *; }
-dontwarn com.google.android.gms.**

# ===========================
# GENERAL KOTLIN
# ===========================
-keep class kotlin.** { *; }
-keep class kotlin.Metadata { *; }
-dontwarn kotlin.**
-keepclassmembers class **$WhenMappings {
    <fields>;
}
-keepclassmembers class kotlin.Metadata {
    public <methods>;
}
