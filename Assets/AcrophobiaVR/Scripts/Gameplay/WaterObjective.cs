using System.Collections.Generic;

namespace AcrophobiaVR
{
    /// <summary>Water every flower pot on the ledge.</summary>
    public class WaterObjective : Objective
    {
        public List<FlowerPot> pots = new List<FlowerPot>();
        int bloomed;

        public override string ProgressSuffix => "  (" + bloomed + "/" + pots.Count + ")";

        void Awake()
        {
            foreach (var p in pots) if (p != null) p.owner = this;
        }

        public void NotifyBloomed()
        {
            bloomed++;
            HeadHud.Instance.ShowMessage("The flower bloomed! (" + bloomed + "/" + pots.Count + ")", 2f);
            ProceduralAudio.PlayChime(1.2f + bloomed * 0.15f);
            if (bloomed >= pots.Count) Complete();
        }
    }
}