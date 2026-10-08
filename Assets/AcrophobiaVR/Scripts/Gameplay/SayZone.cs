namespace AcrophobiaVR
{
    /// <summary>Companion says a line the first time the player walks here.</summary>
    public class SayZone : HeadZone
    {
        [UnityEngine.TextArea] public string line;
        public float seconds = 5f;
        bool said;

        protected override void OnHeadEnter()
        {
            if (said) return;
            said = true;
            Companion.Say(line, seconds);
        }
    }
}