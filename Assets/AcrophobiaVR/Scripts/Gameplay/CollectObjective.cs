using System.Collections.Generic;
using UnityEngine;

namespace AcrophobiaVR
{
    /// <summary>Find and grab N items (lost tools, the stranded cat...).</summary>
    public class CollectObjective : Objective
    {
        public List<Collectible> items = new List<Collectible>();

        int collected;

        public override string ProgressSuffix => items.Count > 1 ? "  (" + collected + "/" + items.Count + ")" : "";

        void Awake()
        {
            foreach (var c in items)
                if (c != null) c.Owner = this;
        }

        public void NotifyCollected(Collectible c)
        {
            if (!IsActive || IsComplete) return;
            collected++;
            HeadHud.Instance.ShowMessage(c.displayName + " found! (" + collected + "/" + items.Count + ")", 2.5f);
            if (collected >= items.Count) Complete();
        }
    }
}