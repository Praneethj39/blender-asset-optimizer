// Demo: spins every part whose name contains "_Wheel_" around its own centre.
// Works only because the optimizer moved each part's pivot to its centre and
// the classifier named the wheels — no manual setup in Unity.
using UnityEngine;

public class WheelSpinner : MonoBehaviour
{
    public float degreesPerSecond = 360f;
    public Vector3 localAxis = Vector3.right;
    Transform[] wheels;

    void Start()
    {
        var list = new System.Collections.Generic.List<Transform>();
        foreach (var t in GetComponentsInChildren<Transform>())
            if (t.name.Contains("_Wheel_") && t.GetComponent<LODGroup>() != null)
                list.Add(t);
        wheels = list.ToArray();
        Debug.Log($"[WheelSpinner] found {wheels.Length} wheels");
    }

    void Update()
    {
        foreach (var w in wheels)
            w.Rotate(localAxis, degreesPerSecond * Time.deltaTime, Space.Self);
    }
}
