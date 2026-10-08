using System.Collections;
using UnityEngine;
using UnityEngine.XR.Interaction.Toolkit;
using UnityEngine.XR.Interaction.Toolkit.Interactables;

namespace AcrophobiaVR
{
    /// <summary>An item picked up by grabbing it (VR) or clicking it (desktop). Vanishes with a sparkle.</summary>
    public class Collectible : MonoBehaviour, IDesktopUsable
    {
        public string displayName = "Item";
        public bool isCat;
        public CollectObjective Owner { get; set; }

        bool taken;
        Vector3 startPos;

        void Start()
        {
            startPos = transform.position;
            var grab = GetComponent<XRBaseInteractable>();
            if (grab != null) grab.selectEntered.AddListener(OnGrabbed);
        }

        void Update()
        {
            if (taken) return;
            // Gentle idle animation so items are easy to spot.
            if (!isCat) transform.Rotate(0f, 40f * Time.deltaTime, 0f, Space.World);
        }

        void OnGrabbed(SelectEnterEventArgs args) => Take();

        public string DesktopHint => isCat ? "Click to rescue the cat" : "Click to pick up " + displayName;

        public void DesktopUse() => Take();

        void Take()
        {
            if (taken) return;
            if (Owner != null && !Owner.IsActive)
            {
                HeadHud.Instance.ShowMessage("Start the level first", 1.5f);
                return;
            }
            taken = true;
            Haptics.Medium();
            if (isCat) ProceduralAudio.PlayMeowAt(transform.position); else ProceduralAudio.PlayChime(1.4f);
            if (isCat) Achievements.Unlock("cat_rescuer");
            if (Owner != null) Owner.NotifyCollected(this);
            StartCoroutine(Vanish());
        }

        IEnumerator Vanish()
        {
            var grab = GetComponent<XRBaseInteractable>();
            if (grab != null) grab.enabled = false;
            Effects.Sparkle(transform.position, isCat ? UIFactory.Calm : UIFactory.Gold);
            Vector3 s = transform.localScale;
            for (float t = 0; t < 0.4f; t += Time.deltaTime)
            {
                transform.localScale = Vector3.Lerp(s, Vector3.zero, t / 0.4f);
                transform.position += Vector3.up * Time.deltaTime * 0.6f;
                yield return null;
            }
            gameObject.SetActive(false);
        }
    }
}