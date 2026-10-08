using UnityEngine;

namespace AcrophobiaVR
{
    /// <summary>Runtime particle effects: sparkles, glass shards, wind streaks, fireflies, fireworks.</summary>
    public static class Effects
    {
        static Material particleMat;

        public static Material ParticleMaterial
        {
            get
            {
                if (particleMat != null) return particleMat;
                var shader = Shader.Find("Universal Render Pipeline/Particles/Unlit");
                if (shader == null) shader = Shader.Find("Sprites/Default");
                particleMat = new Material(shader);
                var tex = UIFactory.Circle.texture;
                particleMat.mainTexture = tex;
                if (particleMat.HasProperty("_BaseMap")) particleMat.SetTexture("_BaseMap", tex);
                // Additive, transparent
                if (particleMat.HasProperty("_Surface")) particleMat.SetFloat("_Surface", 1f);
                if (particleMat.HasProperty("_Blend")) particleMat.SetFloat("_Blend", 2f);
                particleMat.SetOverrideTag("RenderType", "Transparent");
                particleMat.SetInt("_SrcBlend", (int)UnityEngine.Rendering.BlendMode.SrcAlpha);
                particleMat.SetInt("_DstBlend", (int)UnityEngine.Rendering.BlendMode.One);
                particleMat.SetInt("_ZWrite", 0);
                particleMat.EnableKeyword("_SURFACE_TYPE_TRANSPARENT");
                particleMat.renderQueue = 3000;
                return particleMat;
            }
        }

        /// <summary>Lets the editor builder hand over a material asset so the shader is included in builds.</summary>
        public static void SetMaterial(Material m)
        {
            if (m != null) particleMat = m;
        }

        static ParticleSystem Create(string name, Vector3 pos, Transform parent = null)
        {
            var go = new GameObject(name);
            if (parent != null) go.transform.SetParent(parent, false);
            go.transform.position = pos;
            var ps = go.AddComponent<ParticleSystem>();
            ps.Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear);
            go.GetComponent<ParticleSystemRenderer>().material = ParticleMaterial;
            return ps;
        }

        public static void Sparkle(Vector3 pos, Color color)
        {
            var ps = Create("Sparkle", pos);
            var main = ps.main;
            main.duration = 1f;
            main.loop = false;
            main.startLifetime = new ParticleSystem.MinMaxCurve(0.5f, 1.1f);
            main.startSpeed = new ParticleSystem.MinMaxCurve(0.6f, 2.2f);
            main.startSize = new ParticleSystem.MinMaxCurve(0.03f, 0.09f);
            main.startColor = new ParticleSystem.MinMaxGradient(color, Color.white);
            main.gravityModifier = -0.05f;
            main.stopAction = ParticleSystemStopAction.Destroy;
            var em = ps.emission;
            em.rateOverTime = 0f;
            em.SetBursts(new[] { new ParticleSystem.Burst(0f, 40) });
            var shape = ps.shape;
            shape.shapeType = ParticleSystemShapeType.Sphere;
            shape.radius = 0.1f;
            var col = ps.colorOverLifetime;
            col.enabled = true;
            col.color = Fade(color);
            ps.Play();
        }

        public static void Shards(Vector3 pos, Vector3 size)
        {
            var ps = Create("Shards", pos);
            var main = ps.main;
            main.duration = 1f;
            main.loop = false;
            main.startLifetime = 2.5f;
            main.startSpeed = new ParticleSystem.MinMaxCurve(0.2f, 1.5f);
            main.startSize = new ParticleSystem.MinMaxCurve(0.04f, 0.15f);
            main.startColor = new Color(0.8f, 0.95f, 1f, 0.8f);
            main.gravityModifier = 1f;
            main.stopAction = ParticleSystemStopAction.Destroy;
            var em = ps.emission;
            em.rateOverTime = 0f;
            em.SetBursts(new[] { new ParticleSystem.Burst(0f, 80) });
            var shape = ps.shape;
            shape.shapeType = ParticleSystemShapeType.Box;
            shape.scale = new Vector3(size.x, 0.05f, size.z);
            ps.Play();
        }

        public static ParticleSystem CreateWindStreaks(Transform parent)
        {
            var ps = Create("WindStreaks", parent.position, parent);
            var main = ps.main;
            main.duration = 3f;
            main.loop = false;
            main.startLifetime = 1.2f;
            main.startSpeed = 18f;
            main.startSize = new ParticleSystem.MinMaxCurve(0.02f, 0.05f);
            main.startColor = new Color(1f, 1f, 1f, 0.35f);
            main.simulationSpace = ParticleSystemSimulationSpace.World;
            var em = ps.emission;
            em.rateOverTime = 120f;
            var shape = ps.shape;
            shape.shapeType = ParticleSystemShapeType.Box;
            shape.scale = new Vector3(2f, 4f, 30f);
            shape.position = new Vector3(-12f, 1f, 0f);
            shape.rotation = new Vector3(0f, 90f, 0f);
            var r = ps.GetComponent<ParticleSystemRenderer>();
            r.renderMode = ParticleSystemRenderMode.Stretch;
            r.lengthScale = 6f;
            return ps;
        }

        public static ParticleSystem Fireflies(Vector3 center, float radius, Transform parent = null)
        {
            var ps = Create("Fireflies", center, parent);
            var main = ps.main;
            main.loop = true;
            main.startLifetime = new ParticleSystem.MinMaxCurve(4f, 8f);
            main.startSpeed = 0.15f;
            main.startSize = new ParticleSystem.MinMaxCurve(0.03f, 0.07f);
            main.startColor = new Color(1f, 0.95f, 0.5f, 1f);
            main.maxParticles = 200;
            var em = ps.emission;
            em.rateOverTime = 15f;
            var shape = ps.shape;
            shape.shapeType = ParticleSystemShapeType.Box;
            shape.scale = new Vector3(radius * 2, 2.5f, radius * 2);
            var noise = ps.noise;
            noise.enabled = true;
            noise.strength = 0.3f;
            noise.frequency = 0.4f;
            var col = ps.colorOverLifetime;
            col.enabled = true;
            col.color = Fade(new Color(1f, 0.95f, 0.5f));
            ps.Play();
            return ps;
        }

        public static void Firework(Vector3 pos)
        {
            Color c = Color.HSVToRGB(Random.value, 0.7f, 1f);
            var ps = Create("Firework", pos);
            var main = ps.main;
            main.duration = 2f;
            main.loop = false;
            main.startLifetime = new ParticleSystem.MinMaxCurve(1.2f, 2f);
            main.startSpeed = new ParticleSystem.MinMaxCurve(8f, 14f);
            main.startSize = new ParticleSystem.MinMaxCurve(0.25f, 0.5f);
            main.startColor = new ParticleSystem.MinMaxGradient(c, Color.white);
            main.gravityModifier = 0.35f;
            main.maxParticles = 400;
            main.stopAction = ParticleSystemStopAction.Destroy;
            var em = ps.emission;
            em.rateOverTime = 0f;
            em.SetBursts(new[] { new ParticleSystem.Burst(0f, 250) });
            var shape = ps.shape;
            shape.shapeType = ParticleSystemShapeType.Sphere;
            shape.radius = 0.3f;
            var lim = ps.limitVelocityOverLifetime;
            lim.enabled = true;
            lim.dampen = 0.08f;
            lim.limit = 4f;
            var col = ps.colorOverLifetime;
            col.enabled = true;
            col.color = Fade(c);
            var trails = ps.trails;
            trails.enabled = true;
            trails.lifetime = 0.25f;
            trails.widthOverTrail = 0.4f;
            ps.GetComponent<ParticleSystemRenderer>().trailMaterial = ParticleMaterial;
            ps.Play();
            ProceduralAudio.PlayBoom();
        }

        static ParticleSystem.MinMaxGradient Fade(Color c)
        {
            var g = new Gradient();
            g.SetKeys(new[] { new GradientColorKey(Color.white, 0f), new GradientColorKey(c, 0.3f), new GradientColorKey(c, 1f) },
                new[] { new GradientAlphaKey(1f, 0f), new GradientAlphaKey(1f, 0.6f), new GradientAlphaKey(0f, 1f) });
            return new ParticleSystem.MinMaxGradient(g);
        }
    }
}