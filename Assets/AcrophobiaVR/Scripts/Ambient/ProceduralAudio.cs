using UnityEngine;

namespace AcrophobiaVR
{
    /// <summary>
    /// All sound effects are synthesised at startup - no audio files needed.
    /// Clicks, chimes, success arpeggio, fanfare, cracks, shatter, whoosh, clunk, chirp and meow.
    /// </summary>
    public class ProceduralAudio : MonoBehaviour
    {
        const int Rate = 44100;
        static ProceduralAudio instance;

        AudioSource[] voices;
        int nextVoice;
        AudioClip click, chime, success, fanfare, crack, shatter, whoosh, clunk, chirp, meow, boom;

        static ProceduralAudio Get()
        {
            if (instance == null)
            {
                var go = new GameObject("[ProceduralAudio]");
                DontDestroyOnLoad(go);
                instance = go.AddComponent<ProceduralAudio>();
            }
            return instance;
        }

        void Awake()
        {
            instance = this;
            voices = new AudioSource[10];
            for (int i = 0; i < voices.Length; i++)
            {
                voices[i] = gameObject.AddComponent<AudioSource>();
                voices[i].playOnAwake = false;
                voices[i].spatialBlend = 0f;
            }
            click = Synth(0.05f, (t, n) => Mathf.Sin(2 * Mathf.PI * 1800 * t) * Env(t, 0.002f, 0.04f) * 0.4f);
            chime = Synth(1.2f, (t, n) => (Mathf.Sin(2 * Mathf.PI * 880 * t) + 0.5f * Mathf.Sin(2 * Mathf.PI * 1760 * t) + 0.25f * Mathf.Sin(2 * Mathf.PI * 2640 * t)) * Env(t, 0.005f, 1.1f) * 0.3f);
            success = Synth(1.0f, (t, n) => Arp(t, new[] { 523.25f, 659.25f, 783.99f, 1046.5f }, 0.09f) * 0.3f);
            fanfare = Synth(2.4f, (t, n) => Arp(t, new[] { 392f, 523.25f, 659.25f, 783.99f, 659.25f, 783.99f, 1046.5f }, 0.16f) * 0.32f);
            crack = Synth(0.25f, (t, n) => n * Env(t, 0.001f, 0.08f) * 0.7f + Mathf.Sin(2 * Mathf.PI * 3200 * t) * Env(t, 0.001f, 0.02f) * 0.3f);
            shatter = Synth(1.2f, (t, n) => n * Env(t, 0.002f, 0.6f) * 0.6f + Mathf.Sin(2 * Mathf.PI * (4000 + 900 * Mathf.Sin(t * 90)) * t) * Env(t, 0.01f, 0.9f) * 0.15f);
            whoosh = SynthFiltered(1.6f, 0.06f, t => Mathf.Sin(Mathf.PI * Mathf.Clamp01(t / 1.6f)) * 0.8f);
            clunk = Synth(0.5f, (t, n) => (Mathf.Sin(2 * Mathf.PI * 70 * t) * 0.8f + n * 0.25f) * Env(t, 0.002f, 0.35f) * 0.8f);
            chirp = Synth(0.35f, (t, n) => Mathf.Sin(2 * Mathf.PI * (2200 + 1400 * Mathf.Sin(t * 40f)) * t) * Env(t, 0.01f, 0.12f) * 0.18f
                                         + Mathf.Sin(2 * Mathf.PI * (2600 + 1200 * Mathf.Sin(t * 55f)) * t) * Env(t - 0.17f, 0.01f, 0.12f) * 0.18f);
            meow = Synth(0.9f, (t, n) =>
            {
                float f = 520f + 260f * Mathf.Sin(Mathf.PI * Mathf.Clamp01(t / 0.8f)) - 120f * t;
                float v = Mathf.Sin(2 * Mathf.PI * f * t) + 0.5f * Mathf.Sin(4 * Mathf.PI * f * t) + 0.3f * Mathf.Sin(6 * Mathf.PI * f * t);
                return v * Env(t, 0.05f, 0.75f) * 0.22f;
            });
            boom = Synth(1.8f, (t, n) => (n * 0.8f + Mathf.Sin(2 * Mathf.PI * 55 * t) * 0.6f) * Env(t, 0.003f, 1.4f) * 0.7f);
        }

        delegate float Gen(float t, float noise);

        static float Env(float t, float attack, float decay)
        {
            if (t < 0f) return 0f;
            if (t < attack) return t / attack;
            return Mathf.Exp(-(t - attack) / (decay * 0.35f));
        }

        static float Arp(float t, float[] notes, float step)
        {
            float v = 0f;
            for (int i = 0; i < notes.Length; i++)
            {
                float lt = t - i * step;
                if (lt < 0f) break;
                v += (Mathf.Sin(2 * Mathf.PI * notes[i] * lt) + 0.3f * Mathf.Sin(4 * Mathf.PI * notes[i] * lt)) * Env(lt, 0.005f, 0.6f);
            }
            return v * 0.6f;
        }

        static AudioClip Synth(float seconds, Gen gen)
        {
            int n = Mathf.CeilToInt(seconds * Rate);
            var data = new float[n];
            var rng = new System.Random(n);
            for (int i = 0; i < n; i++)
                data[i] = Mathf.Clamp(gen(i / (float)Rate, (float)(rng.NextDouble() * 2 - 1)), -1f, 1f);
            var clip = AudioClip.Create("synth", n, 1, Rate, false);
            clip.SetData(data, 0);
            return clip;
        }

        static AudioClip SynthFiltered(float seconds, float smoothing, System.Func<float, float> envelope)
        {
            int n = Mathf.CeilToInt(seconds * Rate);
            var data = new float[n];
            var rng = new System.Random(7);
            float lp = 0f;
            for (int i = 0; i < n; i++)
            {
                float t = i / (float)Rate;
                float a = smoothing * (0.4f + 0.6f * Mathf.Sin(Mathf.PI * Mathf.Clamp01(t / seconds)));
                lp += ((float)(rng.NextDouble() * 2 - 1) - lp) * a;
                data[i] = lp * envelope(t) * 2.5f;
            }
            var clip = AudioClip.Create("whoosh", n, 1, Rate, false);
            clip.SetData(data, 0);
            return clip;
        }

        void Play(AudioClip clip, float volume = 1f, float pitch = 1f)
        {
            var v = voices[nextVoice];
            nextVoice = (nextVoice + 1) % voices.Length;
            v.pitch = pitch;
            v.PlayOneShot(clip, volume);
        }

        public static void PlayClick() => Get().Play(Get().click, 0.6f);
        public static void PlayChime(float pitch = 1f) => Get().Play(Get().chime, 0.6f, pitch);
        public static void PlaySuccess() => Get().Play(Get().success, 0.8f);
        public static void PlayFanfare() => Get().Play(Get().fanfare, 0.9f);
        public static void PlayCrack() => Get().Play(Get().crack, 0.9f, Random.Range(0.85f, 1.2f));
        public static void PlayShatter() => Get().Play(Get().shatter, 1f);
        public static void PlayWhoosh(float volume) => Get().Play(Get().whoosh, volume, Random.Range(0.9f, 1.1f));
        public static void PlayClunk() => Get().Play(Get().clunk, 0.9f);
        public static void PlayChirp() => Get().Play(Get().chirp, 0.7f, Random.Range(0.95f, 1.15f));
        public static void PlayMeow() => Get().Play(Get().meow, 1f, Random.Range(0.95f, 1.1f));
        public static void PlayBoom() => Get().Play(Get().boom, 0.8f, Random.Range(0.8f, 1.2f));
    }
}