namespace AcrophobiaVR
{
    /// <summary>Finishing area. Ends the level once every objective is complete.</summary>
    public class GoalZone : HeadZone
    {
        float nextHint;

        protected override void OnHeadEnter() => TryFinish();

        protected override void OnHeadStay()
        {
            if (UnityEngine.Time.time > nextHint) TryFinish();
        }

        void TryFinish()
        {
            var lc = LevelController.Instance;
            if (lc == null) return;
            if (!lc.TryFinish())
                nextHint = UnityEngine.Time.time + 6f;
            else
                enabled = false;
        }
    }
}