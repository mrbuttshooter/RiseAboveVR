namespace AcrophobiaVR
{
    /// <summary>Complete by pressing a physical button (e.g. launch the fireworks).</summary>
    public class PressObjective : Objective
    {
        public PressButton button;

        void Start()
        {
            if (button != null) button.onPressed.AddListener(OnPressed);
        }

        void OnPressed()
        {
            if (IsActive) Complete();
        }
    }
}