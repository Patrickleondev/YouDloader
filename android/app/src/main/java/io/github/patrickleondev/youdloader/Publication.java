package io.github.patrickleondev.youdloader;

import android.content.ContentResolver;
import android.content.ContentValues;
import android.content.Context;
import android.media.MediaScannerConnection;
import android.net.Uri;
import android.os.Build;
import android.os.Environment;
import android.provider.MediaStore;
import android.webkit.MimeTypeMap;

import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

/**
 * Range les fichiers terminés dans Téléchargements/YouDloader, là où l'appli Fichiers,
 * la galerie et les lecteurs de musique les trouvent.
 *
 * yt-dlp travaille dans le dossier privé de l'appli : ffmpeg y fusionne et y découpe
 * librement, avec de vrais chemins de fichiers. Ce n'est qu'une fois un fichier fini
 * qu'on le copie vers le dossier public :
 * - Android 10 et plus : par MediaStore, sans aucune permission ;
 * - Android 8 et 9 : directement, avec la permission WRITE_EXTERNAL_STORAGE.
 */
public final class Publication {

    public static final String SOUS_DOSSIER = "YouDloader";

    private Publication() {
    }

    /** Le dossier de travail privé (pas de permission, effacé à la désinstallation). */
    public static File dossierTravail(Context c) {
        File d = new File(c.getExternalFilesDir(null), "travail");
        //noinspection ResultOfMethodCallIgnored
        d.mkdirs();
        return d;
    }

    /** Les fichiers encore en cours : yt-dlp reprend ces .part si on relance le même lien. */
    static boolean inacheve(File f) {
        String n = f.getName();
        return n.endsWith(".part") || n.endsWith(".ytdl") || n.contains(".part-Frag")
                || n.contains(".temp.") || n.endsWith(".temp");
    }

    /** Publie tous les fichiers finis du dossier de travail. Renvoie le nombre publié. */
    public static int toutPublier(Context c, File travail) {
        List<File> fichiers = new ArrayList<>();
        lister(travail, fichiers);
        int publies = 0;
        for (File f : fichiers) {
            if (inacheve(f)) continue;
            String sous = relatif(travail, f.getParentFile());
            try {
                publier(c, f, sous);
                //noinspection ResultOfMethodCallIgnored
                f.delete();
                publies++;
                Etat.ecrire("Enregistré : Téléchargements/" + SOUS_DOSSIER + "/"
                        + (sous.isEmpty() ? "" : sous + "/") + f.getName());
            } catch (IOException e) {
                Etat.ecrire("[x] " + f.getName() + " : " + e.getMessage());
            }
        }
        supprimerDossiersVides(travail, travail);
        return publies;
    }

    /** Efface ce qui reste dans le dossier de travail (téléchargements abandonnés). */
    public static long vider(Context c) {
        List<File> fichiers = new ArrayList<>();
        File travail = dossierTravail(c);
        lister(travail, fichiers);
        long octets = 0;
        for (File f : fichiers) {
            octets += f.length();
            //noinspection ResultOfMethodCallIgnored
            f.delete();
        }
        supprimerDossiersVides(travail, travail);
        return octets;
    }

    private static void publier(Context c, File f, String sous) throws IOException {
        String chemin = SOUS_DOSSIER + (sous.isEmpty() ? "" : "/" + sous);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            ContentResolver cr = c.getContentResolver();
            ContentValues v = new ContentValues();
            v.put(MediaStore.Downloads.DISPLAY_NAME, f.getName());
            v.put(MediaStore.Downloads.MIME_TYPE, typeMime(f));
            v.put(MediaStore.Downloads.RELATIVE_PATH, Environment.DIRECTORY_DOWNLOADS + "/" + chemin);
            // IS_PENDING : les autres applis ne voient pas le fichier tant qu'il est incomplet.
            v.put(MediaStore.Downloads.IS_PENDING, 1);
            Uri uri = cr.insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, v);
            if (uri == null) throw new IOException("MediaStore refuse le fichier");
            try (InputStream in = new FileInputStream(f); OutputStream out = cr.openOutputStream(uri)) {
                if (out == null) throw new IOException("écriture impossible");
                copier(in, out);
            } catch (IOException e) {
                cr.delete(uri, null, null);
                throw e;
            }
            v.clear();
            v.put(MediaStore.Downloads.IS_PENDING, 0);
            cr.update(uri, v, null, null);
        } else {
            File dossier = new File(Environment.getExternalStoragePublicDirectory(
                    Environment.DIRECTORY_DOWNLOADS), chemin);
            if (!dossier.isDirectory() && !dossier.mkdirs()) {
                throw new IOException("impossible de créer " + dossier);
            }
            File cible = new File(dossier, f.getName());
            try (InputStream in = new FileInputStream(f); OutputStream out = new FileOutputStream(cible)) {
                copier(in, out);
            }
            // Sans ça, la galerie ne verrait le fichier qu'au prochain redémarrage.
            MediaScannerConnection.scanFile(c, new String[]{cible.getAbsolutePath()}, null, null);
        }
    }

    private static String typeMime(File f) {
        String n = f.getName();
        int point = n.lastIndexOf('.');
        String ext = point < 0 ? "" : n.substring(point + 1).toLowerCase(Locale.ROOT);
        String type = MimeTypeMap.getSingleton().getMimeTypeFromExtension(ext);
        return type != null ? type : "application/octet-stream";
    }

    private static void copier(InputStream in, OutputStream out) throws IOException {
        byte[] tampon = new byte[256 * 1024];
        int lus;
        while ((lus = in.read(tampon)) != -1) out.write(tampon, 0, lus);
    }

    private static void lister(File dossier, List<File> sortie) {
        File[] contenu = dossier.listFiles();
        if (contenu == null) return;
        for (File f : contenu) {
            if (f.isDirectory()) lister(f, sortie);
            else sortie.add(f);
        }
    }

    private static String relatif(File racine, File dossier) {
        String r = racine.getAbsolutePath(), d = dossier.getAbsolutePath();
        return d.length() <= r.length() ? "" : d.substring(r.length() + 1);
    }

    private static void supprimerDossiersVides(File dossier, File racine) {
        File[] contenu = dossier.listFiles();
        if (contenu == null) return;
        for (File f : contenu) if (f.isDirectory()) supprimerDossiersVides(f, racine);
        contenu = dossier.listFiles();
        if (!dossier.equals(racine) && contenu != null && contenu.length == 0) {
            //noinspection ResultOfMethodCallIgnored
            dossier.delete();
        }
    }
}
