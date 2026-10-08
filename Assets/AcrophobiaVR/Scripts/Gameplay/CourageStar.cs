using UnityEngine;
using UnityEngine.SceneManagement;

namespace AcrophobiaVR
{
    /// <summary>
    /// Optional golden stars placed at the scariest spots (end of a plank, the very edge).
    /// Collect by reaching them with your head or hands.
    /// </summary>
    public class CourageStar : MonoBehaviour
    {
        public static int Total { get; private set; }
        public static int Collected { get; private set; }

        public float radius = 0.55f;
        bool taken;
        float reach;
        Vector3 basePos;

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.SubsystemRegistration)]
        static void ResetStatics() { Total = 0; Collected = 0; }

        public static void Init(int total) { Total = total; Collected = 0; }

        void Start() => basePos = transform.position;

        void Update()
        {
            if (taken) return;
            transform.Rotate(0f, 90f * Time.deltaTime, 0f, Space.World);
            transform.position = basePos + Vector3.up * Mathf.Sin(Time.time * 2f + basePos.x) * 0.08f;

            var rig = PlayerRig.Instance;
            if (rig == null) return;
            // Desktop players can't lean over a railing, so give them a longer reach.
            reach = rig.IsDesktop ? radius * 1.8f : radius;
            if (Near(rig.Head.position) || Near(rig.LeftHand) || Near(rig.RightHand)) Take();
        }

        bool Near(Transform t) => t != null && Near(t.position);

        bool Near(Vector3 p) => (p - transform.position).sqrMagnitude < reach * reach;

        void Take()
        {
            taken = true;
            Collected++;
            SessionLogger.Log(SceneManager.GetActiveScene().name, "courage_star", Collected + "/" + Total);
            ProceduralAudio.PlaySuccess();
            Haptics.Light();
            Effects.Sparkle(transform.position, UIFactory.Gold);
            HeadHud.Instance.ShowMessage("Courage star! " + Collected + "/" + Total, 2.5f);
            if (Collected == Total) Companion.Say("Every courage star! You went to the scariest spots on purpose. That is real bravery.");
            gameObject.SetActive(false);
        }
    }
}