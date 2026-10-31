using UnityEngine;
using UnityEngine.XR;

/// Shows the glove model on a controller only while a real, tracked controller is held. When the Quest is using hand tracking
/// the "controller" poses are just pointer poses, and a glove stuck to them looked broken. Logs what the headset reports so
/// the behaviour can be checked from adb logs.
public class HandVisibility : MonoBehaviour
{
    public XRNode node;
    private string lastReport;

    private void Update()
    {
        var d = InputDevices.GetDeviceAtXRNode(node);
        bool tracked = d.isValid && d.TryGetFeatureValue(CommonUsages.isTracked, out bool t) && t;
        bool controller = d.isValid && (d.characteristics & InputDeviceCharacteristics.Controller) != 0
                          && (d.characteristics & InputDeviceCharacteristics.HandTracking) == 0;
        bool show = tracked && controller;
        foreach (var r in GetComponentsInChildren<Renderer>(true)) if (r.enabled != show) r.enabled = show;

        string report = $"{node}: valid={d.isValid} name='{d.name}' characteristics={d.characteristics} tracked={tracked} glove={(show ? "shown" : "hidden")}";
        if (report != lastReport)
        {
            lastReport = report;
            Debug.Log("[HandVisibility] " + report);
        }
    }
}
