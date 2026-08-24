"""
Translations for the public-facing pages (/apply, /thanks).

The staff /admin dashboard is intentionally left English-only for now
(internal tool) -- see README if that changes later.

IMPORTANT: only visible label/option TEXT is translated here. The actual
form field `value` attributes stay in English in the templates, because
logic.py's scoring rules match against English strings (e.g.
holds_italian_passport == "Yes", highest_level_played == "International").
Translating a label's display text is safe; translating a `value` would
silently break scoring for Italian-language submissions. If you add a new
field, keep this in mind.
"""

TRANSLATIONS = {
    "en": {
        "header_tagline": "Talent Identification",
        "tag_apply": "Talent Pathway",

        "apply_intro": (
            "This is Federazione Cricket Italiana (FCRI)'s talent "
            "identification programme — how we find and track prospective "
            "players for Italian cricket, in Italy and overseas. It takes "
            "a few minutes: a couple of quick eligibility questions first, "
            "then a short profile of you and your cricket. Fields marked "
            "<strong>*</strong> are required — everything else helps us "
            "build a fuller picture but can be added later."
        ),

        "section_prescreen": "Quick eligibility check",
        "section_about_you": "About you",
        "section_your_cricket": "Your cricket",
        "section_evidence": "Evidence",
        "section_eligibility": "Eligibility (Italy)",
        "section_nomination": "Nomination",

        "prescreen_intro": (
            "Before the full form, a few quick questions to check there's a "
            "realistic pathway to representing Italy. If none of these apply "
            "to you right now, we're not able to take the registration "
            "further at this time."
        ),
        "prescreen_blocked_body": (
            "Thanks for your interest. Based on your answers, we don't "
            "currently see a pathway to Italian eligibility for you, so "
            "we're not able to proceed with a registration right now. If "
            "your circumstances change — for example your passport "
            "application progresses, or you become Italy-resident — you're "
            "welcome to come back and register then."
        ),

        "hero_heading": "Join the Talent Pathway",
        "step_eligibility": "Eligibility check",
        "step_profile": "Your profile",

        "photo_strip_heading": "Federazione Cricket Italiana in action",
        "photo_caption_bowling": "Men's national team",
        "photo_caption_batting": "Men's national team",
        "photo_caption_women": "Women's national team",
        "photo_caption_winners": "ICC Challenge League B champions",

        "eligibility_intro": (
            "We ask these questions to understand potential eligibility to "
            "represent Italy. This does not determine eligibility on its "
            "own — our staff review this manually."
        ),

        "label_full_name": "Full name *",
        "label_email": "Email *",
        "label_phone": "Phone",
        "hint_phone": "(with country code)",
        "label_dob": "Date of birth *",
        "label_country_residence": "Country of residence *",
        "placeholder_country_residence": "e.g. Italy, Australia, India",
        "label_city": "City",

        "label_primary_role": "Primary role *",
        "opt_select": "Select...",
        "opt_batter": "Batter",
        "opt_bowler": "Bowler",
        "opt_allrounder": "All-rounder",
        "opt_wk_batter": "Wicketkeeper-Batter",

        "label_batting_style": "Batting style",
        "opt_rh_bat": "Right-hand bat",
        "opt_lh_bat": "Left-hand bat",

        "label_bowling_style": "Bowling style",
        "placeholder_bowling_style": "e.g. Right-arm fast-medium, Left-arm orthodox",

        "label_current_club": "Current club *",
        "label_current_league": "Current league / competition",
        "label_highest_level": "Highest level played *",
        "opt_level_recreational": "Recreational/Club",
        "opt_level_premier": "Premier/State",
        "opt_level_firstclass": "First-Class/List A",
        "opt_level_international": "International",

        "label_years_playing": "Years playing competitively",
        "label_rep_honours": "Representative honours",
        "hint_rep_honours": "(rep teams, age-group squads, awards)",

        "label_scorecard_links": "Scorecard link(s)",
        "hint_scorecard_links": "(CricHQ, MyCricket, PlayCricket etc. — comma separated)",
        "label_video_links": "Video link(s)",
        "hint_video_links": "(YouTube, Google Drive etc. — comma separated)",
        "label_referee_name": "Referee / coach name",
        "label_referee_contact": "Referee / coach contact",

        "label_birthplace": "Country of birth *",
        "label_holds_passport": "Do you currently hold an Italian passport? *",
        "opt_yes": "Yes",
        "opt_no": "No",
        "opt_applied": "Applied",
        "opt_unsure": "Unsure",

        "label_italian_parent": "Do you have an Italian parent or grandparent?",
        "label_years_resident_italy": "Years resident in Italy (if any)",
        "label_current_citizenship": "Current citizenship(s)",

        "label_aire_number": "AIRE number",
        "hint_aire_number": "(Registry of Italians Residing Abroad — if registered)",
        "label_codice_fiscale": "Do you have a Codice Fiscale?",
        "hint_codice_fiscale": "(Italian tax identification number — we just need to know if you have one, not the number itself)",

        "label_visa_status": "Visa status",
        "hint_visa_status": "(if applicable, e.g. relocating for cricket)",
        "opt_visa_eu": "EU/Italian citizen",
        "opt_visa_noneu_required": "Non-EU — visa required",
        "opt_visa_noneu_held": "Non-EU — visa currently held",
        "opt_visa_na": "Not applicable",

        "label_nominated_by": "Who is submitting this? *",
        "opt_nom_self": "Self",
        "opt_nom_club": "Club",
        "opt_nom_coach": "Coach",
        "opt_nom_federation": "Federation contact",

        "label_nominator_name": "Nominator name",
        "hint_nominator_name": "(if not self)",
        "label_nominator_contact": "Nominator contact",

        "btn_submit": "Submit registration",

        "thanks_heading": "Thanks, {name}.",
        "thanks_received": (
            "Your registration has been received and logged with "
            "Federazione Cricket Italiana's talent identification programme."
        ),
        "thanks_incomplete_pct": "Your profile is {pct}% complete.",
        "thanks_incomplete_body": (
            "We'll follow up by email if anything further is needed — "
            "you're also welcome to send additional scorecards, video, or "
            "references any time by replying to our confirmation email."
        ),
        "thanks_complete_body": (
            "Your profile is complete. Our staff review new registrations "
            "regularly and will be in touch if there's a fit with our "
            "current needs."
        ),
        "thanks_reference": "Reference ID: #{id}",
    },

    "it": {
        "header_tagline": "Identificazione dei Talenti",
        "tag_apply": "Percorso Talenti",

        "apply_intro": (
            "Questo è il programma di identificazione dei talenti della "
            "Federazione Cricket Italiana (FCRI) — il modo in cui "
            "individuiamo e seguiamo i potenziali giocatori per il cricket "
            "italiano, in Italia e all'estero. Richiede pochi minuti: prima "
            "alcune rapide domande di idoneità, poi un breve profilo su di "
            "te e sul tuo cricket. I campi contrassegnati con "
            "<strong>*</strong> sono obbligatori — tutti gli altri ci "
            "aiutano a farci un'idea più completa, ma possono essere "
            "aggiunti in seguito."
        ),

        "section_prescreen": "Verifica rapida di idoneità",
        "section_about_you": "Su di te",
        "section_your_cricket": "Il tuo cricket",
        "section_evidence": "Documentazione",
        "section_eligibility": "Idoneità (Italia)",
        "section_nomination": "Segnalazione",

        "prescreen_intro": (
            "Prima del modulo completo, alcune domande rapide per verificare "
            "che ci sia un percorso realistico per rappresentare l'Italia. "
            "Se nessuna di queste condizioni ti riguarda al momento, non "
            "siamo in grado di proseguire con la registrazione."
        ),
        "prescreen_blocked_body": (
            "Grazie per il tuo interesse. In base alle tue risposte, al "
            "momento non vediamo un percorso di idoneità italiana per te, "
            "quindi non possiamo procedere con la registrazione. Se la tua "
            "situazione dovesse cambiare — ad esempio se la tua richiesta di "
            "passaporto va avanti, o diventi residente in Italia — sei il "
            "benvenuto a tornare e registrarti allora."
        ),

        "hero_heading": "Entra nel Percorso Talenti",
        "step_eligibility": "Verifica idoneità",
        "step_profile": "Il tuo profilo",

        "photo_strip_heading": "La Federazione Cricket Italiana in azione",
        "photo_caption_bowling": "Nazionale maschile",
        "photo_caption_batting": "Nazionale maschile",
        "photo_caption_women": "Nazionale femminile",
        "photo_caption_winners": "Campioni della ICC Challenge League B",

        "eligibility_intro": (
            "Facciamo queste domande per comprendere la potenziale idoneità "
            "a rappresentare l'Italia. Questo non determina l'idoneità da "
            "solo — il nostro staff esaminerà manualmente le informazioni."
        ),

        "label_full_name": "Nome completo *",
        "label_email": "Email *",
        "label_phone": "Telefono",
        "hint_phone": "(con prefisso internazionale)",
        "label_dob": "Data di nascita *",
        "label_country_residence": "Paese di residenza *",
        "placeholder_country_residence": "es. Italia, Australia, India",
        "label_city": "Città",

        "label_primary_role": "Ruolo principale *",
        "opt_select": "Seleziona...",
        "opt_batter": "Battitore",
        "opt_bowler": "Lanciatore",
        "opt_allrounder": "Tuttofare",
        "opt_wk_batter": "Wicketkeeper-Battitore",

        "label_batting_style": "Stile di battuta",
        "opt_rh_bat": "Destro",
        "opt_lh_bat": "Mancino",

        "label_bowling_style": "Stile di lancio",
        "placeholder_bowling_style": "es. Destro veloce-medio, Mancino ortodosso",

        "label_current_club": "Club attuale *",
        "label_current_league": "Campionato / competizione attuale",
        "label_highest_level": "Livello massimo raggiunto *",
        "opt_level_recreational": "Ricreativo/Club",
        "opt_level_premier": "Premier/Regionale",
        "opt_level_firstclass": "First-Class/List A",
        "opt_level_international": "Internazionale",

        "label_years_playing": "Anni di attività agonistica",
        "label_rep_honours": "Riconoscimenti rappresentativi",
        "hint_rep_honours": "(squadre rappresentative, selezioni giovanili, premi)",

        "label_scorecard_links": "Link ai tabellini",
        "hint_scorecard_links": "(CricHQ, MyCricket, PlayCricket ecc. — separati da virgola)",
        "label_video_links": "Link video",
        "hint_video_links": "(YouTube, Google Drive ecc. — separati da virgola)",
        "label_referee_name": "Nome allenatore / arbitro",
        "label_referee_contact": "Contatto allenatore / arbitro",

        "label_birthplace": "Paese di nascita *",
        "label_holds_passport": "Sei attualmente in possesso di un passaporto italiano? *",
        "opt_yes": "Sì",
        "opt_no": "No",
        "opt_applied": "Richiesto",
        "opt_unsure": "Non sono sicuro/a",

        "label_italian_parent": "Hai un genitore o un nonno italiano?",
        "label_years_resident_italy": "Anni di residenza in Italia (se applicabile)",
        "label_current_citizenship": "Cittadinanza/e attuale/i",

        "label_aire_number": "Numero AIRE",
        "hint_aire_number": "(Anagrafe degli Italiani Residenti all'Estero — se iscritto/a)",
        "label_codice_fiscale": "Hai un Codice Fiscale?",
        "hint_codice_fiscale": "(ci serve solo sapere se ne hai uno, non il codice stesso)",

        "label_visa_status": "Stato del visto",
        "hint_visa_status": "(se applicabile, es. trasferimento per il cricket)",
        "opt_visa_eu": "Cittadino UE/Italiano",
        "opt_visa_noneu_required": "Extra-UE — visto necessario",
        "opt_visa_noneu_held": "Extra-UE — visto già in possesso",
        "opt_visa_na": "Non applicabile",

        "label_nominated_by": "Chi sta inviando questa candidatura? *",
        "opt_nom_self": "Il giocatore stesso",
        "opt_nom_club": "Club",
        "opt_nom_coach": "Allenatore",
        "opt_nom_federation": "Contatto federale",

        "label_nominator_name": "Nome del segnalatore",
        "hint_nominator_name": "(se diverso dal giocatore)",
        "label_nominator_contact": "Contatto del segnalatore",

        "btn_submit": "Invia la registrazione",

        "thanks_heading": "Grazie, {name}.",
        "thanks_received": (
            "La tua registrazione è stata ricevuta e registrata nel "
            "programma di identificazione dei talenti della Federazione "
            "Cricket Italiana."
        ),
        "thanks_incomplete_pct": "Il tuo profilo è completo al {pct}%.",
        "thanks_incomplete_body": (
            "Ti ricontatteremo via email se servirà altro — puoi anche "
            "inviarci ulteriori tabellini, video o referenze in qualsiasi "
            "momento rispondendo alla nostra email di conferma."
        ),
        "thanks_complete_body": (
            "Il tuo profilo è completo. Il nostro staff esamina "
            "regolarmente le nuove registrazioni e ti contatterà se ci "
            "sarà una corrispondenza con le nostre esigenze attuali."
        ),
        "thanks_reference": "ID di riferimento: #{id}",
    },
}


def translate(key, lang="en"):
    lang_dict = TRANSLATIONS.get(lang, TRANSLATIONS["en"])
    return lang_dict.get(key, TRANSLATIONS["en"].get(key, key))
