package io.github.patrickleondev.youdloader;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.content.pm.ServiceInfo;
import android.os.Build;
import android.os.IBinder;
import android.os.SystemClock;

import androidx.core.app.NotificationCompat;
import androidx.core.app.NotificationManagerCompat;
import androidx.core.app.ServiceCompat;
import androidx.core.content.ContextCompat;
import androidx.core.content.IntentCompat;

import com.yausername.youtubedl_android.YoutubeDL;
import com.yausername.youtubedl_android.YoutubeDLResponse;

import java.io.File;
import java.util.ArrayDeque;
import java.util.Deque;
import java.util.Locale;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

import kotlin.Unit;

/**
 * Lance yt-dlp et le garde en vie écran éteint.
 *
 * Service au premier plan de type dataSync : Android ne le tue pas tant que la
 * notification est affichée. Il ne tourne que pendant un téléchargement
 * (START_NOT_STICKY, stopSelf à la fin) ; le bouton Annuler de la notification l'arrête.
 */
public class TelechargementService extends Service {

    public static final String ACTION_LANCER = "lancer";
    public static final String ACTION_ANNULER = "annuler";
    public static final String EXTRA_REGLAGES = "reglages";

    private static final String CANAL = "telechargements";
    private static final int NOTIF_EN_COURS = 1;
    private static final int NOTIF_FIN = 2;
    private static final String PROCESSUS = "youdloader";

    private volatile boolean annule;
    /** Les dernières lignes de yt-dlp, pour expliquer un échec. */
    private final Deque<String> dernieres = new ArrayDeque<>();
    private long derniereNotif;

    public static void lancer(Context c, Reglages r) {
        Intent i = new Intent(c, TelechargementService.class)
                .setAction(ACTION_LANCER).putExtra(EXTRA_REGLAGES, r);
        ContextCompat.startForegroundService(c, i);
    }

    public static void annuler(Context c) {
        c.startService(new Intent(c, TelechargementService.class).setAction(ACTION_ANNULER));
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        if (intent != null && ACTION_ANNULER.equals(intent.getAction())) {
            if (!Etat.occupe()) {
                stopSelf();
                return START_NOT_STICKY;
            }
            annule = true;
            Etat.progres(-1, "Annulation...");
            YoutubeDL.getInstance().destroyProcessById(PROCESSUS);
            return START_NOT_STICKY;
        }

        Reglages r = intent == null ? null
                : IntentCompat.getSerializableExtra(intent, EXTRA_REGLAGES, Reglages.class);
        creerCanal();
        // startForeground doit être appelé tout de suite, même si on s'arrête juste après :
        // Android tue l'appli si un service lancé par startForegroundService ne le fait pas.
        ServiceCompat.startForeground(this, NOTIF_EN_COURS, notification("Préparation...", -1),
                Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q
                        ? ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC : 0);
        if (r == null || Etat.occupe()) {
            if (!Etat.occupe()) arreter();
            return START_NOT_STICKY;
        }

        annule = false;
        // Le bilan du téléchargement précédent n'a plus lieu d'être.
        NotificationManagerCompat.from(this).cancel(NOTIF_FIN);
        Etat.demarrer("Préparation de yt-dlp...");
        Etat.ecrire("--- " + r.urls.size() + " lien(s)" + (r.extrait()
                ? ", extrait " + Reglages.ecrireDuree(Math.max(r.debut, 0)) + " -> "
                + (r.fin >= 0 ? Reglages.ecrireDuree(r.fin) : "fin") : ""));
        YouDloaderApp.fond().execute(() -> telecharger(r));
        return START_NOT_STICKY;
    }

    /** Exécuté sur le fil de yt-dlp (YouDloaderApp.fond), jamais sur le fil principal. */
    private void telecharger(Reglages r) {
        File travail = Publication.dossierTravail(this);
        String bilan;
        boolean succes = false;
        try {
            YouDloaderApp.attendrePret();
            // Annulé pendant la préparation : yt-dlp n'a pas encore de processus à arrêter.
            if (annule) throw new InterruptedException();
            Etat.progres(-1, "Analyse des liens...");
            // redirectErrorStream = true : les avertissements et erreurs de yt-dlp arrivent
            // aussi dans le journal, au fil de l'eau.
            YoutubeDLResponse reponse = YoutubeDL.getInstance().execute(
                    r.requete(travail), PROCESSUS, true,
                    (pct, eta, ligne) -> {
                        surLigne(pct, eta, ligne);
                        return Unit.INSTANCE;
                    });
            succes = reponse.getExitCode() == 0;
            bilan = succes ? "Terminé" : "Terminé, mais au moins un lien a échoué";
        } catch (YoutubeDL.CanceledException e) {
            bilan = "Annulé";
        } catch (Exception e) {
            bilan = annule ? "Annulé" : "Échec";
            if (!annule) {
                for (String l : dernieres) {
                    if (l.startsWith("ERROR") || l.startsWith("WARNING")) Etat.ecrire("[x] " + l);
                }
                if (e.getMessage() != null && !e.getMessage().trim().isEmpty()) {
                    Etat.ecrire("[x] " + e.getMessage().trim());
                }
            }
        }

        // Même après un échec ou une annulation, les vidéos déjà finies sont gardées.
        int publies = Publication.toutPublier(this, travail);
        String texte = bilan + " : " + publies + " fichier(s) dans Téléchargements/"
                + Publication.SOUS_DOSSIER;
        Etat.ecrire("--- " + texte);
        Etat.terminer(texte);
        notifierFin(texte, succes);
        arreter();
    }

    /** "[download]  12.3% of ~ 1.20GiB at 2.00MiB/s ETA Unknown (frag 4/123)" */
    private static final Pattern POURCENT = Pattern.compile("^\\[download\\]\\s+(\\d+(?:\\.\\d+)?)%");

    private void surLigne(float pctBiblio, long eta, String ligne) {
        String l = ligne.trim();
        if (l.isEmpty()) return;
        // La bibliothèque ne reconnaît que "ETA mm:ss". En mode fragmenté (HLS, souvent
        // au-dessus de 1080p), yt-dlp écrit "ETA Unknown" : on lit le pourcentage nous-mêmes.
        Matcher m = POURCENT.matcher(l);
        boolean progression = m.find();
        float pct = progression ? Float.parseFloat(m.group(1)) : pctBiblio;
        if (!progression) {
            Etat.ecrire(l);
            synchronized (dernieres) {
                dernieres.addLast(l);
                if (dernieres.size() > 15) dernieres.removeFirst();
            }
        }
        if (l.startsWith("[Merger]") || l.startsWith("[ExtractAudio]")
                || l.startsWith("[ffmpeg]") || l.startsWith("[download] Destination")) {
            Etat.progres(-1, etape(l));
        } else if (progression) {
            String texte = String.format(Locale.FRANCE, "%.0f %%", pct)
                    + (eta > 0 ? "  ·  reste " + Reglages.ecrireDuree(eta) : "");
            Etat.progres(pct, texte);
        }
        // La notification n'a pas besoin de plus de deux mises à jour par seconde.
        long maintenant = SystemClock.elapsedRealtime();
        if (maintenant - derniereNotif > 500) {
            derniereNotif = maintenant;
            NotificationManagerCompat nm = NotificationManagerCompat.from(this);
            if (nm.areNotificationsEnabled()) {
                try {
                    nm.notify(NOTIF_EN_COURS, notification(Etat.message(), Etat.pourcentage()));
                } catch (SecurityException ignore) {
                    // permission de notification retirée entre-temps : rien de grave
                }
            }
        }
    }

    private static String etape(String ligne) {
        if (ligne.startsWith("[Merger]")) return "Fusion de l'image et du son...";
        if (ligne.startsWith("[ExtractAudio]")) return "Conversion de l'audio...";
        if (ligne.startsWith("[ffmpeg]")) return "Découpe de l'extrait...";
        String nom = ligne.substring(ligne.lastIndexOf('/') + 1);
        return "Téléchargement : " + nom;
    }

    private Notification notification(String texte, float pct) {
        PendingIntent ouvrir = PendingIntent.getActivity(this, 0,
                new Intent(this, MainActivity.class).addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP),
                PendingIntent.FLAG_IMMUTABLE);
        PendingIntent stop = PendingIntent.getService(this, 1,
                new Intent(this, TelechargementService.class).setAction(ACTION_ANNULER),
                PendingIntent.FLAG_IMMUTABLE);
        return new NotificationCompat.Builder(this, CANAL)
                .setSmallIcon(R.drawable.ic_notif)
                .setContentTitle(getString(R.string.notif_titre))
                .setContentText(texte)
                .setProgress(100, Math.max(0, Math.round(pct)), pct < 0)
                .setOngoing(true)
                .setOnlyAlertOnce(true)
                .setContentIntent(ouvrir)
                .addAction(0, getString(R.string.annuler), stop)
                .setForegroundServiceBehavior(NotificationCompat.FOREGROUND_SERVICE_IMMEDIATE)
                .build();
    }

    private void notifierFin(String texte, boolean succes) {
        NotificationManagerCompat nm = NotificationManagerCompat.from(this);
        if (!nm.areNotificationsEnabled()) return;
        PendingIntent ouvrir = PendingIntent.getActivity(this, 0,
                new Intent(this, MainActivity.class).addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP),
                PendingIntent.FLAG_IMMUTABLE);
        try {
            nm.notify(NOTIF_FIN, new NotificationCompat.Builder(this, CANAL)
                    .setSmallIcon(R.drawable.ic_notif)
                    .setContentTitle(getString(succes ? R.string.notif_fini : R.string.notif_titre))
                    .setContentText(texte)
                    .setAutoCancel(true)
                    .setContentIntent(ouvrir)
                    .build());
        } catch (SecurityException ignore) {
            // pas de permission : le bilan reste visible dans l'appli
        }
    }

    private void creerCanal() {
        NotificationChannel canal = new NotificationChannel(CANAL,
                getString(R.string.canal_nom), NotificationManager.IMPORTANCE_LOW);
        canal.setDescription(getString(R.string.canal_description));
        getSystemService(NotificationManager.class).createNotificationChannel(canal);
    }

    private void arreter() {
        ServiceCompat.stopForeground(this, ServiceCompat.STOP_FOREGROUND_REMOVE);
        stopSelf();
    }

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }
}
