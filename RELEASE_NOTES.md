**TRIP streaming tool** – Massimiliano Mascioli Trippa aka Max Trip

🇮🇹 Streaming audio dal vivo gratuito, leggero e open-source verso Icecast, SHOUTcast e WebRTC/WHIP.
MP3, AAC+, Ogg/Vorbis, Ogg/Opus, Ogg/FLAC; registrazione (anche WAV); dispositivo primario e secondario con mixer;
equalizzatore e compressore; metadati del brano; rilevamento segnale/silenzio; controllo da riga di comando.
Interfaccia in Italiano e Inglese, lingua scelta in fase di installazione e modificabile in seguito.

🇬🇧 Free, lightweight, open-source live audio streaming to Icecast, SHOUTcast and WebRTC/WHIP.
MP3, AAC+, Ogg/Vorbis, Ogg/Opus, Ogg/FLAC; recording (also WAV); primary and secondary device with mixer;
equalizer and compressor; song metadata; signal/silence detection; command-line control.
Italian and English interface, language chosen at install time and changeable later.

### Novità 1.0.3 / What's new in 1.0.3
- 🇮🇹 **Mac: compatibilità corretta.** Le build per Mac della 1.0.2 contenevano librerie Qt compilate per macOS 26 e non
  si avviavano su macOS 14/15. La 1.0.3 funziona da **macOS 12.3** (Apple Silicon) e **macOS 12** (Intel); ogni build
  viene ora verificata automaticamente prima della pubblicazione. Windows e Linux sono invariati.
- 🇬🇧 **Mac: compatibility fixed.** The 1.0.2 Mac builds contained Qt libraries built for macOS 26 and did not start on
  macOS 14/15. 1.0.3 runs on **macOS 12.3** (Apple Silicon) and **macOS 12** (Intel); every build is now checked
  automatically before it is published. Windows and Linux are unchanged.

### Novità 1.0.2 / What's new in 1.0.2
- 🇮🇹 **Versione nativa per Mac Apple Silicon (M1/M2/M3/M4)**: scarica i file `macos-apple-silicon`. Per i Mac con
  processore Intel usa i file `macos-intel`. Il codice del programma è lo stesso della 1.0.1.
- 🇬🇧 **Native build for Apple Silicon Macs (M1/M2/M3/M4)**: download the `macos-apple-silicon` files. Intel Macs use
  the `macos-intel` files. The program code is the same as 1.0.1.

### Novità 1.0.1 / What's new in 1.0.1
- 🇮🇹 **Registrazione corretta e più sicura:** il file WAV resta valido e riproducibile anche se il programma viene chiuso
  bruscamente; se FFmpeg non riesce a scrivere il file la registrazione si ferma subito con l'errore sul display
  (prima il display poteva mostrare "registrazione" senza produrre il file); avviso se il file smette di crescere
  (permessi della cartella); cambio file automatico prima del limite di 4 GB dei WAV.
- 🇮🇹 Le registrazioni vanno ora in **Musica/TRIP streaming tool** (prima nella cartella utente) e il nuovo pulsante
  **📁** apre la cartella; alla fine della registrazione la barra di stato mostra il file salvato.
- 🇬🇧 **Recording fixed and hardened:** WAV files stay valid even if the program is closed abruptly; if FFmpeg cannot
  write the file, recording stops immediately with the error on the display (previously the display could show
  "recording" without producing a file); warning when the file stops growing (folder permissions); automatic new
  file before the 4 GB WAV limit.
- 🇬🇧 Recordings now go to **Music/TRIP streaming tool** (previously the home folder) and the new **📁** button opens
  it; the status bar shows the saved file when recording stops.
- Windows: `trip-streaming-tool.exe -S` and the other command-line options now print their output in the terminal.

### Download
- **Windows**: `TRIP-streaming-tool-*-windows-setup.exe`
- **macOS Apple Silicon (M1/M2/M3/M4)**, macOS 12.3+: `TRIP-streaming-tool-*-macos-apple-silicon.pkg` or `.dmg`
- **macOS Intel**, macOS 12+: `TRIP-streaming-tool-*-macos-intel.pkg` or `.dmg`
- macOS `.pkg`: lingua nel programma di installazione / language in the installer; `.dmg`: lingua al primo avvio / language on first launch
- **Linux**: `TRIP-streaming-tool-*-linux-x86_64.tar.gz` → `./install.sh`

macOS: le build non sono firmate, al primo avvio clic destro → Apri. / Builds are unsigned: right-click → Open on first launch.
