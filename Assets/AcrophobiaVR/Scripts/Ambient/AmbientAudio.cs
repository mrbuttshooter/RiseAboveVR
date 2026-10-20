using UnityEngine;

namespace AcrophobiaVR
{
    /// <summary>
    /// Streaming procedural ambience mixed on the audio thread: wind that grows with height (and gusts),
    /// distant city hum, lift machinery, and a soft major-chord pad + birdsong in the Calm Meadow.
    /// </summary>
    [RequireComponent(typeof(AudioSource))]
    public class AmbientAudio : MonoBehaviour
    {
        public static float GustBoost;
        public static float Machinery;
        static bool meadow;
        static AmbientAudio instance;

        public float groundY = 0f;
        public float maxHeight = 150f;
        public float cityLevel = 0.5f;
        public bool startInMeadow;

        float windTarget, windVol, cityVol, padVol, machVol;
        float lp1, lp2, lp3, hum;
        double phase1, phase2, phase3, birdPhase;
        float birdTimer, birdFreq, birdEnv;
        System.Random rng = new System.Random(42);
        int sampleRate;

        public static void SetMeadow(bool on) => meadow = on;

        void Awake()
        {
            instance = this;
            meadow = startInMeadow;
            GustBoost = 0f;
            Machinery = 0f;
            sampleRate = AudioSettings.outputSampleRate;
            var src = GetComponent<AudioSource>();
            src.playOnAwake = true;
            src.loop = true;
            src.spatialBlend = 0f;
            src.clip = AudioClip.Create("ambience", sampleRate, 2, sampleRate, true, OnRead);
            src.Play();
        }

        void Update()
        {
            var rig = PlayerRig.Instance;
            float h = rig != null ? rig.Head.position.y - groundY : 0f;
            float k = Mathf.Clamp01(h / maxHeight);
            float windMul = Difficulty.Wind;
            windTarget = meadow ? 0.04f : Mathf.Lerp(0.05f, 0.55f, Mathf.Sqrt(k)) * windMul + GustBoost * 0.45f * windMul;
            cityVol = meadow ? 0f : cityLevel * Mathf.Lerp(0.35f, 0.08f, k);
            padVol = meadow ? 0.12f : 0.035f;
            machVol = Machinery * 0.25f;
        }

        void OnRead(float[] data)
        {
            float sr = sampleRate;
            for (int i = 0; i < data.Length; i += 2)
            {
                windVol += (windTarget - windVol) * 0.00005f;
                float n = (float)(rng.NextDouble() * 2 - 1);
                lp1 += (n - lp1) * 0.02f;               // wind body
                lp2 += (n - lp2) * (0.004f + 0.002f * (float)System.Math.Sin(phase3 * 0.0003)); // whistle movement
                lp3 += (n - lp3) * 0.0015f;             // distant city rumble
                float wind = (lp1 * 0.6f + lp2 * 3f) * windVol;

                hum = (float)System.Math.Sin(phase3 * 2 * System.Math.PI * 55 / sr) * 0.3f + lp3 * 6f;
                float city = hum * cityVol * 0.35f;

                float pad = ((float)System.Math.Sin(phase1 * 2 * System.Math.PI * 261.63 / sr) +
                             (float)System.Math.Sin(phase1 * 2 * System.Math.PI * 329.63 / sr) * 0.7f +
                             (float)System.Math.Sin(phase1 * 2 * System.Math.PI * 392.0 / sr) * 0.6f +
                             (float)System.Math.Sin(phase1 * 2 * System.Math.PI * 523.25 / sr) * 0.3f)
                            * (0.75f + 0.25f * (float)System.Math.Sin(phase2 * 2 * System.Math.PI * 0.1 / sr)) * padVol * 0.25f;

                float mach = ((float)System.Math.Sin(phase3 * 2 * System.Math.PI * 110 / sr) * 0.5f + lp1 * 0.5f) * machVol;

                float bird = 0f;
                if (meadow)
                {
                    birdTimer -= 1f / sr;
                    if (birdTimer <= 0f)
                    {
                        birdTimer = 1.5f + (float)rng.NextDouble() * 4f;
                        birdFreq = 2500f + (float)rng.NextDouble() * 1500f;
                        birdEnv = 1f;
                    }
                    if (birdEnv > 0.001f)
                    {
                        birdEnv *= 0.99985f;
                        float f = birdFreq * (1f + 0.15f * (float)System.Math.Sin(birdPhase * 0.002));
                        birdPhase += 1;
                        bird = (float)System.Math.Sin(birdPhase * 2 * System.Math.PI * f / sr) * birdEnv * 0.05f
                               * (float)System.Math.Abs(System.Math.Sin(birdPhase * 0.0015));
                    }
                }

                phase1 += 1; phase2 += 1; phase3 += 1;
                float s = Mathf.Clamp(wind + city + pad + mach + bird, -1f, 1f);
                data[i] = s;
                if (i + 1 < data.Length) data[i + 1] = s;
            }
        }
    }
}