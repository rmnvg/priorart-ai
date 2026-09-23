"use client";

import { useEffect, useRef, useState } from "react";

// Browser speech recognition, used as a dictation aid: many inventors can
// explain a mechanism out loud far more completely than they can write it
// down, especially in their first language. Chrome and Edge support it
// (with Indian-language models); where it's missing, the button simply
// doesn't render — typing still works everywhere.

// Minimal typings: the Web Speech API isn't in TypeScript's DOM lib.
interface SpeechRecognitionResultLike {
  isFinal: boolean;
  0: { transcript: string };
}
interface SpeechRecognitionEventLike {
  resultIndex: number;
  results: ArrayLike<SpeechRecognitionResultLike>;
}
interface SpeechRecognitionLike {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  onresult: ((event: SpeechRecognitionEventLike) => void) | null;
  onend: (() => void) | null;
  onerror: ((event: { error: string }) => void) | null;
  start: () => void;
  stop: () => void;
}
type SpeechRecognitionCtor = new () => SpeechRecognitionLike;

function getRecognitionCtor(): SpeechRecognitionCtor | null {
  if (typeof window === "undefined") return null;
  const w = window as unknown as {
    SpeechRecognition?: SpeechRecognitionCtor;
    webkitSpeechRecognition?: SpeechRecognitionCtor;
  };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

export const SPEECH_LANGUAGES = [
  { code: "hi-IN", label: "हिन्दी" },
  { code: "en-IN", label: "English" },
  { code: "bn-IN", label: "বাংলা" },
  { code: "ta-IN", label: "தமிழ்" },
  { code: "te-IN", label: "తెలుగు" },
  { code: "mr-IN", label: "मराठी" },
  { code: "gu-IN", label: "ગુજરાતી" },
  { code: "kn-IN", label: "ಕನ್ನಡ" },
  { code: "ml-IN", label: "മലയാളം" },
  { code: "pa-IN", label: "ਪੰਜਾਬੀ" },
] as const;

const ERROR_COPY: Record<string, string> = {
  "not-allowed": "Microphone access was blocked — allow it in your browser to dictate.",
  "no-speech": "Didn't catch anything — try again a little closer to the mic.",
  network: "Speech recognition needs an internet connection.",
};

export default function VoiceInput({
  onTranscript,
  disabled,
}: {
  onTranscript: (text: string) => void;
  disabled?: boolean;
}) {
  const [supported, setSupported] = useState(false);
  const [listening, setListening] = useState(false);
  const [language, setLanguage] = useState<string>(SPEECH_LANGUAGES[0].code);
  const [interim, setInterim] = useState("");
  const [error, setError] = useState<string | null>(null);
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);

  // Feature detection has to wait for the client — the server render has no
  // window, and rendering the button there would mismatch on hydration.
  useEffect(() => setSupported(getRecognitionCtor() !== null), []);
  useEffect(() => () => recognitionRef.current?.stop(), []);

  function start() {
    const Ctor = getRecognitionCtor();
    if (!Ctor) return;
    const recognition = new Ctor();
    recognition.lang = language;
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.onresult = (event) => {
      let pending = "";
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const result = event.results[i];
        if (result.isFinal) onTranscript(result[0].transcript.trim());
        else pending += result[0].transcript;
      }
      setInterim(pending);
    };
    recognition.onerror = (event) => {
      if (event.error !== "aborted") setError(ERROR_COPY[event.error] ?? "Dictation stopped unexpectedly.");
    };
    recognition.onend = () => {
      setListening(false);
      setInterim("");
    };
    recognitionRef.current = recognition;
    setError(null);
    setListening(true);
    recognition.start();
  }

  function stop() {
    recognitionRef.current?.stop();
  }

  if (!supported) return null;

  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={listening ? stop : start}
          disabled={disabled}
          aria-pressed={listening}
          className={`flex items-center gap-2 rounded-lg border px-3 py-1.5 text-sm font-medium shadow-sm transition disabled:opacity-50 ${
            listening
              ? "border-red-300 bg-red-50 text-red-700"
              : "border-neutral-300 bg-white text-neutral-700 hover:bg-neutral-50"
          }`}
        >
          <span
            className={`inline-block h-2 w-2 rounded-full ${listening ? "animate-pulse bg-red-500" : "bg-neutral-400"}`}
          />
          {listening ? "Stop" : "🎤 Speak your idea"}
        </button>
        <select
          value={language}
          onChange={(e) => setLanguage(e.target.value)}
          disabled={listening || disabled}
          aria-label="Speech language"
          className="rounded-lg border border-neutral-300 bg-white px-2 py-1.5 text-sm text-neutral-700 disabled:opacity-50"
        >
          {SPEECH_LANGUAGES.map((l) => (
            <option key={l.code} value={l.code}>
              {l.label}
            </option>
          ))}
        </select>
      </div>
      {listening && (
        <p className="text-xs text-neutral-500">
          Listening… {interim && <span className="italic text-neutral-700">{interim}</span>}
        </p>
      )}
      {error && <p className="text-xs text-red-600">{error}</p>}
    </div>
  );
}
