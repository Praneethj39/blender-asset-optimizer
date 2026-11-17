// Put this file in Assets/Editor/. Any model dropped into a folder called
// "Optimized" is imported with pipeline-friendly settings, and the LODGroups
// Unity builds from the _LOD0/_LOD1/_LOD2 names get sensible switch distances.
using UnityEditor;
using UnityEngine;

public class AutoLODImporter : AssetPostprocessor
{
    // fraction of screen height at which each LOD stops being used
    static readonly float[] Transitions = { 0.5f, 0.2f, 0.05f };

    bool IsPipelineAsset => assetPath.Replace('\\', '/').Contains("/Optimized/");

    void OnPreprocessModel()
    {
        if (!IsPipelineAsset) return;
        var mi = (ModelImporter)assetImporter;
        mi.useFileScale = true;          // optimizer exports 1 unit = 1 m
        mi.globalScale = 1f;
        mi.isReadable = false;           // save memory on standalone headsets
        mi.meshCompression = ModelImporterMeshCompression.Medium;
        mi.generateSecondaryUV = true;   // lightmap UVs
        mi.importAnimation = false;
        mi.importCameras = false;
        mi.importLights = false;
    }

    void OnPostprocessModel(GameObject root)
    {
        if (!IsPipelineAsset) return;
        var groups = root.GetComponentsInChildren<LODGroup>();
        foreach (var g in groups)
        {
            var lods = g.GetLODs();
            for (int i = 0; i < lods.Length && i < Transitions.Length; i++)
                lods[i].screenRelativeTransitionHeight = Transitions[i];
            g.SetLODs(lods);
            g.RecalculateBounds();
        }

        int noLod = 0;
        foreach (var mf in root.GetComponentsInChildren<MeshFilter>())
            if (!mf.name.Contains("_LOD")) noLod++;

        Debug.Log($"[AutoLOD] {assetPath}: {groups.Length} LOD groups");
        if (noLod > 0)
            Debug.LogWarning($"[AutoLOD] {assetPath}: {noLod} meshes have no LOD chain");
    }
}
