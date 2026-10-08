using UnityEngine;

namespace AcrophobiaVR
{
    /// <summary>Plays a fireworks show over the city (level 3 finale).</summary>
    public class FireworksShow : MonoBehaviour
    {
        public float duration = 9f;
        public float area = 60f;
        public float height = 40f;

        public void Play() => StartCoroutine(Run());

        System.Collections.IEnumerator Run()
        {
            float end = Time.time + duration;
            while (Time.time < end)
            {
                Vector3 p = transform.position + new Vector3(Random.Range(-area, area), Random.Range(height * 0.6f, height), Random.Range(-area * 0.3f, area * 0.3f));
                Effects.Firework(p);
                yield return new WaitForSeconds(Random.Range(0.25f, 0.7f));
            }
        }
    }
}
