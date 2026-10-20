namespace AcrophobiaVR
{
    /// <summary>Finishing area. Ends the level once every objective is complete.</summary>
    public class GoalZone : HeadZone
    {
        float nextTry;
        float nextHint;

        protected override void OnHeadEnter() => TryFinish();

        protected override void OnHeadStay()
        {
            if (UnityEngine.Time.time > nextTry) TryFinish();
        }

        void TryFinish()
        {
            var lc = LevelController.Instance;
            if (lc == null) return;
            // Retry quietly every few frames (a goal reached in the same moment as the last task), hint now and then.
            bool hint = UnityEngine.Time.time > nextHint;
            if (!lc.TryFinish(hint))
            {
                nextTry = UnityEngine.Time.time + 0.25f;
                if (hint) nextHint = UnityEngine.Time.time + 5f;
            }
            else
                enabled = false;
        }
    }
}