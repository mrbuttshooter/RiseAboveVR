namespace AcrophobiaVR
{
    /// <summary>Lets keyboard/mouse players use things that VR players grab or poke.</summary>
    public interface IDesktopUsable
    {
        string DesktopHint { get; }
        void DesktopUse();
    }
}