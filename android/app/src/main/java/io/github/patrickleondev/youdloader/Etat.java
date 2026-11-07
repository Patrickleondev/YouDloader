package io.github.patrickleondev.youdloader;

import android.os.Handler;
import android.os.Looper;

import java.util.List;
import java.util.concurrent.CopyOnWriteArrayList;

/**
 * État du téléchargement en cours, partagé entre le service (qui l'écrit depuis son fil
 * de travail) et l'écran (qui l'affiche). Les écouteurs sont toujours prévenus sur le fil
 * principal : ils peuvent toucher aux vues sans runOnUiThread.
 */
public final class Etat {

    public interface Ecouteur {
        void changement();
    }

    private static final Handler PRINCIPAL = new Handler(Looper.getMainLooper());
    private static final List<Ecouteur> ECOUTEURS = new CopyOnWriteArrayList<>();
    /** On garde la fin du journal seulement : une playlist de 200 vidéos en écrit beaucoup. */
    private static final int TAILLE_JOURNAL = 20000;

    private static final StringBuilder journal = new StringBuilder();
    private static volatile boolean occupe;
    /** 0 à 100, ou -1 quand on ne sait pas (préparation, fusion, découpe) */
    private static volatile float pourcentage = -1;
    private static volatile String message = "";

    private Etat() {
    }

    public static boolean occupe() {
        return occupe;
    }

    public static float pourcentage() {
        return pourcentage;
    }

    public static String message() {
        return message;
    }

    public static synchronized String journal() {
        return journal.toString();
    }

    public static void demarrer(String texte) {
        occupe = true;
        pourcentage = -1;
        message = texte;
        notifier();
    }

    public static void progres(float pct, String texte) {
        pourcentage = pct;
        message = texte;
        notifier();
    }

    public static void terminer(String texte) {
        occupe = false;
        pourcentage = -1;
        message = texte;
        notifier();
    }

    public static synchronized void ecrire(String ligne) {
        journal.append(ligne.trim()).append('\n');
        if (journal.length() > TAILLE_JOURNAL) {
            journal.delete(0, journal.length() - TAILLE_JOURNAL);
        }
        notifier();
    }

    public static void ecouter(Ecouteur e) {
        ECOUTEURS.add(e);
    }

    public static void oublier(Ecouteur e) {
        ECOUTEURS.remove(e);
    }

    private static void notifier() {
        PRINCIPAL.post(() -> {
            for (Ecouteur e : ECOUTEURS) e.changement();
        });
    }
}
