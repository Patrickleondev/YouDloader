package io.github.patrickleondev.youdloader;

import android.app.Application;
import android.content.Context;
import android.content.SharedPreferences;

import com.yausername.ffmpeg.FFmpeg;
import com.yausername.youtubedl_android.YoutubeDL;

import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * Prépare yt-dlp une fois pour toute l'appli.
 *
 * Au premier lancement, la bibliothèque décompresse Python et ffmpeg (une centaine de Mo) :
 * plusieurs secondes, donc jamais sur le fil principal. Tout ce qui touche à yt-dlp passe
 * ensuite par le même fil unique (FOND) : une mise à jour de yt-dlp ne peut ainsi jamais
 * remplacer le programme pendant qu'un téléchargement l'utilise.
 */
public class YouDloaderApp extends Application {

    private static final ExecutorService FOND = Executors.newSingleThreadExecutor();
    private static final CountDownLatch PRET = new CountDownLatch(1);
    private static volatile String erreurInit;

    /** YouTube change souvent ; yt-dlp suit. Une vérification par jour suffit. */
    private static final long INTERVALLE_MAJ = 24L * 3600 * 1000;

    @Override
    public void onCreate() {
        super.onCreate();
        FOND.execute(() -> {
            try {
                YoutubeDL.getInstance().init(this);
                FFmpeg.getInstance().init(this);
            } catch (Exception e) {
                erreurInit = e.getMessage();
                Etat.ecrire("[x] Préparation de yt-dlp impossible : " + e.getMessage());
            } finally {
                PRET.countDown();
            }
            if (erreurInit == null && majDue(this)) mettreAJour(this);
        });
    }

    /** Le fil où s'exécute tout ce qui touche à yt-dlp. */
    public static ExecutorService fond() {
        return FOND;
    }

    /** Bloque jusqu'à ce que yt-dlp soit prêt. À appeler depuis FOND uniquement. */
    public static void attendrePret() throws Exception {
        PRET.await();
        if (erreurInit != null) throw new IllegalStateException(erreurInit);
    }

    private static boolean majDue(Context c) {
        long derniere = prefs(c).getLong("derniere_maj", 0);
        return System.currentTimeMillis() - derniere > INTERVALLE_MAJ;
    }

    /** Met yt-dlp à jour depuis ses releases GitHub. À appeler depuis FOND uniquement. */
    public static void mettreAJour(Context c) {
        try {
            Etat.ecrire("Recherche d'une mise à jour de yt-dlp...");
            YoutubeDL.UpdateStatus statut =
                    YoutubeDL.getInstance().updateYoutubeDL(c, YoutubeDL.UpdateChannel._STABLE);
            prefs(c).edit().putLong("derniere_maj", System.currentTimeMillis()).apply();
            String version = YoutubeDL.getInstance().versionName(c);
            Etat.ecrire(statut == YoutubeDL.UpdateStatus.DONE
                    ? "yt-dlp mis à jour : " + version
                    : "yt-dlp est déjà à jour (" + version + ")");
        } catch (Exception e) {
            // Pas de réseau, GitHub injoignable : on garde la version actuelle et on réessaiera.
            Etat.ecrire("[!] Mise à jour de yt-dlp impossible : " + e.getMessage());
        }
    }

    public static SharedPreferences prefs(Context c) {
        return c.getSharedPreferences("youdloader", MODE_PRIVATE);
    }
}
