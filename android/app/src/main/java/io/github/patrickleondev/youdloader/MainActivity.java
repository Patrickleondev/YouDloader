package io.github.patrickleondev.youdloader;

import android.Manifest;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.os.Build;
import android.os.Bundle;
import android.text.Editable;
import android.text.TextWatcher;
import android.view.MenuItem;
import android.view.View;
import android.widget.Button;
import android.widget.CheckBox;
import android.widget.EditText;
import android.widget.TextView;

import androidx.activity.EdgeToEdge;
import androidx.activity.result.ActivityResultLauncher;
import androidx.activity.result.contract.ActivityResultContracts;
import androidx.appcompat.app.AlertDialog;
import androidx.appcompat.app.AppCompatActivity;
import androidx.core.content.ContextCompat;
import androidx.core.graphics.Insets;
import androidx.core.view.ViewCompat;
import androidx.core.view.WindowInsetsCompat;

import com.google.android.material.appbar.MaterialToolbar;
import com.google.android.material.button.MaterialButtonToggleGroup;
import com.google.android.material.progressindicator.LinearProgressIndicator;
import com.google.android.material.textfield.MaterialAutoCompleteTextView;
import com.yausername.youtubedl_android.YoutubeDL;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * L'écran unique de YouDloader : on colle des liens, on choisit, on télécharge.
 * Le téléchargement lui-même vit dans TelechargementService ; cet écran ne fait que
 * remplir un objet Reglages et afficher l'Etat, comme gui.py sur le bureau.
 */
public class MainActivity extends AppCompatActivity implements Etat.Ecouteur {

    private static final Pattern URL = Pattern.compile("https?://\\S+");

    private EditText liens, debut, fin, langue, elements;
    private MaterialButtonToggleGroup mode;
    private MaterialAutoCompleteTextView qualite, format;
    private CheckBox extrait, precise, sousTitres, numeroter;
    private View blocExtrait;
    private Button telecharger, annuler;
    private LinearProgressIndicator progres;
    private TextView etat, journal;

    /** Réglages en attente pendant qu'Android demande les permissions. */
    private Reglages enAttente;

    private final ActivityResultLauncher<String[]> permissions = registerForActivityResult(
            new ActivityResultContracts.RequestMultiplePermissions(), this::apresPermissions);

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        EdgeToEdge.enable(this);
        setContentView(R.layout.activity_main);

        MaterialToolbar barre = findViewById(R.id.barre);
        setSupportActionBar(barre);
        // Android 15+ dessine sous les barres système : on décale le haut et le bas nous-mêmes.
        View defilement = findViewById(R.id.defilement);
        ViewCompat.setOnApplyWindowInsetsListener(findViewById(R.id.racine), (v, ins) -> {
            Insets b = ins.getInsets(WindowInsetsCompat.Type.systemBars()
                    | WindowInsetsCompat.Type.displayCutout());
            Insets clavier = ins.getInsets(WindowInsetsCompat.Type.ime());
            barre.setPadding(b.left, b.top, b.right, 0);
            defilement.setPadding(b.left, 0, b.right, Math.max(b.bottom, clavier.bottom));
            return WindowInsetsCompat.CONSUMED;
        });

        liens = findViewById(R.id.liens);
        mode = findViewById(R.id.mode);
        qualite = findViewById(R.id.qualite);
        format = findViewById(R.id.format);
        extrait = findViewById(R.id.extrait);
        blocExtrait = findViewById(R.id.bloc_extrait);
        debut = findViewById(R.id.debut);
        fin = findViewById(R.id.fin);
        precise = findViewById(R.id.precise);
        sousTitres = findViewById(R.id.sous_titres);
        langue = findViewById(R.id.langue);
        numeroter = findViewById(R.id.numeroter);
        elements = findViewById(R.id.elements);
        telecharger = findViewById(R.id.telecharger);
        annuler = findViewById(R.id.annuler);
        progres = findViewById(R.id.progres);
        etat = findViewById(R.id.etat);
        journal = findViewById(R.id.journal);

        restaurer();

        mode.addOnButtonCheckedListener((groupe, id, coche) -> {
            if (coche) remplirListes();
        });
        extrait.setOnCheckedChangeListener((b, coche) ->
                blocExtrait.setVisibility(coche ? View.VISIBLE : View.GONE));
        sousTitres.setOnCheckedChangeListener((b, coche) -> langue.setEnabled(coche));
        liens.addTextChangedListener(new TextWatcher() {
            @Override
            public void beforeTextChanged(CharSequence s, int a, int b, int c) {
            }

            @Override
            public void onTextChanged(CharSequence s, int a, int b, int c) {
            }

            @Override
            public void afterTextChanged(Editable s) {
                changement();
            }
        });

        findViewById(R.id.coller).setOnClickListener(v -> coller());
        findViewById(R.id.vider).setOnClickListener(v -> liens.setText(""));
        telecharger.setOnClickListener(v -> lancer());
        annuler.setOnClickListener(v -> TelechargementService.annuler(this));

        recevoirPartage(getIntent());
    }

    /** L'appli était déjà ouverte et on lui partage un nouveau lien (launchMode singleTop). */
    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        recevoirPartage(intent);
    }

    /** « Partager > YouDloader » depuis YouTube : le texte contient le lien, parfois avec un titre. */
    private void recevoirPartage(Intent intent) {
        if (intent == null || !Intent.ACTION_SEND.equals(intent.getAction())) return;
        String texte = intent.getStringExtra(Intent.EXTRA_TEXT);
        if (texte != null) ajouterLiens(texte);
        // Consommé : une rotation de l'écran ne doit pas l'ajouter une deuxième fois.
        intent.setAction(Intent.ACTION_MAIN);
    }

    private void ajouterLiens(String texte) {
        Matcher m = URL.matcher(texte);
        StringBuilder sb = new StringBuilder(liens.getText().toString().trim());
        while (m.find()) {
            // Partager deux fois la même vidéo ne doit pas la télécharger deux fois.
            if (sb.indexOf(m.group()) >= 0) continue;
            if (sb.length() > 0) sb.append('\n');
            sb.append(m.group());
        }
        liens.setText(sb);
        liens.setSelection(liens.length());
    }

    private void coller() {
        ClipboardManager cm = ContextCompat.getSystemService(this, ClipboardManager.class);
        ClipData clip = cm == null ? null : cm.getPrimaryClip();
        if (clip != null && clip.getItemCount() > 0) {
            CharSequence texte = clip.getItemAt(0).coerceToText(this);
            if (texte != null) ajouterLiens(texte.toString());
        }
    }

    // ------------------------------------------------------------------ listes déroulantes

    private boolean audio() {
        return mode.getCheckedButtonId() == R.id.mode_audio;
    }

    private void remplirListes() {
        SharedPreferences p = YouDloaderApp.prefs(this);
        boolean a = audio();
        String[] qualites;
        if (a) {
            qualites = new String[]{getString(R.string.meilleure)};
        } else {
            qualites = new String[Reglages.HAUTEURS.length];
            for (int i = 0; i < qualites.length; i++) {
                int h = Reglages.HAUTEURS[i];
                qualites[i] = h == 0 ? getString(R.string.meilleure) : h + "p";
            }
        }
        qualite.setSimpleItems(qualites);
        qualite.setText(a ? qualites[0] : p.getString("qualite_video", "360p"), false);

        String[] formats = a ? Reglages.CONTENEURS_AUDIO : Reglages.CONTENEURS_VIDEO;
        format.setSimpleItems(formats);
        format.setText(p.getString(a ? "format_audio" : "format_video", formats[0]), false);
    }

    // ------------------------------------------------------------------ réglages mémorisés

    private void restaurer() {
        SharedPreferences p = YouDloaderApp.prefs(this);
        mode.check(p.getBoolean("audio", false) ? R.id.mode_audio : R.id.mode_video);
        remplirListes();
        sousTitres.setChecked(p.getBoolean("sous_titres", false));
        langue.setText(p.getString("langue", "fr"));
        langue.setEnabled(sousTitres.isChecked());
        numeroter.setChecked(p.getBoolean("numeroter", false));
        precise.setChecked(p.getBoolean("precise", true));
    }

    private void memoriser() {
        boolean a = audio();
        SharedPreferences.Editor e = YouDloaderApp.prefs(this).edit()
                .putBoolean("audio", a)
                .putString(a ? "format_audio" : "format_video", format.getText().toString())
                .putBoolean("sous_titres", sousTitres.isChecked())
                .putString("langue", langue.getText().toString().trim())
                .putBoolean("numeroter", numeroter.isChecked())
                .putBoolean("precise", precise.isChecked());
        if (!a) e.putString("qualite_video", qualite.getText().toString());
        e.apply();
    }

    @Override
    protected void onPause() {
        super.onPause();
        memoriser();
    }

    // ------------------------------------------------------------------ lancement

    private Reglages rassembler() throws Reglages.Erreur {
        Reglages r = new Reglages();
        for (String ligne : liens.getText().toString().split("\\s+")) {
            String l = ligne.trim();
            if (!l.isEmpty() && !l.startsWith("#")) r.urls.add(l);
        }
        r.audioSeul = audio();
        String q = qualite.getText().toString();
        r.hauteur = q.endsWith("p") ? Integer.parseInt(q.substring(0, q.length() - 1)) : 0;
        r.conteneur = format.getText().toString();
        r.sousTitres = sousTitres.isChecked();
        r.langue = langue.getText().toString().trim().isEmpty() ? "fr" : langue.getText().toString().trim();
        r.numeroter = numeroter.isChecked();
        r.elements = elements.getText().toString().trim();
        if (extrait.isChecked()) {
            String de = debut.getText().toString(), a = fin.getText().toString();
            if (de.trim().isEmpty() && a.trim().isEmpty()) {
                throw new Reglages.Erreur("Indique au moins le début ou la fin du passage.");
            }
            if (!de.trim().isEmpty()) r.debut = Reglages.lireDuree(de);
            if (!a.trim().isEmpty()) r.fin = Reglages.lireDuree(a);
            r.coupePrecise = precise.isChecked();
        }
        r.verifier();
        return r;
    }

    private void lancer() {
        Reglages r;
        try {
            r = rassembler();
        } catch (Reglages.Erreur e) {
            new AlertDialog.Builder(this)
                    .setTitle("Réglage à corriger")
                    .setMessage(e.getMessage())
                    .setPositiveButton(android.R.string.ok, null)
                    .show();
            return;
        }
        memoriser();

        // Notification (Android 13+) et stockage (Android 8 et 9) : demandés au moment
        // où on en a besoin, pas au démarrage.
        List<String> manquantes = new ArrayList<>();
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU && !accordee(Manifest.permission.POST_NOTIFICATIONS)) {
            manquantes.add(Manifest.permission.POST_NOTIFICATIONS);
        }
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.Q && !accordee(Manifest.permission.WRITE_EXTERNAL_STORAGE)) {
            manquantes.add(Manifest.permission.WRITE_EXTERNAL_STORAGE);
        }
        if (manquantes.isEmpty()) {
            TelechargementService.lancer(this, r);
        } else {
            enAttente = r;
            permissions.launch(manquantes.toArray(new String[0]));
        }
    }

    private boolean accordee(String permission) {
        return ContextCompat.checkSelfPermission(this, permission) == PackageManager.PERMISSION_GRANTED;
    }

    private void apresPermissions(Map<String, Boolean> resultat) {
        Reglages r = enAttente;
        enAttente = null;
        if (r == null) return;
        // Refuser les notifications n'empêche rien : on ne verra simplement pas la progression
        // hors de l'appli. Le stockage, lui, est indispensable sur Android 8 et 9.
        if (Boolean.FALSE.equals(resultat.get(Manifest.permission.WRITE_EXTERNAL_STORAGE))) {
            new AlertDialog.Builder(this)
                    .setMessage(R.string.permission_stockage)
                    .setPositiveButton(android.R.string.ok, null)
                    .show();
            return;
        }
        TelechargementService.lancer(this, r);
    }

    // ------------------------------------------------------------------ affichage de l'état

    @Override
    protected void onStart() {
        super.onStart();
        Etat.ecouter(this);
        changement();
    }

    @Override
    protected void onStop() {
        super.onStop();
        Etat.oublier(this);
    }

    /** Appelé par Etat sur le fil principal à chaque nouvelle ligne ou progression. */
    @Override
    public void changement() {
        boolean occupe = Etat.occupe();
        telecharger.setEnabled(!occupe && !liens.getText().toString().trim().isEmpty());
        annuler.setEnabled(occupe);

        float pct = Etat.pourcentage();
        if (occupe && pct < 0) {
            if (!progres.isIndeterminate()) {
                progres.setVisibility(View.INVISIBLE);
                progres.setIndeterminate(true);
                progres.setVisibility(View.VISIBLE);
            }
        } else {
            progres.setIndeterminate(false);
            progres.setProgressCompat(occupe ? Math.round(pct) : 0, true);
        }
        String m = Etat.message();
        etat.setText(m.isEmpty() ? getString(R.string.pret) : m);
        // Seulement les dernières lignes : le reste est le passé, et il faudrait défiler pour voir le présent.
        String j = Etat.journal();
        int debutFin = j.length();
        for (int n = 0; n < 40 && debutFin > 0; n++) debutFin = j.lastIndexOf('\n', debutFin - 2) + 1;
        String fin = j.substring(Math.max(0, debutFin));
        if (!fin.contentEquals(journal.getText())) journal.setText(fin);
    }

    // ------------------------------------------------------------------ menu

    @Override
    public boolean onCreateOptionsMenu(android.view.Menu menu) {
        getMenuInflater().inflate(R.menu.principal, menu);
        return true;
    }

    @Override
    public boolean onOptionsItemSelected(MenuItem item) {
        int id = item.getItemId();
        if (id == R.id.menu_maj) {
            // Sur le fil de yt-dlp : attend la fin d'un téléchargement en cours.
            YouDloaderApp.fond().execute(() -> {
                try {
                    YouDloaderApp.attendrePret();
                    YouDloaderApp.mettreAJour(getApplicationContext());
                } catch (Exception e) {
                    Etat.ecrire("[x] " + e.getMessage());
                }
            });
            return true;
        }
        if (id == R.id.menu_vider) {
            if (Etat.occupe()) {
                Etat.ecrire("[!] Attends la fin du téléchargement pour effacer.");
            } else {
                long octets = Publication.vider(this);
                Etat.ecrire(String.format(Locale.FRANCE, "Fichiers inachevés effacés : %.1f Mo libérés",
                        octets / 1e6));
            }
            return true;
        }
        if (id == R.id.menu_versions) {
            String appli;
            try {
                appli = getPackageManager().getPackageInfo(getPackageName(), 0).versionName;
            } catch (PackageManager.NameNotFoundException e) {
                appli = "?";
            }
            String versionAppli = appli;
            YouDloaderApp.fond().execute(() -> {
                try {
                    YouDloaderApp.attendrePret();
                    String v = YoutubeDL.getInstance().versionName(getApplicationContext());
                    if (v == null) v = YoutubeDL.getInstance().version(getApplicationContext());
                    Etat.ecrire("YouDloader " + versionAppli + ", yt-dlp " + v);
                } catch (Exception e) {
                    Etat.ecrire("[x] " + e.getMessage());
                }
            });
            return true;
        }
        return super.onOptionsItemSelected(item);
    }
}
