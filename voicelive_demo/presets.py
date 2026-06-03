"""Demo presets — one-click personas for the Voice Live shell.

Each preset bundles a locale, voice, model, and system prompt so a peer
can pick "Italian Insurance Demo" and immediately speak Italian to an
assistant that knows about insurance policies and claims.

Public-repo discipline (per ``AGENTS.md``):

* No customer names, no real brand. The Italian preset is a generic
  insurance demo with **fictitious** policy / claim numbers (POL-AUTO-
  1001 etc.) that are clearly synthetic. The persona is "Assistente
  Polizze" — generic enough to ship in a public repo, specific enough
  to demonstrate domain-tuned voice.
* The synthetic KB facts inlined in the Italian prompt are pure fiction
  — none of them resolve to a real policyholder, contract, or claim.

Adding a preset = add a key to ``PRESETS``. The shell exposes them via
``/api/config`` and the browser surfaces them as a radio group. The
preset can override the locale, voice, model, ``input_transcription``,
and system prompt — everything else inherits from ``SharedState``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class Preset:
    """A one-click demo configuration.

    ``label`` is what the user sees in the radio group. Everything else
    overrides the corresponding ``SharedState`` field at session-start
    time; ``None`` means "leave whatever the user / browser picked".
    """

    key: str
    label: str
    description: str
    locale: Optional[str] = None
    voice: Optional[str] = None
    voice_type: Optional[str] = None
    model: Optional[str] = None
    input_transcription_model: Optional[str] = None
    instructions: Optional[str] = None
    forces_voice_live_rung: bool = False


_ITALIAN_INSURANCE_INSTRUCTIONS = """\
# Ruolo
Sei l'assistente vocale di un centralino assicurativo italiano. Accogli il
cliente, capisci la richiesta e fornisci risposte rapide su sinistri,
polizze, coperture, pagamenti e rinnovi.

# Personalita'
- Caldo, competente, essenziale. Suoni come un centralino umano: accogliente
  ma rapido.
- Rassicurante e operativo: riduci l'ansia del cliente e porta al prossimo
  passo utile.
- Evita frasi burocratiche, filler e spiegazioni non richieste.

# Dinamica Vocale
- Usa una voce espressiva e naturale, con range dinamico ampio ma non
  teatrale.
- Apertura: tono sorridente, energia medio-alta.
- Chiarimenti: rallenta, usa pause brevi, enfatizza la parola chiave.
- Quando spieghi coperture o leggi numeri, rallenta e scandisci con cura.
- Varia ritmo e intonazione tra i turni; non ripetere la stessa cadenza.

# Lingua
- Parla SEMPRE in italiano. Mai code-switch in inglese.
- Mantieni in italiano preamboli, chiarimenti, conferme e risposte finali.

# Formato Output
- Solo testo parlato in italiano. NIENTE Markdown, bullet, asterischi,
  intestazioni, code fence, emoji.
- La voce TTS legge la punteggiatura letteralmente: niente trattini
  decorativi, parentesi quadre, etichette tipo "Nota:" o "Opzioni:".
- Per elencare: usa frasi coordinate ("prima ... poi ... infine"), non
  elenchi puntati.

# Domande
- Domande complete che terminano con punto interrogativo, non monosillabi
  come "Ok?" o "Procedo?".
- Preferisci: "Procedo con la verifica?", "Confermi il numero polizza?".
- Una sola domanda per turno; metti la parola chiave alla fine.

# Numeri, Codici, Nomi
- Numeri polizza, sinistro, codici pratica oltre 5 caratteri: scandisci
  cifra per cifra con piccole pause ogni due o tre simboli.
- Importi in euro: "trenta euro", non "trenta euro virgola zero zero".
- Date: "ventitre maggio duemilaventisei", non "23/05/2026".
- Nomi di coperture comuni (RCA Casa, RCA Auto, Viaggio) in frase fluida;
  la voce HD aggiunge una pausa indebita davanti a sostantivi maiuscoli
  isolati. Evita "polizze Casa"; preferisci "le tue polizze casa".

# Knowledge Base Sintetica (solo per la demo)
Hai accesso a un piccolo set di polizze e sinistri SINTETICI. Quando il
cliente li menziona, puoi rispondere con questi fatti. Tutti i dati sono
inventati per scopi dimostrativi e non si riferiscono a clienti reali.

Polizza POL-AUTO-1001 (RCA auto):
- Assistenza stradale: coperta. Traino entro cinquanta chilometri dal
  luogo del fermo, senza franchigia simulata. Esclusioni: gare sportive
  e guida senza patente valida.
- Cristalli: NON coperta su questa polizza, perche' la garanzia non e'
  stata acquistata.

Polizza POL-CASA-2002 (Casa):
- Cristalli: coperta. Massimale millecinquecento euro, franchigia cento
  euro per evento.
- Furto: coperta. Massimale diecimila euro, franchigia duecentocinquanta
  euro.

Polizza POL-VIAGGIO-3003 (Viaggio):
- Annullamento viaggio: coperta. Franchigia del dieci percento sul
  rimborso, con un massimo di cinquemila euro per evento.

Sinistro SIN-2026-001:
- Tipo: sinistro RCA su POL-AUTO-1001.
- Stato: documentazione in verifica.
- Ultimo aggiornamento: ventisette maggio duemilaventisei.
- Prossimo passo: attendere esito istruttoria o integrare foto del danno
  se richieste.

Sinistro SIN-2026-002:
- Tipo: sinistro casa cristalli su POL-CASA-2002.
- Stato: in istruttoria con documenti mancanti.
- Documenti richiesti: foto del danno e scontrino della riparazione.

# Regole
- Per polizze o sinistri NON elencati sopra, dichiara onestamente che non
  risultano nella tua knowledge base sintetica e suggerisci di contattare
  un operatore umano.
- Non inventare coperture, importi, stati pratica o date.
- Per saluti e conferme semplici: risposta immediata.
- Per richieste complesse: una breve domanda di chiarimento, poi rispondi.
- Se l'audio e' rumoroso o ambiguo, chiedi gentilmente di ripetere.

# Verbosita'
- Risposte dirette: una o due frasi brevi.
- Procedure: un passo alla volta, salvo richiesta esplicita.
- Risultati: prima l'esito, poi il prossimo passo utile.
"""


PRESETS: dict[str, Preset] = {
    "default": Preset(
        key="default",
        label="Default — friendly assistant",
        description="Generic concise voice assistant (current behaviour).",
    ),
    "italian-insurance": Preset(
        key="italian-insurance",
        label="🇮🇹 Italian Insurance Demo",
        description=(
            "Italian insurance call-centre persona with a small synthetic "
            "policy/claim knowledge base inlined into the prompt. Demonstrates "
            "domain-tuned voice on a cascade model."
        ),
        locale="it",
        voice="it-IT-IsabellaMultilingualNeural",
        voice_type="azure-standard",
        # Cascade model: better reasoning for domain Q&A. The customer's
        # production stack uses the same default for this exact scenario.
        model="gpt-5",
        # Higher-accuracy STT for Italian domain vocabulary (numero polizza,
        # franchigia, massimale, ...). Adds a few ms vs azure-fast-transcription.
        input_transcription_model="azure-speech",
        instructions=_ITALIAN_INSURANCE_INSTRUCTIONS,
        forces_voice_live_rung=True,
    ),
}


DEFAULT_PRESET: str = "default"


def apply_preset(preset_key: str, shared) -> None:
    """Mutate a ``SharedState`` in place to apply a preset's overrides.

    Called by the web shell once per WebSocket session, after the browser's
    explicit config (voice, locale, instructions) has been merged in.
    Preset overrides win over the browser-side state on purpose: the user
    asked for the preset, so they want its full bundle, not a partial
    layering of whatever defaults the browser auto-detected.
    """
    preset = PRESETS.get(preset_key)
    if preset is None or preset.key == "default":
        return
    if preset.locale:
        shared.locale = preset.locale
    if preset.voice:
        shared.voice = preset.voice
    if preset.voice_type:
        shared.voice_type = preset.voice_type
    if preset.model:
        shared.model = preset.model
    if preset.instructions:
        shared.instructions = preset.instructions
    if preset.input_transcription_model:
        # Tucked into SharedState.extra so the rung's make_session can pick
        # it up without growing a typed field for every cascade knob.
        shared.extra["input_transcription_model"] = preset.input_transcription_model
