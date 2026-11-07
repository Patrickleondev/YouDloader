package io.github.patrickleondev.youdloader;

import com.yausername.youtubedl_android.YoutubeDLRequest;

import java.io.File;
import java.io.Serializable;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.regex.Pattern;

/**
 * Tout ce que l'utilisateur choisit, traduit en options yt-dlp.
 * C'est la même logique que Reglages et construire() dans youdloader/core.py,
 * pour que l'appli Android et la version de bureau donnent les mêmes fichiers.
 */
public class Reglages implements Serializable {

    /** Levée quand un réglage est incohérent : on prévient avant de lancer quoi que ce soit. */
    public static class Erreur extends Exception {
        public Erreur(String message) {
            super(message);
        }
    }

    public static final String[] CONTENEURS_VIDEO = {"mp4", "mkv", "webm"};
    public static final String[] CONTENEURS_AUDIO = {"m4a", "mp3", "opus", "wav"};
    /** 0 = la meilleure qualité disponible */
    public static final int[] HAUTEURS = {144, 240, 360, 480, 720, 1080, 1440, 2160, 0};

    public final ArrayList<String> urls = new ArrayList<>();
    public boolean audioSeul;
    public int hauteur = 360;
    public String conteneur = "mp4";
    public boolean sousTitres;
    public String langue = "fr";
    /** secondes ; -1 = pas de borne */
    public double debut = -1;
    public double fin = -1;
    public boolean coupePrecise = true;
    public boolean numeroter;
    /** éléments de playlist, ex. "1-5,8" ; vide = tous */
    public String elements = "";

    public boolean extrait() {
        return debut >= 0 || fin >= 0;
    }

    public void verifier() throws Erreur {
        if (urls.isEmpty()) throw new Erreur("Aucun lien à télécharger.");
        if (debut >= 0 && fin >= 0 && fin <= debut) {
            throw new Erreur("La fin (" + ecrireDuree(fin) + ") doit être après le début ("
                    + ecrireDuree(debut) + ").");
        }
        if (!elements.isEmpty() && !elements.matches("[\\d\\s,:\\-]+")) {
            throw new Erreur("« " + elements + " » n'est pas une liste d'éléments (ex. 1-5,8).");
        }
    }

    /** La requête complète pour yt-dlp : tous les liens d'un coup, pour que la numérotation suive. */
    public YoutubeDLRequest requete(File dossierTravail) {
        YoutubeDLRequest r = new YoutubeDLRequest(urls);

        if (audioSeul) {
            r.addOption("-f", "ba[ext=m4a]/ba/b");
            r.addOption("-S", "abr");
            r.addOption("-x");
            r.addOption("--audio-format", conteneur);
            r.addOption("--audio-quality", "0");
        } else {
            r.addOption("-f", "bv*+ba/b");
            // res:360 prend la plus haute résolution <= 360 et, s'il n'y en a aucune,
            // la plus basse au-dessus. Un filtre height<=360 échouerait dans ce cas.
            // vcodec:h264 : à résolution égale, H.264 plutôt qu'AV1. Beaucoup de téléphones
            // d'avant 2022 ne décodent pas l'AV1 : la vidéo ne se lirait pas, ou saccaderait.
            r.addOption("-S", (hauteur == 0 ? "res" : "res:" + hauteur) + ",vcodec:h264,ext:mp4:m4a");
            r.addOption("--merge-output-format", conteneur);
        }

        if (sousTitres) {
            r.addOption("--write-subs");
            r.addOption("--write-auto-subs");
            r.addOption("--sub-langs", langue);
            r.addOption("--convert-subs", "srt");
        }
        r.addOption("--embed-metadata");
        if (!elements.isEmpty()) r.addOption("-I", elements.replace(" ", ""));

        if (extrait()) {
            String de = debut >= 0 ? secondes(debut) : "0";
            String a = fin >= 0 ? secondes(fin) : "inf";
            r.addOption("--download-sections", "*" + de + "-" + a);
            // Sans ça, la coupe tombe sur l'image clé précédente : jusqu'à ~10 s de décalage.
            if (coupePrecise) r.addOption("--force-keyframes-at-cuts");
        }

        // Un lien qui échoue ne doit pas arrêter les suivants.
        r.addOption("--ignore-errors");
        // Les caractères : ? * " < > | posent problème sur les cartes SD et dans MediaStore.
        r.addOption("--windows-filenames");
        r.addOption("--no-mtime");
        // Chaque mise à jour de la progression sur sa propre ligne : l'appli les lit une à une.
        r.addOption("--newline");
        r.addOption("-o", dossierTravail.getAbsolutePath() + "/" + modeleNom());
        return r;
    }

    /**
     * Modèle de nom de fichier. Le "/" du sous-dossier de playlist reste hors du champ :
     * placé dedans, il serait nettoyé et on obtiendrait un seul nom de fichier à rallonge.
     */
    private String modeleNom() {
        String suffixe = audioSeul ? "(%(abr)dk)" : "(%(height)sp)";
        String numero = numeroter ? "%(autonumber)03d - " : "%(playlist_index&{:03d} - |)s";
        // Un extrait porte ses bornes dans le nom, sinon il écraserait la vidéo entière.
        String borne = extrait()
                ? " [%(section_start>%H-%M-%S|)s a %(section_end>%H-%M-%S|)s]" : "";
        return "%(playlist_title|)s/" + numero + "%(title)s" + suffixe + borne + ".%(ext)s";
    }

    private static String secondes(double s) {
        return String.format(Locale.US, "%.3f", s);
    }

    private static final Pattern DUREE = Pattern.compile("\\d+(\\.\\d+)?(:\\d{1,2}(\\.\\d+)?){0,2}");

    /**
     * "20", "20:30" ou "1:20:30" en secondes. Un nombre seul est lu comme des minutes :
     * c'est la façon dont on parle d'une vidéo (« à partir de la 20e minute »).
     */
    public static double lireDuree(String texte) throws Erreur {
        String t = texte == null ? "" : texte.trim().replace(',', '.');
        if (t.isEmpty()) throw new Erreur("Durée vide.");
        if (!DUREE.matcher(t).matches()) {
            throw new Erreur("« " + t + " » n'est pas une durée (attendu : 20, 20:30 ou 1:20:30).");
        }
        String[] p = t.split(":");
        List<Double> v = new ArrayList<>();
        for (String morceau : p) v.add(Double.parseDouble(morceau));
        if (v.size() == 1) return v.get(0) * 60;
        if (v.size() == 2) return v.get(0) * 60 + v.get(1);
        return v.get(0) * 3600 + v.get(1) * 60 + v.get(2);
    }

    public static String ecrireDuree(double secondes) {
        long s = Math.round(secondes);
        long h = s / 3600, m = (s % 3600) / 60;
        s = s % 60;
        return h > 0 ? String.format(Locale.FRANCE, "%d:%02d:%02d", h, m, s)
                : String.format(Locale.FRANCE, "%d:%02d", m, s);
    }
}
