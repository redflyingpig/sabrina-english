// Cantonese text-to-speech (Web Speech API) and voice recording for 跟讀.
import { settings } from "./store.js";

let voices = [];
const ready = new Promise((resolve) => {
  if (!("speechSynthesis" in window)) return resolve([]);
  const grab = () => {
    voices = speechSynthesis.getVoices();
    if (voices.length) resolve(voices);
  };
  grab();
  speechSynthesis.addEventListener?.("voiceschanged", grab);
  setTimeout(() => resolve(voices), 1500);
});

const isCantonese = (v) => /^(zh|yue)[-_](HK|hk)|yue/i.test(v.lang) || /cantonese|粵|廣東/i.test(v.name);

export async function cantoneseVoices() {
  await ready;
  return voices.filter(isCantonese);
}

export function hasSpeech() {
  return "speechSynthesis" in window;
}

async function pickVoice() {
  const list = await cantoneseVoices();
  const want = settings().voice;
  return list.find((v) => v.name === want) || list.find((v) => /HK/i.test(v.lang)) || list[0] || null;
}

// Strip things a voice should not read: speaker labels, (jyutping), slashes, ellipses.
export function speakable(text) {
  return String(text || "")
    .replace(/^[^：:\s]{1,6}[：:]\s*/gm, "")
    .replace(/[（(][A-Za-z0-9 ]+[）)]/g, "")
    .replace(/\s*[\/／]\s*/g, "，")
    .replace(/[…]+|\.{3,}/g, "，")
    .replace(/[＿_*]/g, "")
    .trim();
}

let current = null;

export async function speak(text, { rate } = {}) {
  if (!hasSpeech()) return false;
  const voice = await pickVoice();
  stop();
  const u = new SpeechSynthesisUtterance(speakable(text));
  u.lang = voice?.lang || "zh-HK";
  if (voice) u.voice = voice;
  u.rate = rate || settings().rate || 0.9;
  current = u;
  return new Promise((resolve) => {
    u.onend = () => resolve(true);
    u.onerror = () => resolve(false);
    speechSynthesis.speak(u);
  });
}

export function stop() {
  if (hasSpeech()) speechSynthesis.cancel();
  current = null;
}

export const speaking = () => !!current && speechSynthesis.speaking;

// ---- recording ------------------------------------------------------------
export function canRecord() {
  return !!(navigator.mediaDevices?.getUserMedia && window.MediaRecorder);
}

export async function startRecording() {
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  const rec = new MediaRecorder(stream);
  const chunks = [];
  rec.ondataavailable = (e) => chunks.push(e.data);
  rec.start();
  return () => new Promise((resolve) => {
    rec.onstop = () => {
      stream.getTracks().forEach((t) => t.stop());
      resolve(URL.createObjectURL(new Blob(chunks, { type: rec.mimeType })));
    };
    rec.stop();
  });
}
