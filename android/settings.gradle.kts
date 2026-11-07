pluginManagement {
    repositories {
        google {
            content {
                includeGroupByRegex("com\\.android.*")
                includeGroupByRegex("com\\.google.*")
                includeGroupByRegex("androidx.*")
            }
        }
        mavenCentral()
        gradlePluginPortal()
    }
}
dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        google()
        // youtubedl-android (Python, yt-dlp, ffmpeg et QuickJS pour Android) est sur Maven Central
        mavenCentral()
    }
}

rootProject.name = "YouDloader"
include(":app")
