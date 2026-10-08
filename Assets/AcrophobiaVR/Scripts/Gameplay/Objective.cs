using System;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace AcrophobiaVR
{
    /// <summary>Base class for level tasks. Tasks only progress once the level has started.</summary>
    public abstract class Objective : MonoBehaviour
    {
        public string description = "Task";
        [TextArea] public string companionLineOnComplete;

        public bool IsComplete { get; private set; }
        public bool IsActive { get; private set; }
        public string Description => description;
        public virtual string ProgressSuffix => "";

        public event Action<Objective> Completed;

        public virtual void Activate() => IsActive = true;

        protected void Complete()
        {
            if (IsComplete) return;
            IsComplete = true;
            SessionLogger.Log(SceneManager.GetActiveScene().name, "objective_complete", description);
            ProceduralAudio.PlaySuccess();
            FearSystem.Relief(0.3f);
            if (!string.IsNullOrEmpty(companionLineOnComplete)) Companion.Say(companionLineOnComplete);
            Completed?.Invoke(this);
        }
    }
}