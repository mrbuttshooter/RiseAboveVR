using System.Collections.Generic;
using UnityEngine;

namespace AcrophobiaVR
{
    public enum EmitterKind { BuskerGuitar, Fountain, CarEngine, Motor, CafeChatter, Birds, Construction }

    /// <summary>
    /// Looping 3D ambient sound source for otherwise silent scene objects (busker, fountain, cars, lift motors,
    /// cafe chatter, bird flocks). Clips are synthesised once per kind and cached; no audio files needed.
    /// Motor emitters fade with the MovingPlatform on this object or a parent.
    /// </summary>
    public class SoundEmitter : MonoBehaviour
    {
        public EmitterKind kind;
        public float volume = 1f;

        const int Rate = 22050;
        const int GuitarRate = 44100;

        static readonly Dictionary<EmitterKind, AudioClip> clips = new Dictionary<EmitterKind, AudioClip>();

        AudioSource source;
        MovingPlatform platform;
        float baseVolume;
        float basePitch = 1f;
        float motorLevel;
        bool started;
        bool pausedByMotor;
        bool resume;

        void Start()
        {
            AudioClip clip = GetClip(kind);
            if (clip == null) { enabled = false; return; }

            source = gameObject.AddComponent<AudioSource>();
            source.playOnAwake = false;
            source.loop = true;
            source.clip = clip;
            source.spatialBlend = 1f;
            source.rolloffMode = AudioRolloffMode.Logarithmic;
            source.dopplerLevel = 0f;

            float minD = 1f, maxD = 30f, kindVolume = 1f;
            int priority = 128;
            switch (kind)
            {
                case EmitterKind.BuskerGuitar: minD = 2f; maxD = 35f; kindVolume = 0.8f; priority = 100; break;
                case EmitterKind.Fountain: minD = 1.5f; maxD = 25f; kindVolume = 1f; priority = 120; break;
                case EmitterKind.CarEngine:
                    minD = 3f; maxD = 60f; kindVolume = 0.5f; priority = 160;
                    source.dopplerLevel = 1.2f;
                    basePitch = Random.Range(0.85f, 1.2f);
                    break;
                case EmitterKind.Motor:
                    minD = 2f; maxD = 40f; kindVolume = 1f; priority = 110;
                    platform = GetComponentInParent<MovingPlatform>();
                    break;
                case EmitterKind.CafeChatter: minD = 2f; maxD = 18f; kindVolume = 0.5f; priority = 130; break;
                case EmitterKind.Birds: minD = 5f; maxD = 80f; kindVolume = 1f; priority = 140; break;
                case EmitterKind.Construction: minD = 8f; maxD = 120f; kindVolume = 0.9f; priority = 110; break;
            }
            source.minDistance = minD;
            source.maxDistance = maxD;
            source.priority = priority;
            source.pitch = basePitch;
            baseVolume = kindVolume * Mathf.Max(0f, volume);
            source.volume = kind == EmitterKind.Motor ? 0f : baseVolume;

            source.Play();
            source.timeSamples = Random.Range(0, Mathf.Max(1, clip.samples - 1));
            started = true;
        }

        // Re-activation: the AudioSource stops when its GameObject is deactivated and (playOnAwake off) does not
        // restart by itself. Resume from Update, because this OnEnable can run before the AudioSource is re-enabled.
        void OnEnable()
        {
            if (started) resume = true;
        }

        void OnDisable()
        {
            pausedByMotor = false;
        }

        void Update()
        {
            if (source == null) return;
            if (kind != EmitterKind.Motor)
            {
                if (resume)
                {
                    resume = false;
                    if (!source.isPlaying && source.isActiveAndEnabled) source.Play();
                }
                return;
            }

            float target = platform == null ? 1f : (platform.MotorRunning ? 1f : 0f);
            float rate = target > motorLevel ? 1.5f : 0.8f;
            motorLevel = Mathf.MoveTowards(motorLevel, target, Time.deltaTime * rate);
            source.volume = baseVolume * motorLevel;
            source.pitch = basePitch * (0.75f + 0.25f * motorLevel);

            if (motorLevel <= 0.001f)
            {
                if (source.isPlaying) { source.Pause(); pausedByMotor = true; }
            }
            else if (!source.isPlaying)
            {
                if (pausedByMotor) source.UnPause(); else source.Play();
                pausedByMotor = false;
            }
        }

        // ------------------------------------------------------------------ clip cache

        static AudioClip GetClip(EmitterKind k)
        {
            AudioClip c;
            if (clips.TryGetValue(k, out c) && c != null) return c;

            int rate = Rate;
            float[] data;
            switch (k)
            {
                case EmitterKind.BuskerGuitar: rate = GuitarRate; data = GenGuitar(rate); break;
                case EmitterKind.Fountain: data = GenFountain(rate); break;
                case EmitterKind.CarEngine: data = GenEngine(rate); break;
                case EmitterKind.Motor: data = GenMotor(rate); break;
                case EmitterKind.CafeChatter: data = GenChatter(rate); break;
                case EmitterKind.Construction: data = GenConstruction(rate); break;
                default: data = GenBirds(rate); break;
            }
            if (data == null || data.Length == 0) return null;

            c = AudioClip.Create("Emitter_" + k, data.Length, 1, rate, false);
            c.SetData(data, 0);
            c.hideFlags = HideFlags.DontUnloadUnusedAsset;
            clips[k] = c;
            return c;
        }

        // ------------------------------------------------------------------ DSP helpers

        /// <summary>Chamberlin state-variable filter (low/band outputs).</summary>
        struct Svf
        {
            float low, band, f, q;
            public float Low => low;
            public float Bp => band;

            public void Set(float fc, float resonance, int rate)
            {
                fc = Mathf.Clamp(fc, 10f, rate * 0.16f);
                f = 2f * Mathf.Sin(Mathf.PI * fc / rate);
                q = 1f / Mathf.Max(0.5f, resonance);
            }

            public void Tick(float x)
            {
                low += f * band;
                float high = x - low - q * band;
                band += f * high;
            }
        }

        static float R(System.Random r, float a, float b) { return a + (float)r.NextDouble() * (b - a); }
        static float Noise(System.Random r) { return (float)(r.NextDouble() * 2.0 - 1.0); }
        static float Sin01(double cycles) { return (float)System.Math.Sin(2.0 * System.Math.PI * cycles); }
        static float Midi(int m) { return 440f * Mathf.Pow(2f, (m - 69) / 12f); }

        /// <summary>Seamless loop: src holds n + fade samples; the overhang is crossfaded into the head.</summary>
        static float[] LoopCrossfade(float[] src, int n, bool equalPower)
        {
            int fade = src.Length - n;
            var o = new float[n];
            System.Array.Copy(src, o, n);
            for (int i = 0; i < fade && i < n; i++)
            {
                float a = (float)i / fade;
                float gIn, gOut;
                if (equalPower) { gIn = Mathf.Sin(a * Mathf.PI * 0.5f); gOut = Mathf.Cos(a * Mathf.PI * 0.5f); }
                else { gIn = a; gOut = 1f - a; }
                o[i] = src[i] * gIn + src[n + i] * gOut;
            }
            return o;
        }

        static void Normalize(float[] d, float peak)
        {
            float m = 0f;
            for (int i = 0; i < d.Length; i++) { float a = Mathf.Abs(d[i]); if (a > m) m = a; }
            if (m < 1e-6f) return;
            float g = peak / m;
            for (int i = 0; i < d.Length; i++) d[i] *= g;
        }

        // ------------------------------------------------------------------ generators

        /// <summary>8 s Karplus-Strong arpeggio, I-V-vi-IV in C major at 90 bpm (3 beats per chord), wraps seamlessly.</summary>
        static float[] GenGuitar(int rate)
        {
            float eighth = 60f / 90f * 0.5f;
            int[][] chords =
            {
                new[] { 48, 55, 60, 64, 67, 64 }, // C
                new[] { 43, 50, 55, 59, 62, 59 }, // G
                new[] { 45, 52, 57, 60, 64, 60 }, // Am
                new[] { 41, 48, 53, 57, 60, 57 }, // F
            };
            int[][] melody =
            {
                new[] { 76, 72 },
                new[] { 74, 71 },
                new[] { 72, 76 },
                new[] { 77, 72 },
            };
            int n = Mathf.RoundToInt(eighth * 24f * rate);
            var o = new float[n];
            var rng = new System.Random(1234);
            int step = 0;
            for (int c = 0; c < 4; c++)
            {
                for (int k = 0; k < 6; k++, step++)
                {
                    float start = step * eighth + R(rng, -0.01f, 0.01f);
                    Pluck(o, rate, Midi(chords[c][k]), start, k == 0 ? 0.5f : 0.36f, rng);
                    if (k == 0) Pluck(o, rate, Midi(melody[c][0]), start + 0.012f, 0.3f, rng);
                    else if (k == 3) Pluck(o, rate, Midi(melody[c][1]), start + 0.012f, 0.26f, rng);
                }
            }
            Normalize(o, 0.75f);
            return o;
        }

        static void Pluck(float[] o, int rate, float freq, float startSec, float amp, System.Random rng)
        {
            int n = o.Length;
            int len = Mathf.Max(2, Mathf.RoundToInt(rate / freq));
            var buf = new float[len];
            float lp = 0f, mean = 0f;
            for (int i = 0; i < len; i++)
            {
                lp += (Noise(rng) - lp) * 0.4f; // soft (nylon-ish) excitation
                buf[i] = lp;
                mean += lp;
            }
            mean /= len;
            for (int i = 0; i < len; i++) buf[i] -= mean;

            int dur = Mathf.Min(n, (int)(rate * 2.2f));
            int fadeStart = dur - (int)(rate * 0.35f);
            int startIdx = Mathf.RoundToInt(startSec * rate);
            int idx = 0;
            const float decay = 0.997f;
            for (int s = 0; s < dur; s++)
            {
                int next = idx + 1;
                if (next >= len) next = 0;
                float y = buf[idx];
                buf[idx] = decay * 0.5f * (buf[idx] + buf[next]);
                idx = next;
                float g = amp;
                if (s > fadeStart) g *= 1f - (float)(s - fadeStart) / (dur - fadeStart);
                int w = (startIdx + s) % n;
                if (w < 0) w += n;
                o[w] += y * g;
            }
        }

        /// <summary>4 s splashing water: band-passed noise layers + random droplet plinks.</summary>
        static float[] GenFountain(int rate)
        {
            int n = rate * 4;
            int fade = rate / 4;
            int total = n + fade;
            var d = new float[total];
            var rng = new System.Random(4242);
            var hiss = new Svf(); hiss.Set(2200f, 0.8f, rate);
            var body = new Svf(); body.Set(650f, 0.7f, rate);
            var rumble = new Svf(); rumble.Set(160f, 0.7f, rate);
            float splash = 0.7f, splashTarget = 0.7f;
            int splashTimer = 0;
            for (int i = 0; i < total; i++)
            {
                if (--splashTimer <= 0)
                {
                    splashTarget = R(rng, 0.45f, 1f);
                    splashTimer = (int)(rate * R(rng, 0.03f, 0.12f));
                }
                splash += (splashTarget - splash) * 0.002f;
                float w = Noise(rng);
                hiss.Tick(w); body.Tick(w); rumble.Tick(w);
                d[i] = (hiss.Bp * 0.6f + body.Bp * 0.5f + rumble.Low * 1.5f) * splash;
            }
            var o = LoopCrossfade(d, n, true);

            for (int k = 0; k < 70; k++)
            {
                int start = rng.Next(n);
                float f0 = R(rng, 700f, 1600f);
                float f1 = f0 * R(rng, 1.6f, 2.6f);
                int len = Mathf.Max(8, (int)(R(rng, 0.015f, 0.05f) * rate));
                float amp = R(rng, 0.05f, 0.25f);
                double phase = 0.0;
                for (int s = 0; s < len; s++)
                {
                    float t = (float)s / len;
                    float f = Mathf.Lerp(f0, f1, t * t);
                    phase += f / rate;
                    float env = Mathf.Min(1f, t * 8f) * (1f - t);
                    o[(start + s) % n] += Sin01(phase) * env * amp;
                }
            }
            Normalize(o, 0.7f);
            return o;
        }

        /// <summary>2 s engine hum: 38 Hz fundamental (76 whole cycles) + harmonics + pulsing rumble.</summary>
        static float[] GenEngine(int rate)
        {
            int n = rate * 2;
            int fade = rate / 5;
            int total = n + fade;
            var d = new float[total];
            var rng = new System.Random(3838);
            var rumble = new Svf(); rumble.Set(180f, 0.7f, rate);
            var tyre = new Svf(); tyre.Set(700f, 0.9f, rate);
            const double f0 = 38.0;
            for (int i = 0; i < total; i++)
            {
                double c = f0 * i / rate;
                float tone = Sin01(c) * 0.55f + Sin01(2.0 * c + 0.05) * 0.4f + Sin01(3.0 * c + 0.18) * 0.22f
                           + Sin01(4.0 * c + 0.11) * 0.16f + Sin01(6.0 * c + 0.32) * 0.08f;
                float w = Noise(rng);
                rumble.Tick(w); tyre.Tick(w);
                float pulse = 0.6f + 0.4f * Sin01(2.0 * c);
                d[i] = tone * 0.6f + rumble.Low * 2.2f * pulse + tyre.Bp * 0.12f;
            }
            var o = LoopCrossfade(d, n, false);
            Normalize(o, 0.75f);
            return o;
        }

        /// <summary>2 s electric motor whine + gear rumble; all periodic parts complete whole cycles in 2 s.</summary>
        static float[] GenMotor(int rate)
        {
            int n = rate * 2;
            int fade = rate / 5;
            int total = n + fade;
            var d = new float[total];
            var rng = new System.Random(5150);
            var rumble = new Svf(); rumble.Set(120f, 0.7f, rate);
            for (int i = 0; i < total; i++)
            {
                double t = (double)i / rate;
                double vib = 0.012 * System.Math.Sin(2.0 * System.Math.PI * 3.0 * t);
                double pw = 330.0 * t + vib;
                float whine = Sin01(pw) * 0.25f + Sin01(2.0 * pw) * 0.18f + Sin01(4.0 * pw) * 0.1f;
                float hi = Sin01(1320.0 * t + vib * 3.0) * 0.06f;
                double gc = 55.0 * t;
                float gear = (Sin01(gc) + Sin01(3.0 * gc) / 3f + Sin01(5.0 * gc) / 5f) * 0.18f;
                float clatter = 0.5f + 0.5f * Sin01(8.0 * t);
                rumble.Tick(Noise(rng));
                d[i] = whine + hi + gear * (0.7f + 0.3f * clatter) + rumble.Low * 1.8f * clatter;
            }
            var o = LoopCrossfade(d, n, false);
            Normalize(o, 0.7f);
            return o;
        }

        /// <summary>6 s distant crowd murmur: several formant-filtered voices with 3-6 Hz syllables + cup clinks.</summary>
        static float[] GenChatter(int rate)
        {
            int n = rate * 6;
            int fade = rate / 2;
            int total = n + fade;
            var d = new float[total];
            var rng = new System.Random(6006);

            for (int v = 0; v < 6; v++)
            {
                float f0 = R(rng, 95f, 230f);
                float gain = R(rng, 0.5f, 1f);
                float sylRate = R(rng, 3f, 6f);
                var form1 = new Svf();
                var form2 = new Svf();
                float F1 = 500f, F2 = 1500f, tF1 = 500f, tF2 = 1500f;
                form1.Set(F1, 5f, rate); form2.Set(F2, 6f, rate);
                double phase = rng.NextDouble();
                float env = 0f, sylAmp = 1f;
                int sylLen = 1, sylPos = 0;
                bool talking = rng.NextDouble() < 0.6;
                int phraseLeft = (int)(rate * R(rng, 0.2f, 2f));

                for (int i = 0; i < total; i++)
                {
                    if (--phraseLeft <= 0)
                    {
                        talking = !talking;
                        phraseLeft = (int)(rate * (talking ? R(rng, 0.8f, 2.6f) : R(rng, 0.25f, 1f)));
                    }
                    if (++sylPos >= sylLen)
                    {
                        sylPos = 0;
                        sylLen = Mathf.Max(1, (int)(rate / (sylRate * R(rng, 0.7f, 1.3f))));
                        tF1 = R(rng, 300f, 800f);
                        tF2 = R(rng, 900f, 2200f);
                        sylAmp = R(rng, 0.5f, 1f);
                    }
                    float shape = Mathf.Sin(Mathf.PI * sylPos / sylLen);
                    shape *= shape;
                    float target = talking ? shape * sylAmp : 0f;
                    env += (target - env) * 0.01f;

                    if ((i & 15) == 0)
                    {
                        F1 += (tF1 - F1) * 0.08f;
                        F2 += (tF2 - F2) * 0.08f;
                        form1.Set(F1, 5f, rate);
                        form2.Set(F2, 6f, rate);
                    }

                    phase += f0 * (0.92f + 0.16f * shape) / rate;
                    if (phase >= 1.0) phase -= 1.0;
                    float src = (float)(phase * 2.0 - 1.0) * 0.7f + Noise(rng) * 0.3f;
                    form1.Tick(src); form2.Tick(src);
                    d[i] += (form1.Bp + form2.Bp * 0.6f) * env * gain;
                }
            }

            // distance: soft lowpass + quiet room bed
            var bed = new Svf(); bed.Set(400f, 0.7f, rate);
            float lp = 0f;
            float a = 1f - Mathf.Exp(-2f * Mathf.PI * 1800f / rate);
            for (int i = 0; i < total; i++)
            {
                bed.Tick(Noise(rng));
                lp += (d[i] - lp) * a;
                d[i] = lp + bed.Low * 0.4f;
            }
            var o = LoopCrossfade(d, n, true);
            Normalize(o, 0.6f);

            // occasional cup / cutlery clinks (wrap around the loop)
            int clinks = 2 + rng.Next(2);
            for (int k = 0; k < clinks; k++)
            {
                int start = rng.Next(n);
                int hits = 1 + rng.Next(2);
                for (int h = 0; h < hits; h++)
                {
                    float fa = R(rng, 2400f, 2900f), fb = fa * R(rng, 1.45f, 1.6f);
                    float amp = R(rng, 0.08f, 0.16f);
                    int len = (int)(rate * 0.35f);
                    for (int s = 0; s < len; s++)
                    {
                        double t = (double)s / rate;
                        float e = Mathf.Exp(-(float)t * 14f);
                        o[(start + s) % n] += (Sin01(fa * t) + 0.6f * Sin01(fb * t)) * e * amp;
                    }
                    start += (int)(rate * R(rng, 0.12f, 0.3f));
                }
            }
            return o;
        }

        /// <summary>6 s: 3-6 short chirp phrases (2.5-5 kHz sweeps) with silence between, wrapped seamlessly.</summary>
        /// <summary>
        /// 8 s construction-site loop: generator hum (whole number of cycles), bursts of hammer blows with a
        /// metallic ring, a power-drill whine and a reversing truck's beeper. Events sit inside the loop so it is seamless.
        /// </summary>
        static float[] GenConstruction(int rate)
        {
            const float seconds = 8f;
            int n = (int)(seconds * rate);
            var o = new float[n];
            var rng = new System.Random(808);

            // Generator: 50 Hz + 100 Hz, 400 / 800 full cycles in 8 s -> seamless.
            for (int i = 0; i < n; i++)
            {
                double t = i / (double)rate;
                o[i] = 0.05f * Sin01(50.0 * t) + 0.03f * Sin01(100.0 * t);
            }

            // Hammer blows: 3 bursts of 3-5 hits.
            float[] burstStarts = { 0.4f, 3.1f, 5.6f };
            foreach (float bs in burstStarts)
            {
                int hits = rng.Next(3, 6);
                float tHit = bs;
                for (int h = 0; h < hits; h++)
                {
                    int s0 = (int)(tHit * rate);
                    int len = (int)(0.35f * rate);
                    float amp = R(rng, 0.35f, 0.55f);
                    for (int k = 0; k < len && s0 + k < n; k++)
                    {
                        float t = k / (float)rate;
                        float ring = 0.6f * Mathf.Sin(2f * Mathf.PI * 820f * t) + 0.35f * Mathf.Sin(2f * Mathf.PI * 1930f * t) + 0.2f * Mathf.Sin(2f * Mathf.PI * 3170f * t);
                        float thud = Noise(rng) * Mathf.Exp(-t * 90f);
                        o[s0 + k] += amp * (thud * 0.8f + ring * Mathf.Exp(-t * 18f) * 0.5f);
                    }
                    tHit += R(rng, 0.38f, 0.55f);
                }
            }

            // Power drill: one 1.3 s whine with a slight pitch wobble.
            {
                int s0 = (int)(2.0f * rate), len = (int)(1.3f * rate);
                double phase = 0;
                for (int k = 0; k < len && s0 + k < n; k++)
                {
                    float t = k / (float)rate;
                    float env = Mathf.Clamp01(t * 8f) * Mathf.Clamp01((1.3f - t) * 8f);
                    float f = 720f + 60f * Mathf.Sin(2f * Mathf.PI * 3f * t);
                    phase += f / rate;
                    float saw = (float)(2.0 * (phase - System.Math.Floor(phase + 0.5)));
                    o[s0 + k] += env * 0.12f * (saw + 0.3f * Noise(rng));
                }
            }

            // Reversing truck beeper: 4 beeps of 1 kHz.
            for (int b = 0; b < 4; b++)
            {
                int s0 = (int)((6.0f + b * 0.45f) * rate), len = (int)(0.22f * rate);
                for (int k = 0; k < len && s0 + k < n; k++)
                {
                    float t = k / (float)rate;
                    float env = Mathf.Clamp01(t * 200f) * Mathf.Clamp01((0.22f - t) * 200f);
                    o[s0 + k] += env * 0.09f * Mathf.Sign(Mathf.Sin(2f * Mathf.PI * 1000f * t));
                }
            }

            for (int i = 0; i < n; i++) o[i] = Mathf.Clamp(o[i], -1f, 1f);
            return o;
        }

        static float[] GenBirds(int rate)
        {
            int n = rate * 6;
            var o = new float[n];
            var rng = new System.Random(9090);
            int count = rng.Next(3, 7);
            for (int c = 0; c < count; c++)
            {
                int pos = rng.Next(n);
                int syl = rng.Next(1, 5);
                float amp = R(rng, 0.4f, 1f);
                float fa = R(rng, 2500f, 5000f), fb = R(rng, 2500f, 5000f);
                float warbleHz = R(rng, 2f, 5f);
                for (int s = 0; s < syl; s++)
                {
                    int len = Mathf.Max(16, (int)(R(rng, 0.04f, 0.12f) * rate));
                    float fs = fa * R(rng, 0.9f, 1.1f), fe = fb * R(rng, 0.9f, 1.1f);
                    double ph = 0.0;
                    for (int j = 0; j < len; j++)
                    {
                        float t = (float)j / len;
                        float f = Mathf.Lerp(fs, fe, t) + 250f * Mathf.Sin(2f * Mathf.PI * warbleHz * t);
                        f = Mathf.Clamp(f, 2500f, 5000f);
                        ph += f / rate;
                        float env = Mathf.Sin(Mathf.PI * t);
                        o[(pos + j) % n] += Sin01(ph) * env * env * amp;
                    }
                    pos += len + (int)(R(rng, 0.02f, 0.07f) * rate);
                }
            }
            Normalize(o, 0.6f);
            return o;
        }
    }
}
