using UnityEngine;

namespace AcrophobiaVR
{
    /// <summary>Walking surface used to pick a footstep sound.</summary>
    public enum StepSurface { Concrete, Wood, Metal, Glass, Grass }

    /// <summary>
    /// All sound effects are synthesised at startup - no audio files needed.
    /// Clicks, chimes, success arpeggio, fanfare, cracks, shatter, whoosh, clunk, chirp and meow (2D),
    /// plus a pooled set of 3D voices for positional one-shots (PlayAt / Play*At), creaks, footsteps
    /// and a dedicated 2D breath voice for the breathing guide.
    /// </summary>
    public class ProceduralAudio : MonoBehaviour
    {
        const int Rate = 44100;
        const int SpatialVoiceCount = 16;
        const float BreathBaseLength = 1.5f;
        static ProceduralAudio instance;

        AudioSource[] voices;
        int nextVoice;
        AudioClip click, chime, success, fanfare, crack, shatter, whoosh, clunk, chirp, meow, boom;

        // Pooled 3D voices (least-recently-used free source, else steal the oldest).
        AudioSource[] spatial;
        int[] spatialStamp;
        int stampCounter;

        AudioSource breathSource;
        AudioClip breathIn, breathOut;
        AudioClip[] creaks;
        AudioClip[][] steps; // [StepSurface][variant]

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

        // Synthesis (~18 s of samples) runs in Awake; do it at load instead of on the first in-game sound (VR frame hitch).
        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        static void Prewarm() => Get();

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

            breathSource = gameObject.AddComponent<AudioSource>();
            breathSource.playOnAwake = false;
            breathSource.loop = false;
            breathSource.spatialBlend = 0f;

            spatial = new AudioSource[SpatialVoiceCount];
            spatialStamp = new int[SpatialVoiceCount];
            for (int i = 0; i < spatial.Length; i++)
            {
                var child = new GameObject("Voice3D_" + i);
                child.transform.SetParent(transform, false);
                var src = child.AddComponent<AudioSource>();
                src.playOnAwake = false;
                src.loop = false;
                src.spatialBlend = 1f;
                src.rolloffMode = AudioRolloffMode.Logarithmic;
                src.dopplerLevel = 0f;
                src.spread = 0f;
                spatial[i] = src;
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

            // New clips (~6.8 s of samples in total).
            creaks = new[]
            {
                SynthCreak(0.45f, 95f, 70f, 520f, 11),
                SynthCreak(0.70f, 85f, 60f, 410f, 23),
                SynthCreak(0.90f, 90f, 58f, 330f, 37),
            };

            int surfaceCount = System.Enum.GetValues(typeof(StepSurface)).Length;
            steps = new AudioClip[surfaceCount][];
            for (int si = 0; si < surfaceCount; si++)
                steps[si] = new[] { StepClip((StepSurface)si, 0), StepClip((StepSurface)si, 1) };

            breathIn = SynthBreath(true);
            breathOut = SynthBreath(false);
        }

        delegate float Gen(float t, float noise);

        static float Env(float t, float attack, float decay)
        {
            if (t < 0f) return 0f;
            if (t < attack) return t / attack;
            return Mathf.Exp(-(t - attack) / (decay * 0.35f));
        }

        static float Smooth(float x)
        {
            x = Mathf.Clamp01(x);
            return x * x * (3f - 2f * x);
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

        // ---------- New synthesis helpers ----------

        /// <summary>Generates samples with a seeded noise source, then normalises to the given peak.</summary>
        static AudioClip SynthNorm(string name, float seconds, int seed, float peak, Gen gen)
        {
            int n = Mathf.CeilToInt(seconds * Rate);
            var data = new float[n];
            var rng = new System.Random(seed);
            for (int i = 0; i < n; i++)
                data[i] = gen(i / (float)Rate, (float)(rng.NextDouble() * 2 - 1));
            Normalize(data, peak);
            return MakeClip(name, data);
        }

        static void Normalize(float[] data, float peak)
        {
            float max = 0f;
            for (int i = 0; i < data.Length; i++)
            {
                float a = Mathf.Abs(data[i]);
                if (a > max) max = a;
            }
            if (max < 1e-5f || float.IsNaN(max)) return;
            float k = peak / max;
            for (int i = 0; i < data.Length; i++)
                data[i] = Mathf.Clamp(data[i] * k, -1f, 1f);
        }

        static AudioClip MakeClip(string name, float[] data)
        {
            var clip = AudioClip.Create(name, data.Length, 1, Rate, false);
            clip.SetData(data, 0);
            return clip;
        }

        /// <summary>
        /// Wood/rope creak: stick-slip friction grains (rate sweeping f0 to f1) exciting a body resonance,
        /// plus a low groan at the grain frequency and a little friction hiss.
        /// </summary>
        static AudioClip SynthCreak(float seconds, float f0, float f1, float resHz, int seed)
        {
            int n = Mathf.CeilToInt(seconds * Rate);
            var data = new float[n];
            var rng = new System.Random(seed);
            float w = 2f * Mathf.PI * resHz / Rate;
            const float r = 0.993f;
            float c1 = 2f * r * Mathf.Cos(w), c2 = r * r;
            float norm = Mathf.Sin(w);
            float y1 = 0f, y2 = 0f, phase = 0f, wander = 0f, hiss = 0f, lastExcite = 0f;
            for (int i = 0; i < n; i++)
            {
                float t = i / (float)Rate;
                float x = Mathf.Clamp01(t / seconds);
                float noise = (float)(rng.NextDouble() * 2 - 1);
                wander += (noise - wander) * 0.002f;
                float f = Mathf.Lerp(f0, f1, x) * (1f + wander * 4f);

                phase += f / Rate;
                float excite = 0f;
                if (phase >= 1f)
                {
                    phase -= 1f;
                    excite = 0.5f + 0.5f * (float)rng.NextDouble();
                    lastExcite = excite;
                }
                float y = excite + c1 * y1 - c2 * y2;
                y2 = y1;
                y1 = y;

                float p = 2f * Mathf.PI * phase;
                float groan = (Mathf.Sin(p) + 0.4f * Mathf.Sin(2f * p)) * (0.6f + 0.4f * lastExcite);
                hiss += (noise - hiss) * 0.15f;

                float env = Mathf.Pow(Mathf.Max(0f, Mathf.Sin(Mathf.PI * x)), 0.6f)
                            * (0.75f + 0.25f * Mathf.Sin(2f * Mathf.PI * 7f * t));
                data[i] = (y * norm * 0.55f + groan * 0.35f + hiss * 0.12f) * env;
            }
            Normalize(data, 0.8f);
            return MakeClip("creak", data);
        }

        static AudioClip StepClip(StepSurface surface, int variant)
        {
            int seed = 101 + (int)surface * 17 + variant * 5;
            float d = variant == 0 ? 1f : 1.07f;
            float lp = 0f, lp2 = 0f;
            switch (surface)
            {
                case StepSurface.Wood:
                    return SynthNorm("step_wood", 0.15f, seed, 0.8f, (t, n) =>
                    {
                        lp += (n - lp) * 0.12f;
                        return Mathf.Sin(2f * Mathf.PI * 180f * d * t) * Env(t, 0.001f, 0.09f) * 0.7f
                             + Mathf.Sin(2f * Mathf.PI * 470f * d * t) * Env(t, 0.001f, 0.035f) * 0.25f
                             + lp * Env(t, 0.001f, 0.03f) * 1.2f;
                    });
                case StepSurface.Metal:
                    return SynthNorm("step_metal", 0.3f, seed, 0.75f, (t, n) =>
                    {
                        lp += (n - lp) * 0.05f;
                        return Mathf.Sin(2f * Mathf.PI * 420f * d * t) * Env(t, 0.001f, 0.25f) * 0.45f
                             + Mathf.Sin(2f * Mathf.PI * 1130f * d * t) * Env(t, 0.001f, 0.16f) * 0.3f
                             + Mathf.Sin(2f * Mathf.PI * 2380f * d * t) * Env(t, 0.001f, 0.08f) * 0.2f
                             + n * Env(t, 0.0005f, 0.012f) * 0.35f
                             + lp * Env(t, 0.002f, 0.05f) * 1.5f;
                    });
                case StepSurface.Glass:
                    return SynthNorm("step_glass", 0.12f, seed, 0.7f, (t, n) =>
                    {
                        lp += (n - lp) * 0.3f;
                        float hp = n - lp;
                        lp2 += (n - lp2) * 0.05f;
                        return Mathf.Sin(2f * Mathf.PI * 3500f * d * t) * Env(t, 0.0005f, 0.05f) * 0.25f
                             + Mathf.Sin(2f * Mathf.PI * 4800f * d * t) * Env(t, 0.0005f, 0.035f) * 0.2f
                             + Mathf.Sin(2f * Mathf.PI * 6000f * d * t) * Env(t, 0.0005f, 0.02f) * 0.15f
                             + hp * Env(t, 0.0003f, 0.005f) * 0.4f
                             + lp2 * Env(t, 0.002f, 0.04f) * 2f;
                    });
                case StepSurface.Grass:
                    return SynthNorm("step_grass", 0.18f, seed, 0.6f, (t, n) =>
                    {
                        lp += (n - lp) * 0.35f;
                        lp2 += (lp - lp2) * 0.05f;
                        float band = lp - lp2;
                        float crackle = n > 0.97f ? n : 0f;
                        return band * Env(t, 0.02f, 0.12f) * 1.5f + crackle * Env(t, 0.01f, 0.1f) * 0.5f;
                    });
                default: // Concrete
                    return SynthNorm("step_concrete", 0.12f, seed, 0.8f, (t, n) =>
                    {
                        lp += (n - lp) * 0.06f;
                        return lp * Env(t, 0.002f, 0.05f) * 3f
                             + Mathf.Sin(2f * Mathf.PI * 95f * d * t) * Env(t, 0.001f, 0.04f) * 0.35f
                             + n * Env(t, 0.0004f, 0.006f) * 0.4f;
                    });
            }
        }

        /// <summary>Airy breath: band-passed noise whose centre rises (inhale) or falls (exhale), with a soft swell.</summary>
        static AudioClip SynthBreath(bool rising)
        {
            int n = Mathf.CeilToInt(BreathBaseLength * Rate);
            var data = new float[n];
            var rng = new System.Random(rising ? 31 : 37);
            float low = 0f, band = 0f, body = 0f;
            for (int i = 0; i < n; i++)
            {
                float x = i / (float)(n - 1);
                float noise = (float)(rng.NextDouble() * 2 - 1);
                float fc = rising ? Mathf.Lerp(550f, 1500f, x) : Mathf.Lerp(1300f, 450f, x);
                float f = 2f * Mathf.Sin(Mathf.PI * fc / Rate);
                low += f * band;
                float high = noise - low - 0.9f * band;
                band += f * high;
                body += (noise - body) * 0.02f;
                float env = rising
                    ? (x < 0.75f ? Smooth(x / 0.75f) : 1f - Smooth((x - 0.75f) / 0.25f))
                    : (x < 0.15f ? Smooth(x / 0.15f) : 1f - Smooth((x - 0.15f) / 0.85f));
                data[i] = (band + body * 1.5f) * env;
            }
            Normalize(data, 0.6f);
            return MakeClip(rising ? "breath_in" : "breath_out", data);
        }

        // ---------- Playback ----------

        void Play(AudioClip clip, float volume = 1f, float pitch = 1f)
        {
            var v = voices[nextVoice];
            nextVoice = (nextVoice + 1) % voices.Length;
            v.pitch = pitch;
            v.PlayOneShot(clip, volume);
        }

        void PlaySpatial(AudioClip clip, Vector3 position, float volume, float pitch, float minDistance, float maxDistance)
        {
            int best = -1, bestStamp = int.MaxValue, oldest = 0, oldestStamp = int.MaxValue;
            for (int i = 0; i < spatial.Length; i++)
            {
                int st = spatialStamp[i];
                if (st < oldestStamp) { oldestStamp = st; oldest = i; }
                if (!spatial[i].isPlaying && st < bestStamp) { bestStamp = st; best = i; }
            }
            if (best < 0) best = oldest;

            var src = spatial[best];
            spatialStamp[best] = ++stampCounter;
            src.Stop();
            src.transform.position = position;
            float minD = Mathf.Max(0.01f, minDistance);
            src.minDistance = 0.01f;
            src.maxDistance = Mathf.Max(minD + 0.01f, maxDistance);
            src.minDistance = minD;
            // pitch 0 would never finish (hogs a voice); negative would start past the clip end.
            src.pitch = Mathf.Clamp(pitch, 0.05f, 3f);
            src.volume = Mathf.Clamp01(volume);
            src.clip = clip;
            src.Play();
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

        /// <summary>Pooled 3D one-shot at a world position (max 16 simultaneous; oldest is stolen).</summary>
        public static void PlayAt(AudioClip clip, Vector3 position, float volume = 1f, float pitch = 1f, float minDistance = 1f, float maxDistance = 40f)
        {
            if (clip == null || !(volume > 0.001f)) return; // silent/NaN volume: don't occupy a pooled voice
            Get().PlaySpatial(clip, position, volume, pitch, minDistance, maxDistance);
        }

        public static void PlayCrackAt(Vector3 position) => PlayAt(Get().crack, position, 0.9f, Random.Range(0.85f, 1.2f), 1.5f, 40f);
        public static void PlayShatterAt(Vector3 position) => PlayAt(Get().shatter, position, 1f, Random.Range(0.95f, 1.05f), 2f, 60f);
        public static void PlayClunkAt(Vector3 position) => PlayAt(Get().clunk, position, 0.9f, Random.Range(0.95f, 1.05f), 2f, 50f);
        public static void PlayMeowAt(Vector3 position) => PlayAt(Get().meow, position, 1f, Random.Range(0.95f, 1.1f), 1f, 25f);
        public static void PlayBoomAt(Vector3 position) => PlayAt(Get().boom, position, 1f, Random.Range(0.8f, 1.2f), 25f, 500f);
        public static void PlayChirpAt(Vector3 position) => PlayAt(Get().chirp, position, 0.7f, Random.Range(0.95f, 1.15f), 1.5f, 40f);

        /// <summary>Wood/rope creak or groan. Higher intensity = louder and lower-pitched.</summary>
        public static void PlayCreakAt(Vector3 position, float intensity01)
        {
            var p = Get();
            float k = Mathf.Clamp01(intensity01);
            var clip = p.creaks[Random.Range(0, p.creaks.Length)];
            float volume = Mathf.Lerp(0.25f, 1f, k);
            float pitch = Mathf.Lerp(1.15f, 0.75f, k) * Random.Range(0.95f, 1.05f);
            PlayAt(clip, position, volume, pitch, 2f, 30f);
        }

        /// <summary>Single footstep on the given surface at a world position (random variant and pitch 0.9-1.1).</summary>
        public static void PlayFootstep(StepSurface surface, Vector3 position, float volume = 0.6f)
        {
            var p = Get();
            int si = Mathf.Clamp((int)surface, 0, p.steps.Length - 1);
            var set = p.steps[si];
            PlayAt(set[Random.Range(0, set.Length)], position, volume, Random.Range(0.9f, 1.1f), 1f, 15f);
        }

        /// <summary>
        /// 2D soft breath swell for the breathing guide. The 1.5 s base clip is stretched to roughly
        /// <paramref name="seconds"/> via pitch (clamped 0.5..1.5). A new breath replaces the previous one.
        /// </summary>
        public static void PlayBreath(bool inhale, float seconds)
        {
            var p = Get();
            float pitch = seconds > 0.01f ? Mathf.Clamp(BreathBaseLength / seconds, 0.5f, 1.5f) : 1f;
            var src = p.breathSource;
            src.Stop();
            src.clip = inhale ? p.breathIn : p.breathOut;
            src.pitch = pitch;
            src.volume = 0.35f;
            src.Play();
        }
    }
}
