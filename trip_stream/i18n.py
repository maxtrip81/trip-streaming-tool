"""Bilingual (Italian / English) user interface strings."""

from __future__ import annotations

LANGUAGES = {"it": "Italiano", "en": "English"}

_STRINGS = {
    # --- general --------------------------------------------------------
    "app.tagline": ("Broadcast live audio, simply", "Trasmetti audio dal vivo, semplicemente"),
    "btn.connect": ("Start streaming", "Avvia streaming"),
    "btn.disconnect": ("Stop streaming", "Ferma streaming"),
    "btn.record": ("Start / stop recording", "Avvia / ferma registrazione"),
    "btn.settings": ("Settings", "Impostazioni"),
    "btn.mixer": ("Mixer", "Mixer"),
    "btn.info": ("Stream info", "Info stream"),
    "btn.update_song": ("Update", "Aggiorna"),
    "btn.add": ("Add", "Aggiungi"),
    "btn.edit": ("Edit", "Modifica"),
    "btn.delete": ("Delete", "Elimina"),
    "btn.ok": ("OK", "OK"),
    "btn.cancel": ("Cancel", "Annulla"),
    "btn.close": ("Close", "Chiudi"),
    "btn.save": ("Save", "Salva"),
    "btn.browse": ("Browse…", "Sfoglia…"),
    "btn.import": ("Import config…", "Importa configurazione…"),
    "btn.export": ("Export config…", "Esporta configurazione…"),
    "btn.refresh": ("Refresh devices", "Aggiorna dispositivi"),
    "btn.reset": ("Reset", "Azzera"),
    "btn.split": ("Split file now", "Dividi file ora"),
    "btn.clear_log": ("Clear log", "Pulisci log"),
    "btn.about": ("About", "Informazioni"),
    "btn.mute": ("Mute", "Muto"),

    # --- LCD / status -----------------------------------------------------
    "lcd.idle": ("idle", "in attesa"),
    "lcd.connecting": ("connecting…", "connessione…"),
    "lcd.connected": ("streaming", "in onda"),
    "lcd.reconnecting": ("reconnecting…", "riconnessione…"),
    "lcd.error": ("error", "errore"),
    "lcd.recording": ("recording", "registrazione"),
    "lcd.sent": ("sent", "inviati"),
    "lcd.no_server": ("no server", "nessun server"),
    "lcd.servers": ("{n} server(s)", "{n} server"),
    "status.connected": ("Connected", "Connesso"),
    "status.disconnected": ("Disconnected", "Disconnesso"),

    # --- main window ------------------------------------------------------
    "main.song": ("Song", "Brano"),
    "main.song_placeholder": ("Artist - Title", "Artista - Titolo"),
    "main.primary": ("Primary", "Primario"),
    "main.secondary": ("Secondary", "Secondario"),
    "main.master": ("Master", "Master"),
    "main.vu_tooltip": ("Input level (dBFS)", "Livello di ingresso (dBFS)"),

    # --- settings tabs ----------------------------------------------------
    "settings.title": ("Settings", "Impostazioni"),
    "tab.main": ("Main", "Principale"),
    "tab.audio": ("Audio", "Audio"),
    "tab.stream": ("Stream", "Stream"),
    "tab.record": ("Record", "Registrazione"),
    "tab.dsp": ("DSP", "DSP"),
    "tab.advanced": ("Advanced", "Avanzate"),
    "tab.gui": ("Interface", "Interfaccia"),
    "tab.log": ("Log", "Log"),

    # --- main tab ---------------------------------------------------------
    "main.servers": ("Servers", "Server"),
    "main.servers_hint": ("Checked servers are used when streaming starts (multiple at once is possible).",
                          "I server spuntati vengono usati all'avvio dello streaming (anche più di uno contemporaneamente)."),
    "main.icy": ("Stream info (ICY)", "Informazioni stream (ICY)"),
    "main.icy_edit": ("Edit stream info…", "Modifica info stream…"),
    "main.config": ("Configuration", "Configurazione"),
    "main.connect_startup": ("Connect at startup", "Connetti all'avvio"),

    # --- server dialog ----------------------------------------------------
    "server.title": ("Server", "Server"),
    "server.name": ("Name", "Nome"),
    "server.type": ("Type", "Tipo"),
    "server.host": ("Address", "Indirizzo"),
    "server.port": ("Port", "Porta"),
    "server.password": ("Password", "Password"),
    "server.mount": ("Mountpoint", "Mountpoint"),
    "server.user": ("User", "Utente"),
    "server.tls": ("Use SSL/TLS", "Usa SSL/TLS"),
    "server.tls_verify": ("Verify certificate", "Verifica certificato"),
    "server.protocol": ("Icecast protocol", "Protocollo Icecast"),
    "server.protocol_put": ("HTTP PUT (Icecast ≥ 2.4)", "HTTP PUT (Icecast ≥ 2.4)"),
    "server.protocol_source": ("SOURCE (legacy)", "SOURCE (legacy)"),
    "server.sid": ("Stream ID (SHOUTcast v2)", "Stream ID (SHOUTcast v2)"),
    "server.whip_url": ("WHIP endpoint URL", "URL endpoint WHIP"),
    "server.whip_token": ("Bearer token", "Bearer token"),
    "server.whip_hint": ("WebRTC always uses Opus 48 kHz, independent of the stream codec.",
                         "WebRTC usa sempre Opus 48 kHz, indipendentemente dal codec dello stream."),
    "server.name_required": ("Please enter a name.", "Inserisci un nome."),
    "server.delete_confirm": ("Delete server \"{name}\"?", "Eliminare il server \"{name}\"?"),

    # --- ICY dialog -------------------------------------------------------
    "icy.title": ("Stream info", "Informazioni stream"),
    "icy.name": ("Name", "Nome"),
    "icy.description": ("Description", "Descrizione"),
    "icy.genre": ("Genre", "Genere"),
    "icy.url": ("Website", "Sito web"),
    "icy.irc": ("IRC", "IRC"),
    "icy.icq": ("ICQ", "ICQ"),
    "icy.aim": ("AIM", "AIM"),
    "icy.public": ("List on public directory", "Pubblica nella directory"),

    # --- audio tab --------------------------------------------------------
    "audio.primary": ("Primary audio device", "Dispositivo audio primario"),
    "audio.secondary": ("Secondary audio device (mixed in)", "Dispositivo audio secondario (miscelato)"),
    "audio.device": ("Device", "Dispositivo"),
    "audio.default": ("System default", "Predefinito di sistema"),
    "audio.none": ("None (disabled)", "Nessuno (disattivato)"),
    "audio.tone": ("Test tone 440 Hz", "Tono di prova 440 Hz"),
    "audio.left": ("Left channel", "Canale sinistro"),
    "audio.right": ("Right channel", "Canale destro"),
    "audio.format": ("Format", "Formato"),
    "audio.samplerate": ("Sample rate", "Frequenza di campionamento"),
    "audio.channels": ("Channels", "Canali"),
    "audio.mono": ("Mono", "Mono"),
    "audio.stereo": ("Stereo", "Stereo"),
    "audio.buffer": ("Buffer (ms)", "Buffer (ms)"),
    "audio.routing_hint": ("TRIP does not play files itself: to stream music from a player, route it with "
                           "Voicemeeter (Windows), BlackHole (macOS) or PipeWire/JACK/PulseAudio monitor (Linux).",
                           "TRIP non riproduce file da solo: per trasmettere musica da un player instradala con "
                           "Voicemeeter (Windows), BlackHole (macOS) o PipeWire/JACK/monitor PulseAudio (Linux)."),
    "audio.channel_n": ("Channel {n}", "Canale {n}"),

    # --- stream tab -------------------------------------------------------
    "stream.codec": ("Stream codec", "Codec stream"),
    "stream.bitrate": ("Bitrate (kbit/s)", "Bitrate (kbit/s)"),
    "stream.aac_profile": ("AAC profile", "Profilo AAC"),
    "stream.song": ("Song update", "Aggiornamento brano"),
    "stream.song_file": ("Update song from file", "Aggiorna brano da file"),
    "stream.song_line": ("Line to read", "Riga da leggere"),
    "stream.first_line": ("First line", "Prima riga"),
    "stream.last_line": ("Last line", "Ultima riga"),
    "stream.song_app": ("Update song from music app", "Aggiorna brano dall'app musicale"),
    "stream.song_app_hint": ("Music/Spotify on macOS, any MPRIS player via playerctl on Linux.",
                             "Musica/Spotify su macOS, qualsiasi player MPRIS tramite playerctl su Linux."),
    "stream.prefix": ("Prefix", "Prefisso"),
    "stream.suffix": ("Suffix", "Suffisso"),
    "stream.delay": ("Update delay (s)", "Ritardo aggiornamento (s)"),
    "stream.signal": ("Signal / silence detection", "Rilevamento segnale / silenzio"),
    "stream.start_signal": ("Start streaming after signal for (s)", "Avvia streaming dopo segnale per (s)"),
    "stream.stop_silence": ("Stop streaming after silence for (s)", "Ferma streaming dopo silenzio per (s)"),
    "stream.reconnect": ("Reconnect automatically", "Riconnetti automaticamente"),
    "stream.reconnect_delay": ("Retry delay (s)", "Attesa tra i tentativi (s)"),
    "stream.reconnect_max": ("Max retries (0 = forever)", "Tentativi massimi (0 = infiniti)"),
    "stream.connection": ("Connection", "Connessione"),

    # --- record tab -------------------------------------------------------
    "record.codec": ("Recording codec", "Codec registrazione"),
    "record.folder": ("Folder", "Cartella"),
    "record.filename": ("File name", "Nome file"),
    "record.filename_hint": ("Variables: %Y year, %m month, %d day, %H hour, %M minute, %S second, %i file index",
                             "Variabili: %Y anno, %m mese, %d giorno, %H ora, %M minuti, %S secondi, %i indice file"),
    "record.split": ("Split file every (min, 0 = off)", "Dividi file ogni (min, 0 = no)"),
    "record.split_sync": ("Sync split to the clock", "Sincronizza divisione all'orologio"),
    "record.start_connect": ("Start recording when connected", "Avvia registrazione alla connessione"),
    "record.stop_disconnect": ("Stop recording when disconnected", "Ferma registrazione alla disconnessione"),
    "record.start_signal": ("Start recording after signal for (s)", "Avvia registrazione dopo segnale per (s)"),
    "record.stop_silence": ("Stop recording after silence for (s)", "Ferma registrazione dopo silenzio per (s)"),
    "record.choose_folder": ("Choose recording folder", "Scegli cartella di registrazione"),

    # --- detection --------------------------------------------------------
    "detect.threshold": ("Signal threshold (dBFS)", "Soglia segnale (dBFS)"),

    # --- DSP tab ----------------------------------------------------------
    "dsp.eq": ("10-band equalizer", "Equalizzatore a 10 bande"),
    "dsp.eq_enable": ("Enable equalizer", "Attiva equalizzatore"),
    "dsp.preset": ("Preset", "Preset"),
    "dsp.comp": ("Compressor", "Compressore"),
    "dsp.comp_enable": ("Enable compressor", "Attiva compressore"),
    "dsp.threshold": ("Threshold (dB)", "Soglia (dB)"),
    "dsp.ratio": ("Ratio", "Rapporto"),
    "dsp.attack": ("Attack (ms)", "Attacco (ms)"),
    "dsp.release": ("Release (ms)", "Rilascio (ms)"),
    "dsp.makeup": ("Makeup gain (dB)", "Guadagno di compensazione (dB)"),
    "dsp.apply_stream": ("Apply to stream", "Applica allo stream"),
    "dsp.apply_record": ("Apply to recording", "Applica alla registrazione"),
    "preset.flat": ("Flat", "Piatto"),
    "preset.voice": ("Voice", "Voce"),
    "preset.bass": ("Bass boost", "Bassi potenziati"),
    "preset.treble": ("Treble boost", "Alti potenziati"),
    "preset.loudness": ("Loudness", "Loudness"),
    "preset.radio": ("Radio", "Radio"),
    "preset.custom": ("Custom", "Personalizzato"),

    # --- advanced tab -----------------------------------------------------
    "adv.ffmpeg": ("FFmpeg executable (empty = automatic)", "Eseguibile FFmpeg (vuoto = automatico)"),
    "adv.ffmpeg_found": ("Encoder engine: {path}", "Motore di codifica: {path}"),
    "adv.ffmpeg_missing": ("FFmpeg not found: only WAV recording is available.",
                           "FFmpeg non trovato: è disponibile solo la registrazione WAV."),
    "adv.remote": ("Remote control (command line / TCP)", "Controllo remoto (riga di comando / TCP)"),
    "adv.remote_enable": ("Enable remote control", "Attiva controllo remoto"),
    "adv.remote_host": ("Listen address", "Indirizzo di ascolto"),
    "adv.remote_port": ("Port", "Porta"),
    "adv.log_file": ("Log file (optional)", "File di log (opzionale)"),

    # --- GUI tab ----------------------------------------------------------
    "gui.language": ("Language", "Lingua"),
    "gui.language_hint": ("The interface changes immediately.", "L'interfaccia cambia immediatamente."),
    "gui.on_top": ("Always on top", "Sempre in primo piano"),
    "gui.start_min": ("Start minimized", "Avvia ridotto a icona"),
    "gui.lcd_color": ("Display color", "Colore display"),

    # --- first run / language --------------------------------------------
    "lang.title": ("Choose language / Scegli la lingua", "Scegli la lingua / Choose language"),
    "lang.prompt": ("Select the interface language. You can change it later in Settings → Interface.",
                    "Seleziona la lingua dell'interfaccia. Puoi cambiarla in seguito da Impostazioni → Interfaccia."),

    # --- about ------------------------------------------------------------
    "about.title": ("About TRIP streaming tool", "Informazioni su TRIP streaming tool"),
    "about.text": ("<b>TRIP streaming tool</b> {version}<br>"
                   "Free, lightweight and open-source live audio streaming tool for Icecast, SHOUTcast and WebRTC/WHIP.<br><br>"
                   "Created by <b>Massimiliano Mascioli Trippa</b> aka <b>Max Trip</b>.<br>"
                   "Released under the MIT license.",
                   "<b>TRIP streaming tool</b> {version}<br>"
                   "Software gratuito, leggero e open-source per lo streaming audio dal vivo verso Icecast, SHOUTcast e WebRTC/WHIP.<br><br>"
                   "Realizzato da <b>Massimiliano Mascioli Trippa</b> aka <b>Max Trip</b>.<br>"
                   "Distribuito con licenza MIT."),

    # --- messages / log ---------------------------------------------------
    "msg.no_servers": ("No server configured or enabled. Add one in Settings → Main.",
                       "Nessun server configurato o attivo. Aggiungine uno in Impostazioni → Principale."),
    "msg.audio_error": ("Audio device error: {err}", "Errore dispositivo audio: {err}"),
    "msg.audio_started": ("Audio input started: {dev} ({sr} Hz, {ch} ch)", "Ingresso audio avviato: {dev} ({sr} Hz, {ch} canali)"),
    "msg.connecting": ("[{server}] connecting to {target}…", "[{server}] connessione a {target}…"),
    "msg.connected": ("[{server}] connected", "[{server}] connesso"),
    "msg.disconnected": ("[{server}] disconnected", "[{server}] disconnesso"),
    "msg.conn_error": ("[{server}] connection error: {err}", "[{server}] errore di connessione: {err}"),
    "msg.reconnect": ("[{server}] reconnecting in {secs} s (attempt {n})", "[{server}] riconnessione tra {secs} s (tentativo {n})"),
    "msg.giving_up": ("[{server}] giving up after {n} attempts", "[{server}] rinuncio dopo {n} tentativi"),
    "msg.song": ("Song updated: {song}", "Brano aggiornato: {song}"),
    "msg.meta_error": ("[{server}] metadata update failed: {err}", "[{server}] aggiornamento metadati fallito: {err}"),
    "msg.rec_start": ("Recording to {file}", "Registrazione su {file}"),
    "msg.rec_stop": ("Recording stopped", "Registrazione fermata"),
    "msg.rec_error": ("Recording error: {err}", "Errore di registrazione: {err}"),
    "msg.encoder_error": ("Encoder error: {err}", "Errore encoder: {err}"),
    "msg.signal_start": ("Signal detected: starting {what}", "Segnale rilevato: avvio {what}"),
    "msg.silence_stop": ("Silence detected: stopping {what}", "Silenzio rilevato: arresto {what}"),
    "msg.what_stream": ("streaming", "streaming"),
    "msg.what_record": ("recording", "registrazione"),
    "msg.remote_listen": ("Remote control listening on {addr}", "Controllo remoto in ascolto su {addr}"),
    "msg.remote_error": ("Remote control unavailable: {err}", "Controllo remoto non disponibile: {err}"),
    "msg.codec_fallback": ("{codec}: libfdk_aac not available, using the FFmpeg AAC-LC encoder",
                           "{codec}: libfdk_aac non disponibile, uso l'encoder AAC-LC di FFmpeg"),
    "msg.config_saved": ("Configuration saved", "Configurazione salvata"),
    "msg.config_imported": ("Configuration imported from {file}", "Configurazione importata da {file}"),
    "msg.no_ffmpeg": ("FFmpeg is required for {codec}", "FFmpeg è necessario per {codec}"),
    "msg.quit_confirm": ("Streaming or recording is active. Quit anyway?",
                         "Streaming o registrazione attivi. Uscire comunque?"),
    "msg.whip_missing": ("WebRTC support requires the 'aiortc' package", "Il supporto WebRTC richiede il pacchetto 'aiortc'"),
}


_current = "en"


def set_language(lang: str) -> None:
    global _current
    _current = lang if lang in LANGUAGES else "en"


def language() -> str:
    return _current


def tr(key: str, **kwargs) -> str:
    pair = _STRINGS.get(key)
    if pair is None:
        text = key
    else:
        text = pair[1] if _current == "it" else pair[0]
    return text.format(**kwargs) if kwargs else text


def keys():
    return set(_STRINGS)
